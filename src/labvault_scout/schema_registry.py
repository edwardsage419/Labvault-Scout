from __future__ import annotations

from importlib.resources import files

SCHEMA_FILES = {
    "scan": "scan-1.schema.json",
    "comparison": "comparison-1.schema.json",
    "verification": "verification-1.schema.json",
}


def load_schema_text(kind: str) -> str:
    """Load a packaged JSON Schema as UTF-8 text."""
    try:
        filename = SCHEMA_FILES[kind]
    except KeyError as exc:
        raise ValueError(f"Unknown schema kind: {kind}") from exc
    return files("labvault_scout").joinpath("schemas", filename).read_text(encoding="utf-8")
