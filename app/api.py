from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import db, service
from app.schemas import PayloadCreated, PayloadOutput, PayloadRequest

router = APIRouter()

SessionDep = Annotated[Session, Depends(db.get_session)]


@router.post("/payload")
def create_payload(request: PayloadRequest, session: SessionDep) -> PayloadCreated:
    id = service.create_payload(session, request.list_1, request.list_2)
    return PayloadCreated(id=id)


@router.get("/payload/{id}")
def get_payload(id: str, session: SessionDep) -> PayloadOutput:
    try:
        payload_id = UUID(id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Payload not found")
    output = service.get_payload(session, payload_id)
    if output is None:
        raise HTTPException(status_code=404, detail="Payload not found")
    return PayloadOutput(output=output)
