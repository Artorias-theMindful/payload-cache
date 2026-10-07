from uuid import NAMESPACE_OID, UUID, uuid5

from sqlalchemy.orm import Session

from app import db, transformer


def transform_all(session: Session, strings: list[str]) -> dict[str, str]:
    distinct = list(dict.fromkeys(strings))
    transformed = db.get_cached(session, distinct)
    missing = [s for s in distinct if s not in transformed]
    if not missing:
        return transformed

    # A concurrent request may be transforming the same strings. Wait for it,
    # then look again: under READ COMMITTED this read sees what it committed.
    # The locks are held until the caller commits, which means this request
    # keeps its database connection while the transformer runs.
    db.lock_strings(session, missing)
    transformed |= db.get_cached(session, missing)
    new = {s: transformer.transform(s) for s in missing if s not in transformed}
    if new:
        db.store_cached(session, new)
    return transformed | new


def interleave(list_1: list[str], list_2: list[str], transformed: dict[str, str]) -> str:
    return ", ".join(transformed[s] for pair in zip(list_1, list_2) for s in pair)


def create_payload(session: Session, list_1: list[str], list_2: list[str]) -> UUID:
    transformed = transform_all(session, list_1 + list_2)
    output = interleave(list_1, list_2, transformed)
    # Deriving the id from the output makes a repeated payload reuse its id
    payload_id = uuid5(NAMESPACE_OID, output)
    db.save_payload(session, payload_id, output)
    session.commit()
    return payload_id


def get_payload(session: Session, payload_id: UUID) -> str | None:
    return db.load_payload(session, payload_id)
