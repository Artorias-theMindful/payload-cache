import httpx

from cli.settings import PayloadInput


class ServiceError(Exception):
    """The server answered, but not with success."""


def _check(response: httpx.Response):
    if response.is_error:
        request = response.request
        raise ServiceError(
            f"{request.method} {request.url.path} returned {response.status_code}: {response.text}"
        )


def _field(response: httpx.Response, name: str) -> str:
    _check(response)
    # A wrong --host can answer with success and a body that is not ours
    try:
        return response.json()[name]
    except (ValueError, KeyError, TypeError):
        request = response.request
        raise ServiceError(
            f"{request.method} {request.url.path} returned an unexpected body"
        ) from None


def create_payload(http: httpx.Client, payload: PayloadInput) -> str:
    return _field(http.post("/payload", json=payload.model_dump()), "id")


def read_payload(http: httpx.Client, payload_id: str) -> str:
    return _field(http.get(f"/payload/{payload_id}"), "output")
