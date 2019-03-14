from db_edu_util.databricks import Workspace, StatusCode, DatabricksError
from db_edu_util import strip_margin
from tempfile import TemporaryDirectory
import os
import pytest

@pytest.fixture(scope="module")
def config() -> str:
    with TemporaryDirectory() as dir:
        path = os.path.join(dir, 'dbcfg')
        with open(path, 'w') as f:
            f.write(strip_margin(
                '''|[foo]
                   |host: https://foo.cloud.databricks.com
                   |token: kjhadsfkjhasdflkjhasdf
                   |[bar]
                   |host: https://bar.cloud.databricks.com
                   |token: kjhadsfkjhasdflkjhasdf
                   |home: /Users/someone@example.com
                   |'''
            ))
        yield path


def test_relative_path_no_home(config: str):
    with pytest.raises(DatabricksError) as exc_info:
        if os.environ.get('DB_SHARD_HOME'):
            del os.environ['DB_SHARD_HOME']
        w = Workspace('foo', config)
        w._adjust_remote_path('foo/bar')

    assert exc_info.value.code == StatusCode.CONFIG_ERROR


def test_relative_path_env_home(config: str):
    home = '/Users/foo@example.com'
    os.environ['DB_SHARD_HOME'] = home
    path = 'SomeFolder'
    w = Workspace('foo', config)
    p = w._adjust_remote_path(path)
    assert p == f'{home}/{path}'


def test_relative_path_cfg_home(config: str):
    if os.environ.get('DB_SHARD_HOME'):
        del os.environ['DB_SHARD_HOME']
    path = 'SomeFolder'
    w = Workspace('bar', config)
    p = w._adjust_remote_path(path)
    assert p == f'/Users/someone@example.com/{path}'


def test_relative_path_cfg_and_env_home(config: str):
    home = '/Users/foo@example.com'
    os.environ['DB_SHARD_HOME'] = home
    path = 'SomeFolder'
    w = Workspace('bar', config)
    p = w._adjust_remote_path(path)
    # Environment should be preferred over the config.
    assert p == f'{home}/{path}'
