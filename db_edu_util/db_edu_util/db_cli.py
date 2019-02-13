"""
Helper functions for using the Databricks CLI.
"""

from typing import Sequence, Optional, Any
import os
import sys
import re
import json
from io import StringIO
from databricks_cli.configure import provider
from databricks_cli.cli import cli

__all__ = ['databricks', 'DatabricksCliError']

class DatabricksCliError(Exception):
    """
    Thrown to indicate errors with the databricks_cli invocation.
    """
    def __init__(self,          # type: DatabricksCLIError
                 code=None,     # type: Optional[str]
                 message=None   # type: Optional[str]
                ):
        super(Exception, self).__init__(message)
        self.code = code


def _configure_databricks(db_profile):
    # type: (str) -> provider.DatabricksConfig

    config = provider.get_config_for_profile(db_profile)
    # If the profile doesn't exist, environment variables can be used.
    if not config.host:
        config.host = os.environ.get('DATABRICKS_HOST')
    if not config.token:
        config.token = os.environ.get('DATABRICKS_TOKEN')
    if not config.password:
        config.password = os.environ.get('DATABRICKS_PASSWORD')
    if not config.username:
        config.username = os.environ.get('DATABRICKS_USERNAME')

    if not config.host:
        raise DatabricksCliError(
            message='No host for databricks_cli profile "{}"'.format(db_profile)
        )

    if config.token is None:
        if (config.username is None) or (config.password is None):
            raise DatabricksCliError(
                message=('databricks_cli profile "{}" has no API token AND ' +
                         'no username and password').format(db_profile)
            )

    return config


def databricks(args, db_profile=None, capture_stdout=False, verbose=False):
    # type: (Sequence[str], str, bool, bool) -> Optional[str]
    """
    Configure and run the Databricks CLI. Example of use:

    databricks(('workspace', 'ls', '/Users/foo@example.com'), db_profile='DEFAULT')

    :param args:           the "databricks" subcommand and arguments, as a list
                           or tuple
    :param capture_stdout: True to capture and return standard output. False
                           otherwise.
    :param db_profile:     The --profile argument for the "databricks" command,
                           if any; None otherwise.
    :param verbose:        True to emit verbose messages, False otherwise.

    :return: the string containing standard output, if capture_stdout is True.
             None otherwise.
    :raises DatabricksCliError: if the command fails. If possible, the code
            field will be set
    """
    if db_profile is None:
        db_profile = 'DEFAULT'

    #config = _configure_databricks(db_profile)
    kwargs = {
        'standalone_mode': False,
        'prog_name': 'databricks',
    }
    args = ('--profile', db_profile) + tuple(args)

    if verbose:
        print(('+ databricks {0}'.format(' '.join(args))))

    buf = None
    saved_stdout = None
    try:
        import unicodedata
        buf = StringIO()
        saved_stdout = sys.stdout
        sys.stdout = buf
        cli(args, **kwargs)
        output = buf.getvalue()
        if not capture_stdout:
            sys.stdout = saved_stdout
            saved_stdout = None
            print(output)
            output = None

        return output

    except:
        stdout = buf.getvalue()
        json_string = re.sub(r'^Error:\s+', '', stdout)
        default_msg = "Unknown error from databricks_cli"
        try:
            d = json.loads(json_string)
            code = d.get("error_code")
            msg = d.get("message", default_msg)
        except:
            code = None
            msg = stdout
        raise DatabricksCliError(code=code, message=msg)

    finally:
        if saved_stdout:
            sys.stdout = saved_stdout
