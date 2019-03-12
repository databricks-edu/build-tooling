from db_edu_util import all_pred
from string import ascii_lowercase, ascii_uppercase

def test_all_pred():
    assert all_pred(lambda x: x > 0, [10, 20, 30, 40]) == True
    assert all_pred(lambda x: x > 0, [0, 20, 30, 40]) == False
    assert all_pred(lambda x: x > 0, [20, 30, 0, 40]) == False
    assert all_pred(lambda c: c in ascii_uppercase, ascii_uppercase) == True
    assert all_pred(lambda c: c in ascii_uppercase, ascii_lowercase) == False
    assert all_pred(lambda c: c in ascii_uppercase, 'SADLFKJaLKJSDF') == False
