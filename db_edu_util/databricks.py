"""
This module is a pared down replacement for databricks-cli functionality.
It replicates some of the functionality of the databricks-cli package, including
using the same configuration file. However, it interacts solely with the
Databricks REST API, without using the databricks-cli package at all.
"""
from __future__ import annotations # PEP 563 (allows annotation forward refs)

import os
import json
from dataclasses import dataclass
from configparser import ConfigParser
import requests
from enum import Enum, auto
import base64

from typing import Optional, Sequence, NoReturn, Tuple, Dict, Any


__all__ = ['DatabricksError', 'Workspace', 'StatusCode',
           'ObjectInfo', 'ObjectType', 'NotebookLanguage']

API_PATH = 'api/2.0'
WORKSPACE_PATH = f'{API_PATH}/workspace'

# -----------------------------------------------------------------------------
# Private Functions
# -----------------------------------------------------------------------------

def _fix_host(host: str) -> str:
    """
    Remove any leading "https://" from a host

    :param host: the host string

    :return: possibly modified result
    """
    if host.startswith('https://'):
        host = host[len('https://'):]
    return host.replace('/', '')


def _map_rest_error(json_data: Dict[str, str]) -> Tuple[StatusCode,
                                                        Optional[str]]:
    """
    Map a Databricks REST API error (from the returned JSON) into a
    status code and a message.

    :param json_data: the JSON returned from the REST API

    :return: A (status code, message) tuple. The message may be None.
    """
    error_code = json_data.get('error_code')
    rest_message = json_data.get('message')
    if error_code == 'RESOURCE_DOES_NOT_EXIST':
        code = StatusCode.NOT_FOUND
        message = rest_message
    elif error_code == 'RESOURCE_ALREADY_EXISTS':
        code = StatusCode.ALREADY_EXISTS
        message = rest_message
    elif error_code:
        code = StatusCode.UNKNOWN_ERROR
        if rest_message:
            message = f'{error_code}: {rest_message}'
        else:
            message = error_code
    else:
        code = StatusCode.UNKNOWN_ERROR
        message = rest_message or 'Unknown error'

    return (code, message)

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class StatusCode(Enum):
    """
    Status codes used in DatabricksError exceptions.
    """
    NOT_FOUND = auto()
    ALREADY_EXISTS = auto()
    CONFIG_ERROR = auto()
    UNKNOWN_ERROR = auto()

class DatabricksError(Exception):
    """
    Thrown to indicate errors with the databricks_cli invocation.
    """
    def __init__(self,
                 message: Optional[str] = None,
                 code: Optional[StatusCode] = StatusCode.UNKNOWN_ERROR):
        super(Exception, self).__init__(message)
        self.code = code
        self.message = message


class RESTClient(object):
    """
    Base class for exposed API classes. Right now, there's only one
    exposed API class (Workspace), but there may be more in the future.
    """
    def __init__(self,
                 profile: str = 'DEFAULT',
                 config: str = "~/.databrickscfg"):
        """
        :param profile: the name of the Databricks profile to use.
        :param config:  path to an alternate configuration to use, instead of
                        "~/.databrickscfg". Can contain a "~", which will be
                        expanded.

        :raises DatabricksError: configuration failure
        """
        if profile is None:
            profile = 'DEFAULT'
        (self._host, self._token, self._home) = self._get_profile(profile,
                                                                  config)
        self._profile = profile

    @property
    def host(self):
        return self._host

    @property
    def profile(self):
        return self._profile

    @property
    def token(self):
        return self._token

    @property
    def home(self):
        return self._home

    def _get_profile(self, profile: str,
                     config: str) -> Tuple[str, str, Optional[str]]:
        config_file = os.path.expanduser(config)
        if not os.path.exists(config_file):
            raise DatabricksError(
                message=f'"{config_file}" does not exist.',
                code=StatusCode.CONFIG_ERROR
            )

        cfg = ConfigParser()
        try:
            cfg.read(config_file)
        except Exception as e:
            raise DatabricksError(
                message=f'Cannot read "{config_file}": {e}',
                code=StatusCode.CONFIG_ERROR
            )

        # Note that DEFAULT is always present, but might be empty.
        if (profile != 'DEFAULT') and (not cfg.has_section(profile)):
            raise DatabricksError(
                message=f'"{config_file}" has no profile "{profile}".',
                code=StatusCode.CONFIG_ERROR
            )

        section = cfg[profile]
        keys = set(section.keys())
        for required in ('host', 'token'):
            if required not in keys:
                raise DatabricksError(
                    message=f'[{profile}] in "{config_file}" is missing a '
                    f'value for "{required}".',
                    code=StatusCode.CONFIG_ERROR
                )

        host = _fix_host(section['host'])

        home = os.getenv('DB_SHARD_HOME')
        if not home:
            home = section.get('home')

        if not home:
            username = section.get('username')
            if username:
                home = f'/Users/{username}'

        if home:
            home = home.rstrip('/')
            if not home:
                # Stripped away all the '/' and got an empty string.
                # So, just make it the top.
                home = '/'

        return (host, section['token'], home)

    def _issue_get(self, url: str, params: Dict[str, Any]) -> requests.Response:
        resp = requests.get(url, params=params, headers=self._auth_header())
        self._check_response(resp)
        data = resp.json()
        if resp.status_code != 200:
            (code, message) = _map_rest_error(data)
            raise DatabricksError(code=code, message=message)

        return resp

    def _issue_post(self,
                    url: str,
                    params: Dict[str, Any],
                    file: Optional[str] = None) -> requests.Response:
        # Payload HAS to be manually encoded as JSON. Otherwise, it's
        # form-encoded. See
        # http://docs.python-requests.org/en/master/user/quickstart/
        headers = self._auth_header()
        if file:
            resp = requests.post(url, data=params, headers=headers,
                                 files={'file': open(file, 'rb')})
        else:
            payload = json.dumps(params)
            resp = requests.post(url, data=payload, headers=headers)

        self._check_response(resp)
        data = resp.json()
        if resp.status_code != 200:
            (code, message) = _map_rest_error(data)
            raise DatabricksError(code=code, message=message)

        return resp

    def _check_response(self, resp: requests.Response) -> NoReturn:
        """
        Ensure that the response has a valid status code (200 series) and
        is JSON. Raises an exception on error. Returns quietly if all is
        well.

        :param resp: the response to check
        """
        def get_text():
            return resp.content.decode(encoding='utf-8').replace('\n', '')

        # Content-type is of the form "text/html" or "text/json; charset=utf-8"
        content_type = (
            resp
                .headers
                .get('Content-Type', '<unknown>')
                .split(';')[0]
        )

        if resp.status_code in [401, 403]:
            msg = (
                f"REST API returned HTTP status code {resp.status_code}. "
                "Perhaps your API token is invalid."
            )
            if content_type == 'text/html':
                raise DatabricksError(f"{msg}\nResponse text: {get_text()}")

            raise DatabricksError(msg)


        if content_type in  ['application/json', 'text/json']:
            return None

        if content_type == 'text/html':
            raise DatabricksError(
                f"REST API error. HTTP status code is {resp.status_code}, "
                f"content: {get_text()}"
            )

        raise DatabricksError(
            f"REST API Error: Got back unexpected content type {content_type}. "
            f"HTTP status code is {resp.status_code} "
        )


    def _auth_header(self):
        return {'Authorization': f'Bearer {self._token}'}


class ObjectType(Enum):
    """
    Type of a remote object. See
    https://docs.databricks.com/api/latest/workspace.html#workspaceobjecttype
    """
    NOTEBOOK = 'NOTEBOOK'
    DIRECTORY = 'DIRECTORY'
    LIBRARY = 'LIBRARY'


class NotebookLanguage(Enum):
    """
    Language of a remote notebook. See
    https://docs.databricks.com/api/latest/workspace.html#workspaceobjecttype
    """
    SCALA = 'SCALA'
    PYTHON = 'PYTHON'
    R = 'R'
    SQL = 'SQL'

    def extension(self):
        """
        Return the extension for this language.
        """
        if self == NotebookLanguage.SCALA:
            return '.scala'
        if self == NotebookLanguage.PYTHON:
            return '.py'
        if self == NotebookLanguage.SQL:
            return '.sql'
        if self == NotebookLanguage.R:
            return '.r'

    @classmethod
    def notebook_extension(cls, nb: str) -> str:
        extensions = ['.scala', '.py', '.sql', '.SQL', '.r', '.R', '.ipynb']
        for ext in extensions:
            if nb.endswith(ext):
                return ext
        return ''

    @classmethod
    def from_extension(cls, ext: str) -> Optional[NotebookLanguage]:
        ext = ext.lower()
        if ext == '.py':
            return NotebookLanguage.PYTHON
        if ext == '.r':
            return NotebookLanguage.R
        if ext == '.scala':
            return NotebookLanguage.SCALA
        if ext == '.sql':
            return NotebookLanguage.SQL

        return None

    @classmethod
    def from_path(cls, path: str) -> NotebookLanguage:
        _, ext = os.path.splitext(path)
        return cls.from_extension(ext)


@dataclass
class ObjectInfo:
    """
    Information about a remote file, usually returned from Workspace.ls().
    """
    path: str
    object_type: ObjectType
    language: Optional[NotebookLanguage]

    def is_dir(self):
        """
        Is this thing a remote directory?
        """
        return self.object_type == ObjectType.DIRECTORY

    def is_notebook(self):
        """
        Is this thing a notebook?
        """
        return self.object_type == ObjectType.NOTEBOOK

    def is_library(self):
        """
        Is this thing a library?
        """
        return self.object_type == ObjectType.LIBRARY


class Workspace(RESTClient):
    """
    Provides a subset of the functionality of "databricks workspace".
    In addition to the methods, below, instances of this class also have
    four read-only properties from the configuration:

    - host: the host name (without any leading "https://")
    - token: the API token
    - home: the (shard) home setting, if defined, or None
    - profile: the Databricks profile passed into the constructor
    """
    def __init__(self,
                 profile: str = 'DEFAULT',
                 config: str = '~/.databrickscfg'):
        """
        Create a new Workspace object.

        :param profile: the name of the Databricks profile to use.
        :param config:  path to an alternate configuration to use, instead of
                        "~/.databrickscfg". Can contain a "~", which will be
                        expanded.

        :raises DatabricksError: configuration failure
        """
        super().__init__(profile, config)

    def ls(self, workspace_path: str):
        """
        List a path in the configuration.

        :param workspace_path: the remote path. If this path is relative, and
                               "home" is defined, the path will be created
                               from "home" + "workspace_path". Otherwise,
                               an error will be thrown.

        :return: the list of files/folders

        :raises DatabricksError: on error, or on file not found. The
                code field will be set appropriately.
        """
        url = self._workspace_url('list')
        payload = {'path': self._adjust_remote_path(workspace_path)}
        try:
            resp = self._issue_get(url, payload)
            data = resp.json()
            files = []
            for f in data.get('objects', []):
                t = self._map_type(f.get('object_type'))
                if t == ObjectType.NOTEBOOK:
                    lang = self._map_lang(f.get('language'))
                else:
                    lang = None
                files.append(
                    ObjectInfo(path=f['path'], object_type=t, language=lang)
                )
            return files

        except DatabricksError:
            raise

        except Exception as e:
            raise DatabricksError(
                f'Unable to list "{workspace_path}" on "{self._host}": {e}'
            )

    def rm(self, workspace_path: str, recursive: bool = True) -> NoReturn:
        """
        Remove a path on the remote workspace.

        :param workspace_path: the remote path. If this path is relative, and
                               "home" is defined or "DB_SHARD_HOME" is set in
                               the environment, the path will be created
                               from "home" + "workspace_path". Otherwise,
                               an error will be thrown.
        :param recursive:      if the path is a directory, do a recursive
                               removal if True, otherwise don't.

        :raises DatabricksError: on error, or on file not found. The
                code field will be set appropriately.
        """
        url = self._workspace_url('delete')
        payload = {
            'path': self._adjust_remote_path(workspace_path),
            'recursive': recursive
        }

        try:
            self._issue_post(url, payload)

        except DatabricksError:
            raise

        except Exception as e:
            raise DatabricksError(
                f'Unable to remove "{workspace_path}" on "{self._host}": {e}'
            )

    def mkdirs(self, workspace_path: str) -> NoReturn:
        """
        Creates the given directory and necessary parent directories if
        they do not exist. If there exists an object (not a directory) at any
        prefix of the input path, an exception is raised.

        :param workspace_path: the remote path. If this path is relative, and
                               "home" is defined, the path will be created
                               from "home" + "workspace_path". Otherwise,
                               an error will be thrown.

        :raises DatabricksError: on error. The code field will be set
            to StatusCode.ALREADY_EXISTS if something exists in any
            prefix of the input path. It'll be set to StatusCode.CONFIG_ERROR
            if the path is relative and "home" isn't set. Otherwise, it'll be
            set to StatusCode.UNKNOWN_ERROR.
        """
        url = self._workspace_url('mkdirs')
        payload = {'path': self._adjust_remote_path(workspace_path)}
        try:
            self._issue_post(url, payload)

        except DatabricksError:
            raise

        except Exception as e:
            raise DatabricksError(
                f'Unable to create "{workspace_path}" on "{self._host}": {e}'
            )

    def import_notebook(self,
                        local_path: str,
                        workspace_path: str,
                        overwrite: bool = False) -> NoReturn:
        """
        Imports a notebook to the specified remote workspace path.

        :param local_path:     the path to the local file
        :param workspace_path: the path to the target file in the Databricks
                               workspace. If this file has an extension, the
                               extension is stripped. If the path is relative,
                               and "home" is defined, the path will be created
                               from "home" + "workspace_path". Otherwise,
                               an error will be thrown.
        :param overwrite:      whether or not to overwrite existing files

        :raises DatabricksError: on error. The code field will be set
            to StatusCode.ALREADY_EXISTS if the remote folder exists already.
            It will be set to StatusCode.CONFIG_ERROR if the path is relative
            and "home" isn't set. It will be set to StatusCode.NOT_FOUND if the
            local directory doesn't exist. It'll be set to something else
            otherwise.
        """

        path, ext = os.path.splitext(workspace_path)
        language = NotebookLanguage.from_path(local_path)
        format = self._format_for_ext(ext)
        payload = {
            "path": self._adjust_remote_path(path),
            "format": format,
            "language": language.value,
            "overwrite": overwrite
        }

        try:
            url = self._workspace_url('import')
            self._issue_post(url, payload, file=local_path)

        except DatabricksError:
            raise

        except Exception as e:
            raise DatabricksError(
                f'Unable to remove "{workspace_path}" on "{self._host}": {e}'
            )

    def import_dir(self, local_dir: str,
                   workspace_path: str,
                   overwrite: bool = False) -> NoReturn:
        """
        Imports the contents of a local directory to the specified remote
        workspace path.

        :param local_dir:      the path to the local directory
        :param workspace_path: the path to the target folder in the Databricks
                               workspace. If the folder already exists, and
                               there are name clashes in what is being uploaded,
                               and overwrite is False, the import will fail.
                               If the path is relative, and "home" is defined,
                               the path will be created from "home" +
                               "workspace_path". Otherwise, an error will be
                               thrown.
        :param overwrite:      whether or not to overwrite existing files

        :raises DatabricksError: on error. The code field will be set
            to StatusCode.ALREADY_EXISTS if the remote folder exists already.
            It will be set to StatusCode.NOT_FOUND if the local directory
            doesn't exist. It will be set to StatusCode.CONFIG_ERROR if the
            path is relative and "home" isn't set. It'll be set to something
            else otherwise.
        """
        if not os.path.isdir(local_dir):
            raise DatabricksError(
                code=StatusCode.NOT_FOUND,
                message=f'Directory "{local_dir}" does not exist'
            )

        # Much of this code was adapted from the databricks-cli
        # WorkspaceApi.import_workspace_dir() method.
        filenames = os.listdir(local_dir)
        filenames = [f for f in filenames if not f.startswith('.')]

        workspace_path = self._adjust_remote_path(workspace_path)
        self.mkdirs(workspace_path)
        for filename in filenames:
            cur_src = os.path.join(local_dir, filename)
            # Don't use os.path.join() here, since URL paths are always
            # '/', but os.path will use `\` on Windows.
            cur_dst = workspace_path.rstrip('/') + '/' + filename
            if os.path.isdir(cur_src):
                self.import_dir(cur_src, cur_dst, overwrite)

            elif os.path.isfile(cur_src):
                # import file here
                ext = NotebookLanguage.notebook_extension(cur_src)
                if ext == '':
                    # Not a supported file object_type. Skip it.
                    continue

                self.import_notebook(cur_src, cur_dst, overwrite)

    def import_dbc(self, dbc_path: str, workspace_folder: str) -> NoReturn:
        """
        Imports a DBC into a remote folder.

        :param dbc_path:         the path to the (local) DBC
        :param workspace_folder: the path to the (nonexistent) remote folder.
                                 If the path is relative, and "home" is defined,
                                 the path will be created from "home" +
                                 "workspace_path". Otherwise, an error will be
                                 thrown.

        :raises DatabricksError: on error. The code field will be set
            to StatusCode.ALREADY_EXISTS if the remote folder exists already.
            It will be set to StatusCode.NOT_FOUND if the local directory
            doesn't exist. It will be set to StatusCode.CONFIG_ERROR if the
            path is relative and "home" isn't set. It'll be set to something
            else otherwise.
        """

        try:
            url = self._workspace_url('import')
            params = {
                'path': self._adjust_remote_path(workspace_folder),
                'format': 'DBC'
            }
            self._issue_post(url, params, file=dbc_path)

        except DatabricksError:
            raise

        except Exception as e:
            raise DatabricksError(
                f'Unable to import "{dbc_path}" to "{self._host}": {e}'
            )

    def export_dir(self, workspace_path: str, local_dir: str) -> NoReturn:
        """
        Export a remote directory to a local directory.

        :param workspace_path: the remote path. If the path is relative, and
                               "home" is defined, the path will be created from
                               "home" + "workspace_path". Otherwise, an error
                               will be thrown.
        :param local_dir:      the local directory, which may or may not exist.

        :raises DatabricksError: on error. The code field will be set
            to StatusCode.ALREADY_EXISTS if the local directory exists but
            isn't actually a directory. It will be set to StatusCode.NOT_FOUND
            if the remote path doesn't exist. It will be set to
            StatusCode.CONFIG_ERROR if the path is relative and "home" isn't
            set. It'll be set to something else otherwise.
        """

        # This code is adapted from the databricks-cli
        # WorkspaceApi.export_workspace_dir() method.
        if os.path.isfile(local_dir):
            raise DatabricksError(
                code=StatusCode.ALREADY_EXISTS,
                message=f'Local directory {local_dir} exists and is not a '
                        'directory'
            )

        if not os.path.isdir(local_dir):
            os.makedirs(local_dir)

        for obj in self.ls(workspace_path):
            cur_src = obj.path
            cur_dst = os.path.join(local_dir, os.path.basename(obj.path))
            if obj.is_dir():
                self.export_dir(cur_src, cur_dst)
            elif obj.is_notebook():
                cur_dst = cur_dst + obj.language.extension()
                self.export_notebook(cur_src, cur_dst)


    def export_notebook(self, workspace_path: str, local_path: str) -> NoReturn:
        """
        Export a remote Databricks notebook to a local file.

        :param workspace_path: the path to the remote notebook. If the path is
                               relative, and "home" is defined, the path will
                               be created from "home" + "workspace_path".
                               Otherwise, an error will be thrown.
        :param local_path:     the local path

        :raises DatabricksError: on error. The code field will be set
            to StatusCode.ALREADY_EXISTS if the remote folder exists already.
            It will be set to StatusCode.CONFIG_ERROR if the path is relative
            and "home" isn't set.
        """
        url = self._workspace_url('export')
        try:
            params = {
                "path": self._adjust_remote_path(workspace_path),
                "format": "SOURCE"
            }
            resp = self._issue_get(url, params)
            data = resp.json()
            if 'content' not in data:
                raise DatabricksError('No "content" in JSON response.')
            with open(local_path, 'wb') as f:
                f.write(base64.b64decode(data['content']))

        except DatabricksError:
            raise

        except Exception as e:
            raise DatabricksError(
                f'Unable to export "{workspace_path}" on "{self._host}": {e}'
            )

    def export_dbc(self, workspace_path: str, local_path: str):
        """

        :param workspace_path: the remote path. If the path is relative, and
                               "home" is defined, the path will be created from
                               "home" + "workspace_path". Otherwise, an error
                               will be thrown.
        :param local_path:     the local path. If it exists, it'll be
                               overwritten.

        :raises DatabricksError: on error. The code field will be set
            to StatusCode.ALREADY_EXISTS if the local file exists but is
            a directory. It will be set to StatusCode.NOT_FOUND
            if the remote path doesn't exist. It will be set to
            StatusCode.CONFIG_ERROR if the path is relative and "home" isn't
            set. It'll be set to something else otherwise.
        """
        url = self._workspace_url('export')
        try:
            params = {
                "path": self._adjust_remote_path(workspace_path),
                "format": "DBC"
            }
            resp = self._issue_get(url, params)
            data = resp.json()
            if 'content' not in data:
                raise DatabricksError('No "content" in JSON response.')
            with open(local_path, 'wb') as f:
                f.write(base64.b64decode(data['content']))

        except DatabricksError:
            raise

        except Exception as e:
            raise DatabricksError(
                f'Unable to export "{workspace_path}" on "{self._host}": {e}'
            )


    def _adjust_remote_path(self, path: str) -> str:
        if path[0] == '/':
            return path

        if self.home:
            return f'{self.home}/{path}'

        raise DatabricksError(
            code=StatusCode.CONFIG_ERROR,
            message=f'Path "{path}" is relative, but profile "{self.profile} '
                    'has no "home" variable, and "DB_SHARD_HOME" is not set '
                    'in the environment.'
        )


    def _format_for_ext(self, ext: str) -> str:
        return 'JUPYTER' if ext == '.ipynb' else 'SOURCE'

    def _workspace_url(self, endpoint: str) -> str:
        return f'https://{self._host}/{WORKSPACE_PATH}/{endpoint}'

    def _map_type(self, s: str) -> Optional[ObjectType]:
        for o in ObjectType:
            if o.value.upper() == s:
                return o
        return None

    def _map_lang(self, s: str) -> Optional[NotebookLanguage]:
        for l in NotebookLanguage:
            if l.value.upper() == s:
                return l
        return None
