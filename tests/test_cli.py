import io
import json

from cli.main import main

SAMPLE = json.dumps(
    {
        "list_1": ["first string", "second string", "third string"],
        "list_2": ["other string", "another string", "last string"],
    }
)
SAMPLE_OUTPUT = (
    "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
)


def lines(text):
    return [json.loads(line) for line in text.splitlines()]


def test_repeat_writes_one_line_per_iteration_with_same_id(client, capsys):
    assert main(["--json", SAMPLE, "--repeat", "3"], http=client) == 0

    results = lines(capsys.readouterr().out)
    assert len(results) == 3
    assert {r["output"] for r in results} == {SAMPLE_OUTPUT}
    assert len({r["id"] for r in results}) == 1


def test_input_and_output_files(client, tmp_path, capsys):
    source = tmp_path / "in.json"
    target = tmp_path / "out.jsonl"
    source.write_text(SAMPLE)

    assert main(["-i", str(source), "-o", str(target)], http=client) == 0

    assert [r["output"] for r in lines(target.read_text())] == [SAMPLE_OUTPUT]
    assert capsys.readouterr().out == ""


def test_input_from_stdin(client, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(SAMPLE))
    assert main(["--input", "-"], http=client) == 0
    assert lines(capsys.readouterr().out)[0]["output"] == SAMPLE_OUTPUT


def test_stdin_is_the_default_input(client, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(SAMPLE))
    assert main([], http=client) == 0
    assert lines(capsys.readouterr().out)[0]["output"] == SAMPLE_OUTPUT


def test_server_rejection_exits_1(client, capsys):
    unequal = '{"list_1": ["a", "b"], "list_2": ["c"]}'
    assert main(["--json", unequal], http=client) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "422" in captured.err
    assert "same length" in captured.err


def test_unencodable_input_exits_2(client, capsys):
    # A lone surrogate is refused by the JSON parser before anything is sent
    assert main(["--json", '{"list_1": ["\\ud800"], "list_2": ["b"]}'], http=client) == 2
    assert "Invalid JSON" in capsys.readouterr().err


def test_unreachable_host_exits_1(capsys):
    assert main(["--host", "http://127.0.0.1:1", "--json", SAMPLE]) == 1
    assert capsys.readouterr().err.startswith("cache-cli: error:")


def test_invalid_argument_exits_2(client, capsys):
    assert main(["--repeat", "0", "--json", SAMPLE], http=client) == 2
    assert "repeat" in capsys.readouterr().err


def test_missing_input_file_exits_2(client, tmp_path, capsys):
    assert main(["--input", str(tmp_path / "absent.json")], http=client) == 2
    assert "absent.json" in capsys.readouterr().err


def test_malformed_input_file_exits_2(client, tmp_path, capsys):
    source = tmp_path / "in.json"
    source.write_text("{not json")
    assert main(["--input", str(source)], http=client) == 2
    assert "Invalid JSON" in capsys.readouterr().err
