from bdc.bdcutil import flatten

from typing import Sequence, Any

def test_flatten():

    data = [
        (['foobar', range(1, 3), ['a', 'b', range(4, 6)], 'xyz'],
         ['foobar', 1, 2, 'a', 'b', 4, 5, 'xyz']),

        ([(1, 2, (3, 4), 5), [6, 7, [[8, 9]], 10]],
         [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),

        ([(1, 2, (3, 4), 5), [6, 7, [[8, 9]], 10], range(11, 20)],
         [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]),
    ]

    for input, expected in data:
        assert list(flatten(input)) == list(expected)


