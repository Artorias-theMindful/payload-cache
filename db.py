import os
from uuid import UUID

from sqlalchemy import Engine, Text, create_engine, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5433/payloads"
)


class Base(DeclarativeBase):
    pass


class TransformCache(Base):
    __tablename__ = "transform_cache"

    input: Mapped[str] = mapped_column(Text, primary_key=True)
    output: Mapped[str] = mapped_column(Text)


class Payload(Base):
    __tablename__ = "payloads"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    output: Mapped[str] = mapped_column(Text)


engine: Engine


def init():
    global engine
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)


def close():
    engine.dispose()


def get_cached(strings: list[str]) -> dict[str, str]:
    with Session(engine) as session:
        rows = session.execute(
            select(TransformCache.input, TransformCache.output).where(
                TransformCache.input.in_(strings)
            )
        ).all()
    return {row.input: row.output for row in rows}


def store_cached(transformed: dict[str, str]):
    with Session(engine) as session, session.begin():
        # A concurrent request may have cached the same string already
        session.execute(
            insert(TransformCache).on_conflict_do_nothing(),
            [{"input": k, "output": v} for k, v in transformed.items()],
        )


def save_payload(id: UUID, output: str):
    with Session(engine) as session, session.begin():
        # The id is derived from the output, so a repeat is the same row
        session.execute(
            insert(Payload).values(id=id, output=output).on_conflict_do_nothing()
        )


def load_payload(id: UUID) -> str | None:
    with Session(engine) as session:
        return session.scalar(select(Payload.output).where(Payload.id == id))
