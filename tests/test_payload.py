import random
import string
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy.orm import Session

from app import db, service, transformer


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
    assert response.json()["message"] == "Payload created"

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
    payload_id = post(client, ["a"], ["b"]).json()["id"]
    calls.clear()

    assert client.get(f"/payload/{payload_id}").json() == {"output": "A, B"}
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


def test_long_strings_are_cached(client, calls):
    # Longer than a PostgreSQL B-tree index entry can hold, and incompressible
    long = "".join(random.Random(0).choices(string.ascii_lowercase, k=20_000))

    response = post(client, [long], ["b"])
    assert response.status_code == 200
    assert client.get(f"/payload/{response.json()['id']}").json() == {
        "output": f"{long.upper()}, B"
    }

    calls.clear()
    post(client, [long], ["b"])
    assert calls == []


def test_lone_surrogate_rejected(client):
    # Valid JSON, but not encodable as UTF-8, so it cannot be stored
    response = client.post(
        "/payload",
        content=b'{"list_1": ["\\ud800"], "list_2": ["b"]}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422


def test_more_strings_than_bind_parameters(client):
    # A single statement can carry at most 65535 bind parameters
    strings = [str(i) for i in range(70_000)]
    response = post(client, strings, strings)
    assert response.status_code == 200


def test_concurrent_requests_transform_each_string_once(client, monkeypatch):
    seen = []

    def slow(s):
        seen.append(s)
        time.sleep(0.1)  # keep one request in flight while the other arrives
        return s.upper()

    monkeypatch.setattr(transformer, "transform", slow)

    def create(_):
        with Session(db.engine) as session:
            return service.create_payload(session, ["a", "b"], ["c", "d"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(create, range(2))

    assert sorted(seen) == ["a", "b", "c", "d"]
    assert first == second
