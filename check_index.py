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
import os
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


def summary(now: dict[str, int], baseline: dict[str, int], gained: list[str],
            lost: list[str], unfetched: set[str]) -> None:
    """Write the run's findings where a scheduled job's reader will see them."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    total, was = sum(now.values()), sum(baseline.values())
    lines = ["## Published index", "",
             f"**{total:,} decisions listed** across {len(now)} division-years "
             f"(baseline {was:,}).", ""]
    if gained:
        lines += [f"### {len(gained)} division-year(s) gained decisions", ""]
        lines += [f"- `{g}`" for g in gained] + [""]
    if lost:
        lines += [f"### {len(lost)} division-year(s) LOST decisions", "",
                  "The Board does not unpublish decisions, so this is the "
                  "collector breaking.", ""]
        lines += [f"- `{l}`" for l in lost] + [""]
    if unfetched:
        lines += [f"### {len(unfetched)} division-year(s) not fetched", "",
                  "Not counted either way.", ""]
        lines += [f"- `{u}`" for u in sorted(unfetched)] + [""]
    if not (gained or lost or unfetched):
        lines += ["No change.", ""]
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("index", type=Path)
    ap.add_argument("--baseline", type=Path, default=Path("index_baseline.json"))
    ap.add_argument("--update", action="store_true",
                    help="write the current counts as the new baseline")
    ap.add_argument("--allow-cdp", action="store_true",
                    help="update the baseline even though the index was built "
                         "with --cdp (see the warning this normally raises)")
    args = ap.parse_args()

    now = counts(args.index)
    # Years the collector could not fetch are unknown, not empty. Counting them
    # as zero turns one flaky Archive request into "46 decisions lost".
    meta_path = args.index.with_suffix(".meta.json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    unfetched = set(meta.get("unfetched", []))
    total = sum(now.values())

    if args.update and meta.get("cdp") and not args.allow_cdp:
        # The exact mistake this module's own docstring warns about: a count
        # only a hand-started Chrome can reach becomes the daily target, and
        # the unattended job -- which has no browser to attach to -- fails
        # every single day after, forever, because it can never independently
        # reproduce a number it did not really find. It happened once, the
        # day this flag was added: alj:2026 baselined at 196 from a --cdp run,
        # then the very next scheduled run found the Archive's actual 33 and
        # reported it as 163 decisions lost.
        print("refusing to update the baseline: this index was built with "
              "--cdp, so part of it came from a live browser rather than the "
              "Archive. The unattended daily job can only ever verify the "
              "Archive's copy, so baselining a browser-sourced count fails "
              "every future run against a target it cannot reach. Pass "
              "--allow-cdp if you really mean to do this.", file=sys.stderr)
        return 1

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
        # An annotation shows on the run page; a line of stdout does not, and a
        # green run nobody opens is the same as no run.
        for g in gained:
            print(f"::notice title=New decisions published::{g}")
    if lost:
        print(f"\n{len(lost)} division-year(s) LOST decisions -- the collector is "
              f"probably broken, not the Board:", file=sys.stderr)
        for l in lost:
            print(f"  {l}", file=sys.stderr)
        return 1
    if not gained:
        print("no change")
    summary(now, baseline, gained, lost, unfetched)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
