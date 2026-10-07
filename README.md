# Payload cache

A small FastAPI service that builds "payloads" from two lists of strings and
caches the work, plus `cache-cli`, a command line client for exercising it.

## Description

A payload is built from two lists of strings of the same length:

1. every string goes through a transformer function, which stands in for a
   slow external service (here it upper-cases the string);
2. the transformed strings of the two lists are interleaved and joined with `", "`.

```
list_1: ["first string", "second string", "third string"]
list_2: ["other string", "another string", "last string"]
output: "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
```

The service keeps the number of transformer calls to a minimum:

- each transformed string is stored in PostgreSQL and reused by later requests;
- a string that appears several times in one request is transformed once;
- concurrent requests for the same new string transform it once: the second
  request waits for the first and reuses its result;
- a payload that was generated before gets the same identifier again, because
  the identifier is derived from the output.

| Endpoint | Body | Response |
|---|---|---|
| `POST /payload` | `{"list_1": [...], "list_2": [...]}` | `{"message": "Payload created", "id": "<uuid>"}` |
| `GET /payload/{id}` | | `{"output": "..."}`, or 404 for an unknown id |

Invalid input (lists of different lengths, strings that cannot be stored) is
answered with 422.

The code is split into layers:

| Path | Role |
|---|---|
| `app/api.py` | HTTP endpoints |
| `app/schemas.py` | request and response bodies |
| `app/service.py` | payload logic |
| `app/db.py` | database engine and queries |
| `app/models.py` | database tables |
| `app/transformer.py` | the simulated external service |
| `cli/` | the `cache-cli` command |
| `tests/` | unit and integration tests |

## Prerequisites and dependencies

- Docker with Docker Compose, to run the service and its database
- Python 3.12 or newer (developed on 3.14), for the CLI, the tests and running
  the service outside Docker

Python dependencies are listed in `requirements.txt`:

| Package | Used for |
|---|---|
| `fastapi`, `uvicorn` | the web service |
| `sqlalchemy`, `psycopg` | PostgreSQL access |
| `pydantic-settings` | CLI argument parsing and validation |
| `httpx` | HTTP client of the CLI |

`requirements-dev.txt` adds `pytest`. The database is PostgreSQL 17, started by
Docker Compose.

## Installation

Start the service and the database:

```bash
docker compose up --build -d
```

The service listens on <http://localhost:8000> (interactive API docs at
`/docs`) and PostgreSQL on port 5433. The tables are created on startup.

Install the CLI, and the test dependencies, into a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e . -r requirements-dev.txt
```

This puts the `cache-cli` command on the path.

There are no schema migrations: the tables are created on startup.

## Usage

### API

```bash
curl -X POST http://localhost:8000/payload \
  -H 'content-type: application/json' \
  -d '{"list_1": ["first string", "second string"], "list_2": ["other string", "another string"]}'
# {"message":"Payload created","id":"<uuid>"}

curl http://localhost:8000/payload/<uuid>
# {"output":"FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING"}
```

### CLI

```
cache-cli [-h|--host URL] [-r|--repeat N] [-i|--input FILE|-] [-j|--json JSON] [-o|--output FILE|-] [--help]
```

| Option | Meaning | Default |
|---|---|---|
| `-h`, `--host` | URL of the server | `http://localhost:8000` |
| `-r`, `--repeat` | number of iterations, at least 1 | `1` |
| `-i`, `--input` | file with the request body, `-` for stdin | stdin |
| `-j`, `--json` | the request body as a JSON string, instead of `--input` | |
| `-o`, `--output` | file to write the results to, `-` for stdout | stdout |
| `--help` | show the help text | |

Each iteration creates the payload and reads it back, then writes one JSON
line. Repeating shows the cache at work: every line has the same id.

```bash
cache-cli -r 2 -j '{"list_1": ["a"], "list_2": ["b"]}'
# {"id": "825d7d68-fa4d-50ad-bde6-61e2305462b2", "output": "A, B"}
# {"id": "825d7d68-fa4d-50ad-bde6-61e2305462b2", "output": "A, B"}

cache-cli -h http://localhost:8000 -i body.json -o results.jsonl

echo '{"list_1": ["a"], "list_2": ["b"]}' | cache-cli -i -
```

`-h` is the host option, so help is available as `--help` only. The original
synopsis assigned `-h` to both.

The CLI checks that the body is two lists of strings. Everything else is left
to the server, so the tool can also show how the server rejects bad input.

| Exit code | Meaning |
|---|---|
| 0 | success |
| 1 | the server refused the request or could not be reached |
| 2 | invalid arguments or input |

### Running the service without Docker

Start only the database, then run the service from the virtual environment:

```bash
docker compose up -d db
uvicorn app.main:app --reload
```

`DATABASE_URL` selects the database. It defaults to
`postgresql+psycopg://postgres:postgres@localhost:5433/payloads`, which matches
the Compose file. The URL must use the `postgresql+psycopg://` scheme.

### Tests

The tests need the database from Docker Compose to be running. They create and
use a separate `payloads_test` database, because they empty the tables.

```bash
docker compose up -d db
python -m pytest
```

`TEST_DATABASE_URL` overrides the test database.

Style is checked with ruff:

```bash
ruff check . && ruff format --check .
```

## Design decisions and shortcuts

**The payload id is derived from the output** (`uuid5` of the output string).
A repeated payload gets its old id without a lookup, and two concurrent
requests for the same payload cannot create two rows. Different inputs that
produce the same output share an id, which is correct: the payload is the same.

**`POST /payload` answers 200, not 201**, because a payload generated before is
returned rather than created again.

**The cache table is keyed on a SHA-256 of the input**, since a PostgreSQL index
entry cannot hold an arbitrarily long string. The input is stored next to it
and compared on lookup, so a hash collision is a cache miss, never a wrong hit.

**Concurrent requests are serialised with PostgreSQL advisory locks.** A request
locks the strings it is about to transform, so a second request for the same
string waits and then finds the result cached. The locks are striped (64
stripes) so that a large request does not exhaust the lock table; the price is
that unrelated strings sometimes wait on each other.

Shortcuts, and what a production version would do instead:

- A request keeps its lock and its database connection while the transformer
  runs. That is fine for a function that returns immediately. With a slow
  external service it would tie up the connection pool; the claim on a string
  should then be recorded in its own short transaction and the call made
  outside of it.
- Strings are transformed one after another. A real service would be called in
  batches or concurrently.
- Tables are created with `create_all` on startup. A schema that changes needs
  migrations (Alembic).
- The queries use PostgreSQL features (`ON CONFLICT`, array parameters,
  advisory locks), so SQLite is not supported, although the task allows it.
- Strings containing NUL characters or lone surrogates are rejected with 422,
  because PostgreSQL text cannot store them.
- The CLI truncates the `--output` file before the first request, so a run that
  fails leaves it empty or partial.
- The credentials in `docker-compose.yml` are for local use only.
