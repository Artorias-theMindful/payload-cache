from uuid import NAMESPACE_OID, UUID, uuid5

from sqlalchemy.orm import Session

from app import db, transformer


def transform_all(session: Session, strings: list[str]) -> dict[str, str]:
    distinct = list(dict.fromkeys(strings))
    transformed = db.get_cached(session, distinct)
    missing = {s: transformer.transform(s) for s in distinct if s not in transformed}
    if missing:
        db.store_cached(session, missing)
    return transformed | missing


def interleave(list_1: list[str], list_2: list[str], transformed: dict[str, str]) -> str:
    return ", ".join(transformed[s] for pair in zip(list_1, list_2) for s in pair)


def create_payload(session: Session, list_1: list[str], list_2: list[str]) -> UUID:
    transformed = transform_all(session, list_1 + list_2)
    output = interleave(list_1, list_2, transformed)
    # Deriving the id from the output makes a repeated payload reuse its id
    id = uuid5(NAMESPACE_OID, output)
    db.save_payload(session, id, output)
    session.commit()
    return id


def get_payload(session: Session, id: UUID) -> str | None:
    return db.load_payload(session, id)
