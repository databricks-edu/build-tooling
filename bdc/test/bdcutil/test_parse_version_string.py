from bdc.bdcutil import parse_version_string
import pytest

def test_parse_version_string():
    assert parse_version_string("2.0.3") == (2,0)
    assert parse_version_string("2.3") ==  (2,3)

    with pytest.raises(ValueError):
        assert parse_version_string("2")

    with pytest.raises(ValueError):
        parse_version_string("2.4.3.1")

    with pytest.raises(ValueError):
        parse_version_string("abc")

    assert parse_version_string("1.2.3-RC2") == (1,2)
    assert parse_version_string("1.2.4-SNAPSHOT") == (1,2)

