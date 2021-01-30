from bdc.bdcutil import merge_dicts, dict_get_and_del

from typing import Dict, Any


def test_merge_dicts():
    def check(
        expected: Dict[str, Any],
        d1: Dict[str, Any],
        d2: Dict[str, Any],
        *d: Dict[str, Any]
    ):
        assert sorted(merge_dicts(d1, d2, *d).items()) == sorted(expected.items())

    x = {"a": 10, "b": 30, "c": "hello"}
    y = {"d": 40, "b": "Bee", "x": "Ecks"}
    z = {"z": 9.3, "c": "Cee"}
    y_copy = dict(y)
    x_copy = dict(x)

    check({"a": 10, "b": "Bee", "c": "hello", "d": 40, "x": "Ecks"}, x, y)
    check({"a": 10, "b": 30, "c": "hello", "d": 40, "x": "Ecks"}, y, x)
    # The dicts should not have been modified in place.
    assert x == x_copy
    assert y == y_copy

    check({"a": 10, "b": "Bee", "c": "Cee", "d": 40, "x": "Ecks", "z": 9.3}, x, y, z)


def test_dict_get_and_del():
    d = {"a": 10, "b": 20, "c": 30}
    assert dict_get_and_del(d, "a") == 10
    assert sorted(list(d.items())) == [("b", 20), ("c", 30)]
    assert dict_get_and_del(d, "x", -1) == -1
    assert sorted(list(d.items())) == [("b", 20), ("c", 30)]
