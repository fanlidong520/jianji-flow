from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict:
    with (SCHEMA_DIR / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate(schema_name: str, data: dict) -> None:
    Draft202012Validator(load_schema(schema_name)).validate(data)


def validate_manifest(data: dict) -> None:
    _validate("manifest.schema.json", data)


def validate_recipe(data: dict) -> None:
    _validate("recipe.schema.json", data)


def validate_matches(data: dict) -> None:
    _validate("matches.schema.json", data)


def validate_fixes(data: dict) -> None:
    _validate("fixes.schema.json", data)


def validate_visual_selection(data: dict) -> None:
    _validate("visual-selection.schema.json", data)
