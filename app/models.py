from uuid import UUID

from sqlalchemy import Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
