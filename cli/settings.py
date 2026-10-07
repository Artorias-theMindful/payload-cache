from argparse import SUPPRESS, ArgumentParser
from pathlib import Path

from pydantic import (
    AliasChoices,
    AnyHttpUrl,
    BaseModel,
    Field,
    PositiveInt,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, CliSettingsSource, SettingsConfigDict

# "-" as a file argument means stdin or stdout
STDIO = Path("-")

USAGE = (
    "cache-cli [-h|--host URL] [-r|--repeat N] [-i|--input FILE|-] "
    "[-j|--json JSON] [-o|--output FILE|-] [--help]"
)


class PayloadInput(BaseModel):
    """Shape of a request body.

    Only the shape is checked here. Rules such as equal list lengths are the
    server's, so the tool can also show how the server rejects bad input.
    """

    list_1: list[str]
    list_2: list[str]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(cli_hide_none_type=True)

    host: AnyHttpUrl = Field(
        AnyHttpUrl("http://localhost:8000"),
        validation_alias=AliasChoices("host", "h"),
        description="URL of the server",
    )
    repeat: PositiveInt = Field(
        1,
        validation_alias=AliasChoices("repeat", "r"),
        description="number of iterations",
    )
    input: Path | None = Field(
        None,
        validation_alias=AliasChoices("input", "i"),
        description='input file, "-" for stdin (stdin when --json is not given)',
    )
    # A plain string: a model-typed field would be exposed as nested flags
    # (--json.list_1 ...) instead of one JSON argument
    json_input: str | None = Field(
        None,
        validation_alias=AliasChoices("json", "j"),
        description="input as a JSON string instead of a file",
    )
    output: Path = Field(
        STDIO,
        validation_alias=AliasChoices("output", "o"),
        description='output file, "-" for stdout',
    )

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, **other_sources):
        # Command line only. The environment source would also read these
        # options from variables named HOST, INPUT, ..., and shells commonly
        # set HOST.
        return (init_settings,)

    @field_validator("json_input")
    @classmethod
    def check_json(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                PayloadInput.model_validate_json(value)
            except ValidationError as error:
                raise ValueError(describe(error)) from None
        return value

    @model_validator(mode="after")
    def check_single_input(self):
        if self.input is not None and self.json_input is not None:
            raise ValueError("--input and --json cannot be used together")
        return self


def describe(error: ValidationError) -> str:
    """One line per problem, without pydantic's type names and URLs."""
    lines = []
    for problem in error.errors():
        where = ".".join(str(part) for part in problem["loc"])
        lines.append(f"{where}: {problem['msg']}" if where else problem["msg"])
    return "; ".join(lines)


def parse_args(argv: list[str]) -> Settings:
    # argparse reserves -h for help, but here -h is --host. The parser is
    # therefore created without the default help, and --help is added alone.
    parser = ArgumentParser(prog="cache-cli", usage=USAGE, add_help=False)
    parser.add_argument(
        "--help", action="help", default=SUPPRESS, help="show this help message and exit"
    )
    source = CliSettingsSource(Settings, root_parser=parser)
    return Settings(_cli_settings_source=source(args=argv))
