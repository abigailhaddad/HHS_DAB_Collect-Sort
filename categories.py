"""Load the category table from categories.yaml.

The table is data, not code: sixteen entries of description, legal citation and
match pattern, which is the part of this repo most likely to be reviewed or
extended by someone who does not write Python. It lives in categories.yaml so
that adding a category is a data edit.

Everything reads the table from here -- the slicer, the counter and the manifest
builder -- so a category cannot exist in one and be missing from another.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

CATEGORIES_FILE = Path(__file__).with_name("categories.yaml")


@dataclass(frozen=True)
class Category:
    name: str
    description: str
    citation: str
    pattern: re.Pattern

    @property
    def regex(self) -> re.Pattern:
        return self.pattern


def load(path: Path = CATEGORIES_FILE) -> dict[str, Category]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = (raw or {}).get("categories") or {}
    if not entries:
        raise SystemExit(f"{path}: no categories defined")

    out: dict[str, Category] = {}
    for name, spec in entries.items():
        missing = [k for k in ("description", "citation", "pattern")
                   if not (spec or {}).get(k)]
        if missing:
            # A blank description used to reach the published manifest as a
            # slice with no stated legal basis. Refuse it at load time instead.
            raise SystemExit(
                f"{path}: category {name!r} is missing {', '.join(missing)}")
        try:
            pattern = re.compile(spec["pattern"], re.IGNORECASE)
        except re.error as e:
            raise SystemExit(f"{path}: category {name!r} has a bad pattern: {e}")
        out[name] = Category(name, spec["description"], spec["citation"], pattern)
    return out


CATEGORIES = load()
