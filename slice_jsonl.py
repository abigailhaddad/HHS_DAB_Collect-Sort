#!/usr/bin/env python3
r"""Filter a full JSONL dataset down to a category slice by regex match on
the record's normalized text. Reuses text already extracted by
pdf_to_jsonl.py, so no PDFs are re-parsed.

Usage:
    python slice_jsonl.py IN.jsonl OUT.jsonl --name enroll_a3_felony \
        --pattern '424\.535\s*\(\s*a\s*\)\s*\(\s*3\s*\)'
"""
import argparse
import json
import re


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="source JSONL (e.g. dab.jsonl)")
    ap.add_argument("output", help="slice JSONL to write")
    ap.add_argument("--name", required=True, help="category name, used as the record field prefix")
    ap.add_argument("--pattern", required=True, help="regex tested against normalized text")
    args = ap.parse_args()

    rx = re.compile(args.pattern, re.IGNORECASE)
    total = matched = 0
    with open(args.input, encoding="utf-8") as fin, \
         open(args.output, "w", encoding="utf-8") as fout:
        for line in fin:
            rec = json.loads(line)
            total += 1
            n = len(rx.findall(norm(rec["text"])))
            if n > 0:
                rec["category"] = args.name
                rec[f"{args.name}_matches"] = n
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                matched += 1

    print(f"{matched}/{total} records matched '{args.name}' -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
