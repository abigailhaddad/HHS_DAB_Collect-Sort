"""Slice membership as one table, rather than a copy of the text per category.

Writing a JSONL per category, each carrying the full decision, stores a decision
in several categories several times over: for this corpus, 263 MB describing
61 MB of decisions. This writes the same information as a membership table --
which decision is in which slice, and the evidence behind it -- at 157 KB, and
it joins to the corpora on (corpus, id).

    python build_slices.py out/dab.parquet out/alj.parquet -o out/slices.parquet
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

import categories
import label

SCHEMA = pa.schema([
    ("corpus", pa.string()),
    ("id", pa.string()),
    ("decision_no", pa.string()),
    ("category", pa.string()),
    ("match_count", pa.int32()),
    ("matches_in_citations", pa.int32()),
    ("first_match_char", pa.int32()),
])


def build(paths: list[Path]) -> pa.Table:
    rows = []
    for path in paths:
        t = pq.read_table(path, columns=["corpus", "id", "decision_no", "text"])
        cols = [t.column(c).to_pylist() for c in ("corpus", "id", "decision_no", "text")]
        for corpus, rid, no, text in zip(*cols):
            # Prepared once per decision: normalising the text and scanning it
            # for citations is per-document work, not per-category work.
            doc = label.Prepared(text)
            for cat in categories.CATEGORIES.values():
                member, ev = label.label(doc, cat.regex)
                if member:
                    rows.append({"corpus": corpus, "id": rid, "decision_no": no,
                                 "category": cat.name,
                                 "match_count": ev["n_matches"],
                                 "matches_in_citations": ev["n_in_citation"],
                                 "first_match_char": ev["first_match_char"]})
    cols = {f.name: [r[f.name] for r in rows] for f in SCHEMA}
    return pa.Table.from_pydict(cols, schema=SCHEMA)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpora", type=Path, nargs="+")
    ap.add_argument("-o", "--out", type=Path, default=Path("out/slices.parquet"))
    args = ap.parse_args()
    table = build(args.corpora)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, args.out, compression="zstd", compression_level=9)
    pairs = len(set(zip(table.column("corpus").to_pylist(),
                        table.column("category").to_pylist())))
    decisions = len(set(zip(table.column("corpus").to_pylist(),
                            table.column("id").to_pylist())))
    print(f"{args.out}: {table.num_rows} memberships, {decisions} decisions, "
          f"{pairs} non-empty slices")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
