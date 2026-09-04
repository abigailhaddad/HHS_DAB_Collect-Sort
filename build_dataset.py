"""Turn the extracted-text JSONL into a typed, queryable Parquet corpus.

Reads the JSONL that pdf_to_jsonl.py produces, strips the website furniture,
parses the header into filterable columns, and writes one Parquet file per
corpus. Text compresses about 5x under zstd, which is the difference between a
dataset you can range-query over HTTP and 284 MB of line-delimited JSON.

    python build_dataset.py dab.jsonl --corpus dab -o out/
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

import clean
import metadata

SCHEMA = pa.schema([
    ("id", pa.string()),
    ("corpus", pa.string()),
    ("decision_no", pa.string()),
    ("docket_nos", pa.list_(pa.string())),
    ("decision_date", pa.date32()),
    ("year", pa.int16()),
    ("tribunal", pa.string()),
    ("respondent", pa.string()),
    ("num_pages", pa.int32()),
    ("num_chars", pa.int32()),
    ("had_web_chrome", pa.bool_()),
    ("clean_guard_tripped", pa.bool_()),
    ("filename_year_disagrees", pa.bool_()),
    ("text", pa.string()),
])


def build(path: Path, corpus: str) -> pa.Table:
    rows = []
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue                      # tolerate a trailing blank line
        r = json.loads(line)
        raw = r["text"]
        had_chrome = clean.has_chrome(raw)
        text, ok = clean.clean_guarded(raw)
        meta = metadata.parse(raw, r["id"])
        rows.append({
            "id": r["id"],
            "corpus": corpus,
            "decision_no": meta["decision_no"],
            "docket_nos": meta["docket_nos"],
            # date32 wants a date object, not the ISO string metadata returns.
            "decision_date": (date.fromisoformat(meta["decision_date"])
                              if meta["decision_date"] else None),
            "year": meta["year"],
            "tribunal": meta["tribunal"],
            "respondent": meta["respondent"],
            "num_pages": r.get("num_pages"),
            "num_chars": len(text),
            "had_web_chrome": had_chrome,
            "clean_guard_tripped": not ok,
            "filename_year_disagrees": bool(
                meta["decision_date"] and meta["filename_year"]
                and int(meta["decision_date"][:4]) != meta["filename_year"]),
            "text": text,
        })
    cols = {f.name: [row[f.name] for row in rows] for f in SCHEMA}
    return pa.Table.from_pydict(cols, schema=SCHEMA)


def main() -> int:
    ap = argparse.ArgumentParser(description="JSONL -> typed Parquet corpus")
    ap.add_argument("input", type=Path)
    ap.add_argument("--corpus", required=True, choices=["dab", "alj"])
    ap.add_argument("-o", "--out-dir", type=Path, default=Path("out"))
    args = ap.parse_args()

    table = build(args.input, args.corpus)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{args.corpus}.parquet"
    pq.write_table(table, out, compression="zstd", compression_level=9)
    src_mb = args.input.stat().st_size / 1e6
    out_mb = out.stat().st_size / 1e6
    print(f"{out}: {table.num_rows} rows, {out_mb:.1f} MB "
          f"(from {src_mb:.1f} MB JSONL, {src_mb/out_mb:.1f}x smaller)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
