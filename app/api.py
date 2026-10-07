from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app import db, service
from app.schemas import PayloadCreated, PayloadOutput, PayloadRequest

router = APIRouter()

SessionDep = Annotated[Session, Depends(db.get_session)]


NOT_FOUND = {404: {"description": "Payload not found"}}


# 200, not 201: a payload generated before is returned, not created again
@router.post("/payload", summary="Generate a payload and return its identifier")
def create_payload(request: PayloadRequest, session: SessionDep) -> PayloadCreated:
    payload_id = service.create_payload(session, request.list_1, request.list_2)
    return PayloadCreated(id=payload_id)


@router.get("/payload/{id}", summary="Read a generated payload", responses=NOT_FOUND)
def get_payload(
    session: SessionDep,
    # Not typed as UUID: a malformed id is an unknown payload, not a bad request
    raw_id: Annotated[str, Path(alias="id")],
) -> PayloadOutput:
    try:
        payload_id = UUID(raw_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Payload not found") from None
    output = service.get_payload(session, payload_id)
    if output is None:
        raise HTTPException(status_code=404, detail="Payload not found")
    return PayloadOutput(output=output)
