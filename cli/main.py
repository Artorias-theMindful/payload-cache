import json
import sys
from contextlib import contextmanager, nullcontext
from pathlib import Path

import httpx
from pydantic import ValidationError

from cli import client
from cli.settings import STDIO, PayloadInput, Settings, describe, parse_args

EXIT_OK = 0
EXIT_SERVICE = 1  # the server failed, refused the input or could not be reached
EXIT_USAGE = 2  # same code argparse uses for bad arguments


def read_input(settings: Settings) -> PayloadInput:
    if settings.json_input is not None:
        text = settings.json_input
    elif settings.input is None or settings.input == STDIO:
        text = sys.stdin.read()
    else:
        text = settings.input.read_text()
    return PayloadInput.model_validate_json(text)


@contextmanager
def open_output(path: Path):
    if path == STDIO:
        yield sys.stdout
    else:
        with path.open("w") as file:
            yield file


def run(settings: Settings, http: httpx.Client):
    """Create and read back the payload `repeat` times, one JSON line each.

    Repeating the same input is what shows the cache at work: every line
    carries the same id.
    """
    payload = read_input(settings)
    with open_output(settings.output) as out:
        for _ in range(settings.repeat):
            id = client.create_payload(http, payload)
            output = client.read_payload(http, id)
            out.write(json.dumps({"id": id, "output": output}) + "\n")


def main(argv: list[str] | None = None, http: httpx.Client | None = None) -> int:
    """Run the tool and return its exit code.

    `http` lets tests supply a client bound to the application in-process;
    it is left open for the caller to close.
    """
    try:
        settings = parse_args(sys.argv[1:] if argv is None else argv)
        connection = (
            nullcontext(http)
            if http is not None
            else httpx.Client(base_url=str(settings.host), timeout=30)
        )
        with connection as http:
            run(settings, http)
    except ValidationError as error:
        print(f"cache-cli: error: {describe(error)}", file=sys.stderr)
        return EXIT_USAGE
    except OSError as error:
        print(f"cache-cli: error: {error}", file=sys.stderr)
        return EXIT_USAGE
    except (client.ServiceError, httpx.HTTPError) as error:
        print(f"cache-cli: error: {error}", file=sys.stderr)
        return EXIT_SERVICE
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
