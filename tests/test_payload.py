import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import db
import transformer
from main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        with db.engine.begin() as conn:
            conn.execute(text("TRUNCATE transform_cache, payloads"))
        yield c


@pytest.fixture
def calls(monkeypatch):
    seen = []
    original = transformer.transform

    def counting(s):
        seen.append(s)
        return original(s)

    monkeypatch.setattr(transformer, "transform", counting)
    return seen


def post(client, list_1, list_2):
    return client.post("/payload", json={"list_1": list_1, "list_2": list_2})


def test_interleaves_transformed_strings(client):
    response = post(
        client,
        ["first string", "second string", "third string"],
        ["other string", "another string", "last string"],
    )
    assert response.status_code == 200

    response = client.get(f"/payload/{response.json()['id']}")
    assert response.status_code == 200
    assert response.json() == {
        "output": "FIRST STRING, OTHER STRING, SECOND STRING, "
        "ANOTHER STRING, THIRD STRING, LAST STRING"
    }


def test_duplicates_in_one_request_transformed_once(client, calls):
    post(client, ["a", "a"], ["a", "b"])
    assert sorted(calls) == ["a", "b"]


def test_repeated_payload_reuses_id_and_cache(client, calls):
    first = post(client, ["a", "b"], ["c", "d"]).json()["id"]
    assert len(calls) == 4

    second = post(client, ["a", "b"], ["c", "d"]).json()["id"]
    assert second == first
    assert len(calls) == 4


def test_overlapping_payload_transforms_only_new_strings(client, calls):
    first = post(client, ["a", "b"], ["c", "d"]).json()["id"]
    calls.clear()

    response = post(client, ["a", "x"], ["d", "b"])
    assert calls == ["x"]
    assert response.json()["id"] != first
    assert client.get(f"/payload/{response.json()['id']}").json() == {
        "output": "A, D, X, B"
    }


def test_get_does_not_call_transformer(client, calls):
    id = post(client, ["a"], ["b"]).json()["id"]
    calls.clear()

    assert client.get(f"/payload/{id}").json() == {"output": "A, B"}
    assert calls == []


def test_empty_lists(client, calls):
    response = post(client, [], [])
    assert response.status_code == 200
    assert client.get(f"/payload/{response.json()['id']}").json() == {"output": ""}
    assert calls == []


def test_unequal_lengths_rejected(client):
    assert post(client, ["a", "b"], ["c"]).status_code == 422


def test_unknown_id_returns_404(client):
    assert client.get("/payload/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get("/payload/not-a-uuid").status_code == 404
