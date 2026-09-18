"""Warn when the Archive's snapshot of the current year's index has gone stale.

collect_index.py can only ever see what the Archive has crawled. For a year
still being published, that can sit for months between visits -- the 2026
index pages were captured once, in May, and the daily job kept quietly
building a decisions_index.jsonl from that same stale copy for four months
without anything noticing, because a shrinking-or-flat count never *looks*
wrong on its own.

This is a separate, lower-bar signal: not "did the count regress" but "how old
is the page we're even reading". It never fails the run -- the Archive's crawl
schedule is not this collector's bug -- it just puts a loud, dated warning in
front of whoever reads the daily job, in time to run the CDP top-up in
fetch_via_browser.py's sibling, `collect_index.py --cdp`, before the gap
becomes a silent multi-month hole like this one was.

    python check_snapshot_age.py --max-age-days 21
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import urllib.parse

import archive
import collect_index

CDX = ("http://web.archive.org/cdx/search/cdx?output=json&fl=timestamp"
       "&filter=statuscode:200&limit=-1&url=")


def latest_snapshot_age_days(page_url: str, now: dt.datetime) -> int | None:
    """Days since the newest 200 snapshot of page_url, or None if never captured."""
    body = archive.get_text(CDX + urllib.parse.quote(page_url, safe=""))
    if not body or not body.strip():
        return None
    import json
    rows = json.loads(body)
    rows = rows[1:] if rows and rows[0][:1] == ["timestamp"] else rows
    if not rows:
        return None
    latest = max(r[0] for r in rows)
    captured = dt.datetime.strptime(latest[:14], "%Y%m%d%H%M%S")
    return (now - captured).days


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=dt.date.today().year,
                     help="the year whose index pages are still changing")
    ap.add_argument("--max-age-days", type=int, default=21,
                     help="warn once the Archive's snapshot is older than this")
    args = ap.parse_args()

    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    stale = []
    for division, slug in collect_index.DIVISIONS.items():
        page_url = f"{collect_index.BASE}/{slug}/{args.year}/index.html"
        age = latest_snapshot_age_days(page_url, now)
        if age is None:
            msg = f"{division} {args.year}: never captured by the Archive"
            stale.append(msg)
            print(msg)
            continue
        print(f"{division} {args.year}: Archive snapshot is {age} day(s) old")
        if age > args.max_age_days:
            stale.append(f"{division} {args.year}: Archive snapshot is {age} "
                         f"day(s) old (over the {args.max_age_days}-day bar)")

    if stale:
        detail = "; ".join(stale)
        print(f"\n::warning title=Stale Archive snapshot::{detail} -- "
              f"decisions published since then are invisible to the daily "
              f"job. Run `python collect_index.py --cdp http://localhost:9222` "
              f"from a machine with a real, hand-started Chrome to top it up.")
        path = os.environ.get("GITHUB_STEP_SUMMARY")
        if path:
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n## Archive snapshot staleness\n\n"
                        f"{detail}\n\n"
                        "Decisions published since then won't show up until "
                        "someone runs `collect_index.py --cdp` locally.\n")
    # Informational only: the Archive's crawl schedule is not this collector's
    # bug, so this never fails the job the way check_index.py does.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
