"""Guard against the collection silently shrinking.

Every failure in this repo's history had the same shape: something stopped
matching, returned nothing, and nothing downstream could tell "no decisions
this year" from "the parser broke". A scheduled collector is the worst place
for that, because it fails quietly for months.

So the index is compared against a committed baseline of counts per division
per year. New decisions are expected and fine. A year that *loses* decisions is
not, and fails the run.

    python check_index.py decisions_index.jsonl --baseline index_baseline.json
    python check_index.py decisions_index.jsonl --baseline index_baseline.json --update

Update the baseline from a plain `collect_index.py` run, the same one CI does.
A baseline built from an index that was hand-merged with anything else -- live
pages fetched through a browser, say -- is a target CI cannot reproduce, and
every run will look like a loss.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import jsonl


def counts(path: Path) -> dict[str, int]:
    """Decisions per "division:year", keyed as strings so JSON round-trips."""
    c: collections.Counter[str] = collections.Counter()
    for r in jsonl.read(path):
        c[f"{r['division']}:{r['year']}"] += 1
    return dict(c)


def compare(baseline: dict[str, int], now: dict[str, int],
            unfetched: set[str] | None = None) -> tuple[list[str], list[str]]:
    unfetched = unfetched or set()
    lost, gained = [], []
    for key, was in sorted(baseline.items()):
        if key in unfetched:      # unknown this run, not lost
            continue
        is_now = now.get(key, 0)
        if is_now < was:
            lost.append(f"{key}: {was} -> {is_now} ({is_now - was})")
    for key, is_now in sorted(now.items()):
        was = baseline.get(key, 0)
        if is_now > was:
            gained.append(f"{key}: {was} -> {is_now} (+{is_now - was})")
    return lost, gained


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("index", type=Path)
    ap.add_argument("--baseline", type=Path, default=Path("index_baseline.json"))
    ap.add_argument("--update", action="store_true",
                    help="write the current counts as the new baseline")
    args = ap.parse_args()

    now = counts(args.index)
    # Years the collector could not fetch are unknown, not empty. Counting them
    # as zero turns one flaky Archive request into "46 decisions lost".
    meta_path = args.index.with_suffix(".meta.json")
    unfetched = set()
    if meta_path.exists():
        unfetched = set(json.loads(meta_path.read_text()).get("unfetched", []))
    total = sum(now.values())

    if args.update or not args.baseline.exists():
        # Merge, never replace. A run with a few flaky fetches would otherwise
        # write zero for those years and quietly disarm the guard on exactly
        # the years most likely to fail again.
        merged = {}
        if args.baseline.exists():
            merged.update(json.loads(args.baseline.read_text(encoding="utf-8")))
        kept = [k for k in merged if k in unfetched]
        merged.update({k: v for k, v in now.items() if k not in unfetched})
        args.baseline.write_text(json.dumps(dict(sorted(merged.items())), indent=2)
                                 + "\n", encoding="utf-8")
        print(f"baseline written: {len(merged)} division-years, "
              f"{sum(merged.values())} decisions")
        if kept:
            print(f"  kept the previous count for {len(kept)} unfetched "
                  f"division-year(s): {', '.join(sorted(kept))}")
        return 0

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    lost, gained = compare(baseline, now, unfetched)

    print(f"{total} decisions listed across {len(now)} division-years "
          f"(baseline {sum(baseline.values())})")
    if unfetched:
        print(f"\n{len(unfetched)} division-year(s) could not be fetched this run "
              f"and are not counted either way: {', '.join(sorted(unfetched))}")
    if gained:
        print(f"\n{len(gained)} division-year(s) gained decisions:")
        for g in gained:
            print(f"  {g}")
    if lost:
        print(f"\n{len(lost)} division-year(s) LOST decisions -- the collector is "
              f"probably broken, not the Board:", file=sys.stderr)
        for l in lost:
            print(f"  {l}", file=sys.stderr)
        return 1
    if not gained:
        print("no change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
