import httpx

from cli.settings import PayloadInput


class ServiceError(Exception):
    """The server answered, but not with success."""


def _check(response: httpx.Response):
    if response.is_error:
        request = response.request
        raise ServiceError(
            f"{request.method} {request.url.path} returned "
            f"{response.status_code}: {response.text}"
        )


def create_payload(http: httpx.Client, payload: PayloadInput) -> str:
    response = http.post("/payload", json=payload.model_dump())
    _check(response)
    return response.json()["id"]


def read_payload(http: httpx.Client, id: str) -> str:
    response = http.get(f"/payload/{id}")
    _check(response)
    return response.json()["output"]
