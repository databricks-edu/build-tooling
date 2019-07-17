from bdc.bdcutil import matches_variable_ref, variable_ref_patterns

def test_matches_variable_ref():
    data = [
        ('foo', '$foo', ('', '$foo', '')),
        ('hello', 'This is ${hello} a', ('This is ', '${hello}', ' a')),
        ('foobar', 'abc $bar cdef.', None),
        ('nb', '$foo bar ${nb == "abc" ? "one" : "two"}',
         ('$foo bar ', '${nb == "abc" ? "one" : "two"}', '')),
        ('nb', '$foo bar ${nb=="abc"?"one":"two"}',
         ('$foo bar ', '${nb=="abc"?"one":"two"}', '')),
    ]

    for pat, string, expected in data:
        assert matches_variable_ref(variable_ref_patterns(pat), string) == expected
