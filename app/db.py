import os
from collections.abc import Iterator
from hashlib import sha256
from uuid import UUID

from sqlalchemy import Engine, String, any_, create_engine, func, literal, select
from sqlalchemy.dialects.postgresql import ARRAY, insert
from sqlalchemy.orm import Session

from app.models import Base, Payload, TransformCache

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5433/payloads"
)

# Advisory lock ids are global to the database; the namespace keeps these
# apart from any other use of advisory locks
LOCK_NAMESPACE = 0x7C4E
LOCK_STRIPES = 64

engine: Engine


def init():
    global engine
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)


def close():
    engine.dispose()


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def _key(string: str) -> str:
    return sha256(string.encode()).hexdigest()


def lock_strings(session: Session, strings: list[str]):
    """Block until no other transaction is transforming any of these strings.

    The locks are released when the transaction ends, so the caller keeps
    them until its results are committed.
    """
    # Striped: one lock per string would exhaust the lock table on a large
    # request. The price is that unrelated strings sometimes share a lock.
    stripes = {int(_key(s)[:8], 16) % LOCK_STRIPES for s in strings}
    # Ascending order, so two requests cannot wait on each other in a cycle
    for stripe in sorted(stripes):
        session.execute(select(func.pg_advisory_xact_lock(LOCK_NAMESPACE, stripe)))


def get_cached(session: Session, strings: list[str]) -> dict[str, str]:
    # One array parameter: IN (...) binds one per string and a statement
    # is limited to 65535 of them
    keys = literal([_key(s) for s in strings], ARRAY(String))
    rows = session.execute(
        select(TransformCache.input, TransformCache.output).where(
            TransformCache.key == any_(keys)
        )
    ).all()
    # Keyed on the stored input, so a hash collision is a miss, not a wrong hit
    return {row.input: row.output for row in rows}


def store_cached(session: Session, transformed: dict[str, str]):
    # A concurrent request may have cached the same string already
    session.execute(
        insert(TransformCache).on_conflict_do_nothing(),
        [{"key": _key(k), "input": k, "output": v} for k, v in transformed.items()],
    )


def save_payload(session: Session, payload_id: UUID, output: str):
    # The id is derived from the output, so a repeat is the same row
    session.execute(
        insert(Payload).values(id=payload_id, output=output).on_conflict_do_nothing()
    )


def load_payload(session: Session, payload_id: UUID) -> str | None:
    return session.scalar(select(Payload.output).where(Payload.id == payload_id))
