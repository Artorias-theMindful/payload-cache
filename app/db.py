import os
from collections.abc import Iterator
from uuid import UUID

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Base, Payload, TransformCache

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5433/payloads"
)

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


def get_cached(session: Session, strings: list[str]) -> dict[str, str]:
    rows = session.execute(
        select(TransformCache.input, TransformCache.output).where(
            TransformCache.input.in_(strings)
        )
    ).all()
    return {row.input: row.output for row in rows}


def store_cached(session: Session, transformed: dict[str, str]):
    # A concurrent request may have cached the same string already
    session.execute(
        insert(TransformCache).on_conflict_do_nothing(),
        [{"input": k, "output": v} for k, v in transformed.items()],
    )


def save_payload(session: Session, id: UUID, output: str):
    # The id is derived from the output, so a repeat is the same row
    session.execute(
        insert(Payload).values(id=id, output=output).on_conflict_do_nothing()
    )


def load_payload(session: Session, id: UUID) -> str | None:
    return session.scalar(select(Payload.output).where(Payload.id == id))
