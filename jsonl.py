"""Reading and writing the line-delimited JSON the pipeline passes around.

Five modules had their own copy of "strip the line, skip it if it is blank,
json.loads the rest". The blank-line guard is the whole reason this exists:
without it a trailing newline crashes the reader, which is a silly way to lose
a run that took an hour.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Iterator


def read(path: Path) -> Iterator[dict]:
    """Yield each record. Blank lines are skipped, not fatal."""
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write(path: Path, records: Iterable[dict]) -> int:
    n = 0
    with Path(path).open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def count(path: Path) -> int:
    """Records in a file, counting the same way read() does."""
    with Path(path).open(encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())
