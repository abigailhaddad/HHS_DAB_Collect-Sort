"""Build the authoritative list of published decisions from archived index pages.

dab.hhs.gov sits behind an Akamai edge block that returns 403 to everything --
the year index pages, the decision PDFs, even robots.txt -- regardless of user
agent. The Internet Archive has both, so collection goes through there.

Each per-year index page lists every decision the Board published that year with
a direct link to its PDF, which is what makes a completeness check possible at
all: the corpus can be diffed against the publisher's own list rather than
against a guess about which decision numbers ought to exist.

    python collect_index.py --out decisions_index.jsonl
"""
from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.parse

import archive
from pathlib import Path

BASE = "https://www.hhs.gov/about/agencies/dab/decisions"
DIVISIONS = {"alj": "alj-decisions", "dab": "board-decisions"}
# First year each division published. Probing outside these costs two failed
# lookups per year and returns nothing: the Civil Remedies Division did not
# exist before 1981, and asking the Archive for its 1974 index just burns the
# retry budget.
FIRST_YEAR = {"alj": 1981, "dab": 1974}

# Decisions are linked three different ways depending on when they were
# published, and a parser that knows only one returns an empty list for the
# other two -- which looks exactly like a year with no decisions:
#
#   to ~1999   .../static/dab/decisions/board-decisions/1995/dab1550.html
#   ~2000-2016 .../static/dab/decisions/alj-decisions/2016/cr4685.pdf
#   2017 on    .../decisions/board-decisions/2020/board-dab-3027/index.html
#              .../decisions/alj-decisions/2020/alj-cr5791/index.html
#
# The last era gives each decision its own page, so the filename is "index.html"
# and only the directory identifies it.
LINK = re.compile(
    r'href="([^"]*?/(?:alj|board)-decisions/\d{4}/'
    r'(?:[^"/]+\.(?:pdf|html?)|[^"/]+/index\.html?))"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL)
# The year page links to itself. Matching any /index.html would also throw away
# every decision published from 2017 on.
SELF_LINK = re.compile(r"/(?:alj|board)-decisions/\d{4}/index\.html?$", re.IGNORECASE)


def parse_index(page: str, division: str, year: int) -> list[dict]:
    out, seen = [], set()
    for href, text in LINK.findall(page):
        url = urllib.parse.urljoin(f"{BASE}/{DIVISIONS[division]}/{year}/", href)
        if url in seen or SELF_LINK.search(url):
            continue
        seen.add(url)
        caption = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(text))).strip()
        # Captions render the number three ways: "CR4685", "DAB2740" (no "No."),
        # and "Decision No. 1550". Requiring "No." after DAB dropped every
        # Appellate decision on the page.
        # ALJ Rulings first. Their captions read "ALJ Ruling No. 2014-17", and
        # the generic "No. NNNN" branch reads that as decision number 2014 --
        # so all 23 rulings of a year collapsed onto one identifier.
        m = re.search(r"\bALJ\s+Ruling\s+No\.?\s*(\d{4}-\d{1,3})\b",
                      caption, re.IGNORECASE)
        if m:
            return_no = "RULING" + m.group(1)
        else:
            m = re.search(r"\b(CR\s?\d{1,5}|DAB\s?(?:No\.?\s?)?\d{1,5}"
                          r"|Decision\s+No\.?\s?\d{1,5}|No\.\s?\d{1,5})\b",
                          caption, re.IGNORECASE)
            return_no = None
            if not m:   # fall back to the slug: "board-dab-3027", "alj-cr5791"
                m = re.search(r"/(?:board|alj)-((?:dab|cr)-?\d{1,5})/", url,
                              re.IGNORECASE)
            if m:
                return_no = re.sub(r"[\s.\-]|No", "", m.group(1),
                                   flags=re.I).upper()
            # A bare four-digit number in a caption is a year, not a decision.
            if return_no and re.fullmatch(r"(?:19|20)\d\d", return_no):
                return_no = None
        out.append({
            "division": division,
            "year": year,
            "decision_no": return_no,
            "caption": caption,
            "url": url,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("decisions_index.jsonl"))
    ap.add_argument("--from-year", type=int, default=None,
                    help="override the per-division first year")
    ap.add_argument("--to-year", type=int, default=2026)
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args()

    rows, missing = [], []
    for division in DIVISIONS:
        start = args.from_year or FIRST_YEAR[division]
        for year in range(start, args.to_year + 1):
            page_url = f"{BASE}/{DIVISIONS[division]}/{year}/index.html"
            snap = archive.snapshot_url(page_url)
            time.sleep(args.delay)
            page = archive.get_text(snap) if snap else None
            if not page:
                missing.append(f"{division} {year}")
                continue
            found = parse_index(page, division, year)
            rows.extend(found)
            print(f"{division} {year}: {len(found)}", flush=True)
            time.sleep(args.delay)

    with args.out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n{len(rows)} decisions listed -> {args.out}")
    if missing:
        print(f"no archived index for: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
