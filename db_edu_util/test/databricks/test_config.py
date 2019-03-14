from db_edu_util import databricks
from db_edu_util.databricks import Workspace, StatusCode, DatabricksError
from db_edu_util import strip_margin
from tempfile import TemporaryDirectory
from configparser import ConfigParser
import os
import pytest

def base_config():
    return strip_margin(
        '''|[foo]
           |host: https://foo.cloud.databricks.com
           |token: kjhadsfkjhasdflkjhasdf
           |[bar]
           |host: https://bar.cloud.databricks.com
           |token: kjhadsfkjhasdflkjhasdf
           |home: /Users/someone@example.com
           |[empty]
           |#empty
           |[missing_host]
           |# Missing host
           |token: sdakjhqreiuyhkjasdfjklasdf
           |home: /Users/kjahdsf@example.org
           |[missing_token]
           |# Missing token
           |host: https://toad.cloud.databricks.com
           |home: /Users/hjdsadf@example.org
           |[missing_home]
           |# Missing token
           |token: sadfuiy23894uihjksafdhkjl
           |host: https://home.cloud.databricks.com
           |'''
    )


@pytest.fixture(scope="module")
def config() -> str:
    with TemporaryDirectory() as dir:
        path = os.path.join(dir, 'dbcfg')
        with open(path, 'w') as f:
            f.write(base_config())

        if os.environ.get('DB_SHARD_HOME'):
            del os.environ['DB_SHARD_HOME']
        yield path


@pytest.fixture(scope="module")
def config_with_default() -> str:
    with TemporaryDirectory() as dir:
        path = os.path.join(dir, 'dbcfg2')
        with open(path, 'w') as f:
            default = strip_margin(
                '''|[DEFAULT]
                   |host: https://default.cloud.databricks.com
                   |token: default_token
                   |home: /Users/bmc@example.com
                '''
            )
            print(default + base_config())
            f.write(default + base_config())

        if os.environ.get('DB_SHARD_HOME'):
            del os.environ['DB_SHARD_HOME']
        yield path


def test_missing_host(config):
    with pytest.raises(DatabricksError) as exc_info:
        Workspace('missing_host', config)

    assert exc_info.value.code == StatusCode.CONFIG_ERROR


def test_missing_token(config):
    with pytest.raises(DatabricksError) as exc_info:
        Workspace('missing_token', config)

    assert exc_info.value.code == StatusCode.CONFIG_ERROR


def test_missing_home_and_token(config):
    with pytest.raises(DatabricksError) as exc_info:
        Workspace('empty', config)

    assert exc_info.value.code == StatusCode.CONFIG_ERROR


def test_missing_section(config):
    with pytest.raises(DatabricksError) as exc_info:
        Workspace('nosuchsection', config)

    assert exc_info.value.code == StatusCode.CONFIG_ERROR


def test_has_all_three(config):
    cfg = ConfigParser()
    cfg.read(config)
    section = cfg['bar']

    w = Workspace('bar', config)
    assert w.home == section['home']
    assert w.host == databricks._fix_host(section['host'])
    assert w.token == section['token']


def test_default_with_missing_host(config_with_default):
    cfg = ConfigParser()
    cfg.read(config_with_default)
    default = cfg['DEFAULT']
    section = cfg['missing_host']

    w = Workspace('missing_host', config_with_default)
    assert w.token == section['token']
    assert w.home == section['home']
    assert w.host == databricks._fix_host(default['host'])


def test_default_with_missing_token(config_with_default):
    cfg = ConfigParser()
    cfg.read(config_with_default)
    default = cfg['DEFAULT']
    section = cfg['missing_token']

    w = Workspace('missing_token', config_with_default)
    assert w.token == default['token']
    assert w.home == section['home']
    assert w.host == databricks._fix_host(section['host'])


def test_default_with_missing_home(config_with_default):
    cfg = ConfigParser()
    cfg.read(config_with_default)
    default = cfg['DEFAULT']
    section = cfg['missing_home']

    w = Workspace('missing_home', config_with_default)
    assert w.token == section['token']
    assert w.home == default['home']
    assert w.host == databricks._fix_host(section['host'])


def test_default_with_missing_all(config_with_default):
    cfg = ConfigParser()
    cfg.read(config_with_default)
    default = cfg['DEFAULT']

    w = Workspace('empty', config_with_default)
    assert w.token == default['token']
    assert w.home == default['home']
    assert w.host == databricks._fix_host(default['host'])


def test_default(config_with_default):
    cfg = ConfigParser()
    cfg.read(config_with_default)
    default = cfg['DEFAULT']

    w = Workspace(config=config_with_default)
    assert w.token == default['token']
    assert w.home == default['home']
    assert w.host == databricks._fix_host(default['host'])
