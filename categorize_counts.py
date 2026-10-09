"""Count category hits across corpora to find naturally-bounded slices.

Prints two numbers per category: how many decisions a bare substring match
would pull in, and how many survive label.py's evidence test. The gap is the
precedent-and-enumeration contamination, and it is large enough to matter --
head_start goes from 253 decisions to 221, and the 253 included appeals by
Washington State University and the New York social services department that
have nothing to do with Head Start.

    python categorize_counts.py dab.jsonl alj.jsonl
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import categories
import label


def count_file(path: Path) -> tuple[dict, dict, int]:
    # Missing files used to return all-zero counts, which reads exactly like a
    # category with no hits. Fail loudly instead.
    if not path.exists():
        raise SystemExit(f"{path}: no such file")
    raw = dict.fromkeys(categories.CATEGORIES, 0)
    kept = dict.fromkeys(categories.CATEGORIES, 0)
    total = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            doc = label.Prepared(json.loads(line)["text"])
            for name, cat in categories.CATEGORIES.items():
                if cat.regex.search(doc.text):
                    raw[name] += 1
                if label.label(doc, cat.regex)[0]:
                    kept[name] += 1
    return raw, kept, total


def main() -> int:
    paths = [Path(p) for p in (sys.argv[1:] or ["dab.jsonl", "alj.jsonl"])]
    results = {p: count_file(p) for p in paths}

    width = max(len(n) for n in categories.CATEGORIES)
    header = f"{'category':<{width}}  " + "  ".join(f"{p.stem:>16}" for p in paths)
    print(header)
    print(f"{'':<{width}}  " + "  ".join(f"{'substring / kept':>16}" for p in paths))
    print("-" * len(header))
    for name in categories.CATEGORIES:
        cells = []
        for p in paths:
            raw, kept, _ = results[p]
            cells.append(f"{raw[name]:>7} / {kept[name]:<6}")
        print(f"{name:<{width}}  " + "  ".join(cells))
    print("-" * len(header))
    print(f"{'TOTAL records':<{width}}  "
          + "  ".join(f"{results[p][2]:>16}" for p in paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
