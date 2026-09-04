"""Build a manifest per corpus describing every category slice on disk.

Descriptions and citations come from categories.py, so a slice can no longer
ship with a blank legal basis because its name was spelled one way in the
slicer and another way in the manifest.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import categories


def count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def build_manifest(root: Path, corpus: str, source_file: str) -> dict:
    source_path = root / source_file
    slices, unknown = [], []
    for path in sorted(root.glob(f"{corpus}_*.jsonl")):
        name = path.stem[len(corpus) + 1:]
        cat = categories.CATEGORIES.get(name)
        if cat is None:
            unknown.append(path.name)
            continue
        slices.append({
            "file": path.name,
            "category": cat.name,
            "description": cat.description,
            "citation": cat.citation,
            "record_count": count_lines(path),
        })
    if unknown:
        raise SystemExit(
            f"{corpus}: slice file(s) with no entry in categories.py: "
            f"{', '.join(unknown)}. Add them there rather than shipping a "
            f"slice with no description or legal basis.")
    return {
        "corpus": corpus,
        "source_file": source_file,
        "source_total_records": count_lines(source_path) if source_path.exists() else None,
        "slice_count": len(slices),
        "slices": slices,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=Path("."),
                    help="directory holding the corpora and slices")
    args = ap.parse_args()
    for corpus in ("dab", "alj"):
        manifest = build_manifest(args.dir, corpus, f"{corpus}.jsonl")
        out = args.dir / f"manifest_{corpus}.json"
        out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        print(f"{out.name}: {manifest['slice_count']} slices")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
