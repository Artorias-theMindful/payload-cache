from contextlib import asynccontextmanager
from uuid import NAMESPACE_OID, UUID, uuid5

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, model_validator

import db
import transformer


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    yield
    db.close()


app = FastAPI(lifespan=lifespan)


class PayloadRequest(BaseModel):
    list_1: list[str]
    list_2: list[str]

    @model_validator(mode="after")
    def check_lists(self):
        if len(self.list_1) != len(self.list_2):
            raise ValueError("list_1 and list_2 must have the same length")
        # PostgreSQL text cannot store NUL characters
        if any("\x00" in s for s in self.list_1 + self.list_2):
            raise ValueError("strings must not contain NUL characters")
        return self


def transform_all(strings: list[str]) -> dict[str, str]:
    distinct = list(dict.fromkeys(strings))
    transformed = db.get_cached(distinct)
    missing = {s: transformer.transform(s) for s in distinct if s not in transformed}
    if missing:
        db.store_cached(missing)
    return transformed | missing


@app.post("/payload")
def create_payload(request: PayloadRequest):
    transformed = transform_all(request.list_1 + request.list_2)
    output = ", ".join(
        transformed[s]
        for pair in zip(request.list_1, request.list_2)
        for s in pair
    )
    id = uuid5(NAMESPACE_OID, output)
    db.save_payload(id, output)
    return {"id": id}


@app.get("/payload/{id}")
def get_payload(id: str):
    try:
        payload_id = UUID(id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Payload not found")
    output = db.load_payload(payload_id)
    if output is None:
        raise HTTPException(status_code=404, detail="Payload not found")
    return {"output": output}
