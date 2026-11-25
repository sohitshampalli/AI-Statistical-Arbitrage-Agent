"""Export the API's response models as one JSON Schema document.

The frontend's TypeScript types are generated from this file
(`npm run gen:types` in frontend/). Two drift tests keep the three in step:
a Python test fails if the committed schema differs from the models, and a
frontend test fails if the committed types differ from the schema.

    uv run python -m statarb_agent.api.schema_export          # write the file
    uv run python -m statarb_agent.api.schema_export --check  # exit 1 on drift
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from typing import Final

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from statarb_agent.api import schemas

SCHEMA_PATH: Final = Path("frontend") / "src" / "api" / "schema.json"


def response_models() -> list[type[BaseModel]]:
    """Every model defined in api.schemas, in name order."""
    return sorted(
        (
            obj for _, obj in inspect.getmembers(schemas, inspect.isclass)
            if issubclass(obj, BaseModel) and obj.__module__ == schemas.__name__
            and obj is not schemas.Model
        ),
        key=lambda cls: cls.__name__,
    )


def schema_text() -> str:
    """The schema document as stable, sorted JSON text with a final newline."""
    _, document = models_json_schema(
        [(model, "serialization") for model in response_models()],
        title="statarb-agent dashboard API",
    )
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path.cwd()
    path = root / SCHEMA_PATH
    text = schema_text()
    if "--check" in args:
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            print(f"{SCHEMA_PATH} is out of date; run the export without --check")
            return 1
        print(f"{SCHEMA_PATH} is up to date")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"wrote {SCHEMA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
