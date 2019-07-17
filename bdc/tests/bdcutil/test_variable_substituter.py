from bdc.bdcutil import VariableSubstituterParseError, VariableSubstituter

import pytest

def test_variable_substition():
    template = '$foo $$ ${bar} ${a == "hello" ? "woof" : "x"}'
    v = VariableSubstituter(template)
    assert v.template == template
    assert v.substitute({'foo': 'FOO', 'bar': 'BAR', 'a': 'hello'}) == 'FOO $ BAR woof'
    with pytest.raises(KeyError):
        v.substitute({'foo': 'FOO', 'a': 'hello'})
    assert v.safe_substitute({'foo': 'FOO', 'a': 'hello'}) == 'FOO $  woof'

    with pytest.raises(VariableSubstituterParseError):
        VariableSubstituter('${foo $bar')

    v = VariableSubstituter('${foo} $bar')
    assert v.substitute({'foo': 10, 'bar': 20}) == '10 20'
    assert v.substitute({'foo': '', 'bar': ''}) == ' '

    v = VariableSubstituter('$foo bar ${baz/[a-z]/x/gi}')
    assert v.substitute({'foo': 'Jimmy', 'baz': 'John'}) == 'Jimmy bar xxxx'

    v = VariableSubstituter('$foo bar ${baz/[a-z]\/[a-z]/x\/y/i}')
    assert v.substitute({'foo': 'Jimmy', 'baz': 'b/d/c/e'}) == 'Jimmy bar x/y/c/e'

    v = VariableSubstituter('$foo bar ${baz|[a-z]/[a-z]|x/y|i}')
    assert v.substitute({'foo': 'Jimmy', 'baz': 'b/d/c/e'}) == 'Jimmy bar x/y/c/e'

    with pytest.raises(VariableSubstituterParseError):
        VariableSubstituter('$foo bar ${baz|[a-z]/[a-z]|x/y|igx}')

    with pytest.raises(VariableSubstituterParseError):
        VariableSubstituter('$foo bar ${baz|[a-z]/[a-z]|x/y') # missing last |

    with pytest.raises(VariableSubstituterParseError):
        VariableSubstituter('$foo bar ${baz|[a-z]/[a-z]|x/y|') # no }

    v = VariableSubstituter('$foo bar ${baz|[a-z]/[a-z]|x/y|}') # no flags
    assert v.substitute({'foo': 'Jimmy', 'baz': 'B/d/c/e'}) == 'Jimmy bar B/x/y/e'

    v = VariableSubstituter('${foo|[a-z]+/\d+|FOOBAR|g}')
    assert v.substitute({'foo': 'abcdef/123/999-/vbn/789'}) == 'FOOBAR/999-/FOOBAR'

    v = VariableSubstituter('${file|^(\d+)|$1s|g}')
    assert v.substitute({'file': '01-Why-Spark.py'}) == '01s-Why-Spark.py'

    v = VariableSubstituter('${file|^(\d+)(-.*)$|$1s$2|g}')
    assert v.substitute({'file': '01-Why-Spark.py'}) == '01s-Why-Spark.py'

    with pytest.raises(VariableSubstituterParseError):
        VariableSubstituter('${file|^(\d+)(-.*)$|$1s$2$3|g}')

    v = VariableSubstituter('${file|^(\d+)(-.*)$|$1s$2\$4\$2|}')
    assert v.substitute({'file': '01-Why-Spark.py'}) == '01s-Why-Spark.py$4$2'

    v = VariableSubstituter('${file|abcdef|ZYXWVU|}')
    assert v.substitute({'file': 'abcdef abcdef'}) == 'ZYXWVU abcdef'
    assert v.substitute({'file': 'foobar'}) == 'foobar'

    with pytest.raises(VariableSubstituterParseError):
        VariableSubstituter('${file|^[.*$|x|}')

    v = VariableSubstituter('${file/abc//}')
    assert v.substitute({'file': 'abc123abc'}) == '123abc'

    v = VariableSubstituter('${file/abc//g}')
    assert v.substitute({'file': 'abc123abc'}) == '123'

    v = VariableSubstituter('${file/\d//g}')
    assert v.substitute({'file': 'abc123abc2'}) == 'abcabc'

    v = VariableSubstituter('${file/\d//}')
    assert v.substitute({'file': 'abc123abc2'}) == 'abc23abc2'

    v = VariableSubstituter(r'${file/\.py$//}')
    assert v.substitute({'file': 'Foobar.py'}) == 'Foobar'

    v = VariableSubstituter(r'${foo == "$bar" ? "BAR" : "NOT BAR"}')
    assert v.substitute({"foo": "x", "bar": "y"}) == 'NOT BAR'
    assert v.substitute({"foo": "x", "bar": "x"}) == 'BAR'

    v = VariableSubstituter(r'''${foo == "$bar" ? "It matches $$bar." : "It's $foo, not $bar"}''')
    assert v.substitute({"foo": "hello", "bar": "hello"}) == 'It matches $bar.'
    assert v.substitute({"foo": "hello", "bar": "goodbye"}) == "It's hello, not goodbye"

    v = VariableSubstituter(r'''${x == "abc${foo}def" ? "YES" : "NO"}''')
    assert v.substitute({"foo": "quux", "x": "abcquuxdef"}) == 'YES'
    assert v.substitute({"foo": "quux", "x": "abc---def"}) == 'NO'

    v = VariableSubstituter(r'''${foo == "ab\"" ?  "YES" : "NO"}''')
    print(f"""--- {v.substitute({'foo': 'ab"'})}""")
    assert v.substitute({'foo': 'ab"'}) == 'YES'

    v = VariableSubstituter(r'\"a\"b\"c\"d\"')
    assert v.substitute({}) == '\"a\"b\"c\"d\"'

    v = VariableSubstituter(r'${x == "ab\$c${foo}def" ? "YES" : "NO"}')
    assert v.substitute({"foo": "quux", "x": "abcquuxdef"}) == 'NO'
    assert v.substitute({"foo": "quux", "x": "ab$cquuxdef"}) == 'YES'

    v = VariableSubstituter(r'$foo ${foo} ${foo[0]} ${foo[-1]} ${foo[2:-1]} ${foo[-11:0]}')
    assert v.substitute({'foo': "Boy, howdy"}) == 'Boy, howdy Boy, howdy B y y, howd '

    with pytest.raises(VariableSubstituterParseError):
        VariableSubstituter('${foo[]}')

    v = VariableSubstituter('${foo[:]} $foo ${foo}')
    assert v.substitute({'foo': 'hello'}) == 'hello hello hello'

    v = VariableSubstituter('${foo[2:]}')
    assert v.substitute({'foo': 'hello'}) == 'llo'

    v = VariableSubstituter('${foo[:2]}')
    assert v.substitute({'foo': 'hello'}) == 'he'

    v = VariableSubstituter('${foo[100000]}')
    assert v.substitute({'foo': 'hello'}) == 'o'

    v = VariableSubstituter('${foo[1:100000000]}')
    assert v.substitute({'foo': 'hello'}) == 'ello'

    v = VariableSubstituter('${x[0]}')
    assert v.substitute({'x': ''}) == ''

    v = VariableSubstituter('${x[10000]}')
    assert v.substitute({'x': ''}) == ''

    v = VariableSubstituter(r'${foo == "abc" ? "${bar[0]}" : "${bar[1]}"}')
    assert v.substitute({'foo': 'abc', 'bar': 'WERTYU'}) == 'W'
    assert v.substitute({'foo': 'xxx', 'bar': 'WERTYU'}) == 'E'

    v = VariableSubstituter(r'${file/^\d+/X${bar[2]}/}')
    assert v.substitute({'file': '01-abc', 'bar': "ABC"}) == 'XC-abc'
    assert v.substitute({'file': '01-abc', 'bar': "A"}) == 'XA-abc'

    v = VariableSubstituter(r'${file/^\d+/X${bar[2]}-$baz/}')
    assert v.substitute({'file': '01-abc', 'bar': 'tuvw', 'baz': '!!'}) == 'Xv-!!-abc'

    v = VariableSubstituter(r'${file/^\d+-(.*)$/X${bar[0:2]}-$baz.$1/}')
    assert v.substitute({'file': '01-abc', 'bar': 'tuvw', 'baz': '!!'}) == 'Xtu-!!.abc'


