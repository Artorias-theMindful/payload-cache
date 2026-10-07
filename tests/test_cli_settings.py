from pathlib import Path

import pytest
from pydantic import ValidationError

from cli.settings import parse_args

BODY = '{"list_1": ["a"], "list_2": ["b"]}'


def test_defaults():
    settings = parse_args([])
    assert str(settings.host) == "http://localhost:8000/"
    assert settings.repeat == 1
    assert settings.input is None
    assert settings.json_input is None
    assert settings.output == Path("-")


def test_short_flags():
    settings = parse_args(
        ["-h", "http://example.com:9000", "-r", "3", "-i", "in.json", "-o", "out.jsonl"]
    )
    assert str(settings.host) == "http://example.com:9000/"
    assert settings.repeat == 3
    assert settings.input == Path("in.json")
    assert settings.output == Path("out.jsonl")


def test_long_flags():
    settings = parse_args(
        ["--host", "https://example.com", "--repeat", "2", "--json", BODY, "--output", "-"]
    )
    assert str(settings.host) == "https://example.com/"
    assert settings.repeat == 2
    assert settings.json_input == BODY
    assert settings.output == Path("-")


def test_short_json_flag():
    assert parse_args(["-j", BODY]).json_input == BODY


def test_help_is_long_form_only(capsys):
    with pytest.raises(SystemExit) as stopped:
        parse_args(["--help"])
    assert stopped.value.code == 0
    assert "--host" in capsys.readouterr().out

    # -h is the host flag, so on its own it is missing its value
    with pytest.raises(SystemExit) as stopped:
        parse_args(["-h"])
    assert stopped.value.code == 2


def test_environment_is_ignored(monkeypatch):
    monkeypatch.setenv("HOST", "my-laptop")
    assert str(parse_args([]).host) == "http://localhost:8000/"


@pytest.mark.parametrize(
    "argv",
    [
        ["--host", "ftp://example.com"],
        ["--host", "not a url"],
        ["--repeat", "0"],
        ["--repeat", "-1"],
        ["--repeat", "many"],
        ["--json", "{not json"],
        ["--json", '{"list_1": "a", "list_2": ["b"]}'],
        ["--json", '{"list_1": ["a"]}'],
        ["--json", BODY, "--input", "in.json"],
    ],
)
def test_invalid_arguments_rejected(argv):
    with pytest.raises(ValidationError):
        parse_args(argv)


def test_unknown_flag_rejected():
    with pytest.raises(SystemExit) as stopped:
        parse_args(["--bogus"])
    assert stopped.value.code == 2
