from bdc.bdcutil import bool_field, bool_value
import pytest

def test_bool_value():
    assert bool_value('0') == False
    assert bool_value(100) == True
    assert bool_value(0) == False
    assert bool_value('true') == True
    assert bool_value('TRUE') == True
    assert bool_value('yes') == True
    assert bool_value('YeS') == True
    assert bool_value('YeS') == True
    with pytest.raises(ValueError):
        bool_value('booyah')


def test_bool_field():
    d = {'a': 0, 'b': 10, 'c': 'false', 'd': 'TRUE', 'e': 'No',
         'f': 'yeS', 'g': True, 'h': 'hello'}
    assert bool_field(d, 'a') == False
    assert bool_field(d, 'b') == True
    assert bool_field(d, 'c') == False
    assert bool_field(d, 'd') == True
    assert bool_field(d, 'e') == False
    assert bool_field(d, 'f') == True
    assert bool_field(d, 'g') == True

    with pytest.raises(ValueError):
        bool_field(d, 'h')
