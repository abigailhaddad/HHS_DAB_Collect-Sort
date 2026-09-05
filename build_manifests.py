"""Describe every category slice: what it is, its legal basis, and its size.

Reads the membership table build_slices.py writes, so the manifest and the
published slices cannot disagree about what is in them. Descriptions and legal
citations come from categories.yaml, so a slice cannot ship with a blank basis.

    python build_manifests.py --dir out/
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq

import categories


def build_manifest(slices: Path, corpus: str) -> dict:
    t = pq.read_table(slices, columns=["corpus", "category"])
    counts: dict[str, int] = {}
    for c, cat in zip(t.column("corpus").to_pylist(), t.column("category").to_pylist()):
        if c == corpus:
            counts[cat] = counts.get(cat, 0) + 1

    unknown = sorted(set(counts) - set(categories.CATEGORIES))
    if unknown:
        raise SystemExit(
            f"{corpus}: slice(s) with no entry in categories.yaml: "
            f"{', '.join(unknown)}. Add them there rather than shipping a slice "
            f"with no description or legal basis.")

    # Every category is listed, including the empty ones. A category that
    # matched nothing is a fact about the corpus; omitting it makes the
    # manifest look like the category was never tried.
    return {
        "corpus": corpus,
        "slice_count": sum(1 for c in categories.CATEGORIES if counts.get(c)),
        "category_count": len(categories.CATEGORIES),
        "slices": [{
            "category": cat.name,
            "description": cat.description,
            "citation": cat.citation,
            "record_count": counts.get(cat.name, 0),
        } for cat in categories.CATEGORIES.values()],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=Path("out"),
                    help="directory holding slices.parquet and the corpora")
    ap.add_argument("--slices", type=Path, default=None)
    args = ap.parse_args()
    slices = args.slices or (args.dir / "slices.parquet")
    if not slices.exists():
        raise SystemExit(f"{slices}: run build_slices.py first")

    t = pq.read_table(slices, columns=["corpus"])
    for corpus in sorted(set(t.column("corpus").to_pylist())):
        manifest = build_manifest(slices, corpus)
        out = args.dir / f"manifest_{corpus}.json"
        out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        print(f"{out.name}: {manifest['slice_count']} non-empty of "
              f"{manifest['category_count']} categories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
