from app.service import interleave


def test_interleave_alternates_between_lists():
    transformed = {"a": "A", "b": "B", "c": "C", "d": "D"}
    assert interleave(["a", "b"], ["c", "d"], transformed) == "A, C, B, D"


def test_interleave_repeated_strings():
    assert interleave(["a", "a"], ["a", "b"], {"a": "A", "b": "B"}) == "A, A, A, B"


def test_interleave_empty_lists():
    assert interleave([], [], {}) == ""
