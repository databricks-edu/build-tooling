from db_edu_util import squeeze_blank_lines


def test_squeeze_blank_lines():
    s = "abc\n\n\ndef\nghi\n\n\n\n\n"
    assert squeeze_blank_lines(s) == "abc\n\ndef\nghi\n"
    assert squeeze_blank_lines("\n\n\n".join(["a", "b", "c"])) == "a\n\nb\n\nc\n"
    assert squeeze_blank_lines("") == ""
    assert squeeze_blank_lines("\n\n") == "\n"
    assert squeeze_blank_lines("\n\na\n\nb\nc\n") == "a\n\nb\nc\n"
    assert squeeze_blank_lines("\n\na\n\nb\nc") == "a\n\nb\nc\n"
