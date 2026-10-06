from uuid import UUID

from pydantic import BaseModel, model_validator


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


class PayloadCreated(BaseModel):
    id: UUID


class PayloadOutput(BaseModel):
    output: str
