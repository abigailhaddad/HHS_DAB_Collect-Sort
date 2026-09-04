"""Diff a corpus against the Board's own published index.

collect_index.py builds the list of every decision HHS published, per year, from
the archived index pages. This says which of them the corpus actually holds, and
-- more usefully -- where the holes are, because a corpus missing 4% of decisions
evenly is a different object from one missing 70% of a single stretch.

    python audit_completeness.py decisions_index.jsonl out/dab.parquet out/alj.parquet
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

import pyarrow.parquet as pq


def norm(no: str | None) -> str | None:
    """Canonical decision number.

    The index page and the decision itself do not agree on the prefix: a caption
    reads "DAB2740" while the decision's own header reads "Decision No. 2740".
    The CR prefix, by contrast, is present in both and distinguishes the two
    series, so it is kept. Comparing the two raw made every Appellate decision
    look missing.
    """
    if not no:
        return None
    s = re.sub(r"[^A-Za-z0-9]", "", no).upper()
    s = re.sub(r"^(?:DAB|DGAB|GAB|DECISION|NO)+", "", s)
    m = re.match(r"^(CR)?0*(\d+)$", s)
    return f"{m.group(1) or ''}{m.group(2)}" if m else s


def load_index(path: Path) -> dict[str, list[dict]]:
    out = collections.defaultdict(list)
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if line:
            r = json.loads(line)
            out[r["division"]].append(r)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("index", type=Path)
    ap.add_argument("parquets", type=Path, nargs="+")
    ap.add_argument("--missing-out", type=Path, default=Path("missing.jsonl"))
    args = ap.parse_args()

    held = {}
    for p in args.parquets:
        t = pq.read_table(p, columns=["decision_no", "corpus"])
        corpus = t.column("corpus").to_pylist()[0] if t.num_rows else p.stem
        held[corpus] = {norm(x) for x in t.column("decision_no").to_pylist() if x}

    index = load_index(args.index)
    missing_rows = []
    for division, rows in sorted(index.items()):
        have = held.get(division, set())
        by_year = collections.defaultdict(lambda: [0, 0])
        unnumbered = 0
        for r in rows:
            n = norm(r["decision_no"])
            if n is None:
                unnumbered += 1
                continue
            by_year[r["year"]][0] += 1
            if n in have:
                by_year[r["year"]][1] += 1
            else:
                missing_rows.append(r)

        listed = sum(v[0] for v in by_year.values())
        got = sum(v[1] for v in by_year.values())
        print(f"\n{division}: {listed} decisions published, {got} in the corpus "
              f"({got/listed:.0%}), {listed - got} missing"
              + (f", {unnumbered} listed without a parseable number" if unnumbered else ""))
        worst = sorted(by_year.items(), key=lambda kv: (kv[1][1] / kv[1][0]) if kv[1][0] else 1)
        print("  worst years:")
        for year, (n, g) in worst[:10]:
            print(f"    {year}  {g:>4}/{n:<4} ({g/n:>4.0%})")
        print("  complete years:",
              ", ".join(str(y) for y, (n, g) in sorted(by_year.items()) if n and g == n) or "none")

    with args.missing_out.open("w", encoding="utf-8") as f:
        for r in missing_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n{len(missing_rows)} missing decisions, with source URLs -> {args.missing_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
