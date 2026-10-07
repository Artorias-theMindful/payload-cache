from uuid import UUID

from pydantic import BaseModel, model_validator


def _is_utf8(string: str) -> bool:
    try:
        string.encode()
    except UnicodeEncodeError:
        return False
    return True


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
        # JSON allows lone surrogates ("\ud800"), UTF-8 storage does not
        if not all(s.isascii() or _is_utf8(s) for s in self.list_1 + self.list_2):
            raise ValueError("strings must be valid Unicode text")
        return self


class PayloadCreated(BaseModel):
    message: str = "Payload created"
    id: UUID


class PayloadOutput(BaseModel):
    output: str
