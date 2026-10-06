from uuid import UUID

from sqlalchemy import String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TransformCache(Base):
    __tablename__ = "transform_cache"

    # SHA-256 of the input: a B-tree index cannot hold arbitrarily long strings
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    input: Mapped[str] = mapped_column(Text)
    output: Mapped[str] = mapped_column(Text)


class Payload(Base):
    __tablename__ = "payloads"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    output: Mapped[str] = mapped_column(Text)
