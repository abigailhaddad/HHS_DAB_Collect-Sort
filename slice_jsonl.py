"""Cut a category slice out of a corpus, by evidence rather than by substring.

    python slice_jsonl.py dab.jsonl out/ --category enroll_a3_felony
    python slice_jsonl.py dab.jsonl out/ --all

Categories come from categories.py; there is no --pattern flag any more,
because a pattern typed at the shell has no description, no legal citation and
no name that build_manifests.py can look up. Adding a category means adding it
to categories.py, where all three travel together.

Every slice gets the same columns -- `category` and `match_count`, not a
per-category `{name}_matches` field. Twenty-one slices with twenty-one
different schemas cannot be loaded as one dataset.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import categories
import label


def slice_corpora(records, wanted) -> dict[str, list[dict]]:
    """Cut every requested category in one pass over the records.

    Normalizing the text and scanning it for citations is per-document work, not
    per-category work, and it is the expensive part. Doing it inside a per
    category loop repeated it once for each of the sixteen categories.
    """
    out = {name: [] for name in wanted}
    for rec in records:
        doc = label.Prepared(rec["text"])
        for name in wanted:
            member, ev = label.label(doc, categories.CATEGORIES[name].regex)
            if not member:
                continue
            out[name].append({**rec,
                              "category": name,
                              "match_count": ev["n_matches"],
                              "matches_in_citations": ev["n_in_citation"],
                              "first_match_char": ev["first_match_char"]})
    return out


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:                       # tolerate a trailing blank line
                yield json.loads(line)


def main() -> int:
    ap = argparse.ArgumentParser(description="corpus JSONL -> category slice(s)")
    ap.add_argument("input", type=Path, help="source JSONL (e.g. dab.jsonl)")
    ap.add_argument("out_dir", type=Path, help="directory to write slices into")
    ap.add_argument("--category", action="append", choices=sorted(categories.CATEGORIES),
                    help="category to cut; repeatable")
    ap.add_argument("--all", action="store_true", help="cut every category")
    args = ap.parse_args()

    if not args.all and not args.category:
        ap.error("pass --category NAME (repeatable) or --all")
    names = sorted(categories.CATEGORIES) if args.all else args.category

    records = list(read_jsonl(args.input))
    corpus = args.input.stem
    args.out_dir.mkdir(parents=True, exist_ok=True)
    sliced = slice_corpora(records, names)
    for name in names:
        rows = sliced[name]
        out = args.out_dir / f"{corpus}_{name}.jsonl"
        with out.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{out.name}: {len(rows)}/{len(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
