from bdc.bdcutil import find_in_path, joinpath
import os
import pytest

def test_find_in_path():
    assert os.path.basename(find_in_path('python')) == 'python'
    with pytest.raises(Exception):
        assert find_in_path('daslkas43-dlk')


def test_join_path():
    if os.name == 'posix':
        assert joinpath('a///', 'b/') == 'a/b'
    else:
        assert True
