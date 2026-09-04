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
import urllib.request
from pathlib import Path

BASE = "https://www.hhs.gov/about/agencies/dab/decisions"
DIVISIONS = {"alj": "alj-decisions", "dab": "board-decisions"}
AVAIL = "http://archive.org/wayback/available?url="
CDX = ("http://web.archive.org/cdx/search/cdx?output=json&fl=timestamp"
       "&filter=statuscode:200&limit=-1&url=")
UA = {"User-Agent": "hhs-dab-collector (+https://github.com/KMisener90/HHS_DAB_Collect-Sort)"}

# "2016.08.17 CR4685 Rochelle Gardens Care Center, v. CMS" -> the file beside it.
# Both extensions matter: HHS serves the older decisions as HTML
# (.../board-decisions/1995/dab1550.html) and the newer ones as PDF
# (.../alj-decisions/2016/cr4685.pdf). Matching only .pdf silently returns an
# empty list for every year before the changeover.
LINK = re.compile(
    r'href="([^"]*?/(?:alj|board)-decisions/\d{4}/[^"]+\.(?:pdf|html?))"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL)
# The index page links to itself; those are not decisions.
SELF_LINK = re.compile(r"/index\.html?$", re.IGNORECASE)


def fetch(url: str, timeout: int = 60, tries: int = 4) -> str | None:
    """GET with backoff. The Archive rate-limits, and a single miss reads
    exactly like "this year was never archived" -- which is how 2016 ALJ came
    back empty on one run and full on the next."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception:
            if attempt == tries - 1:
                return None
            time.sleep(2 ** attempt)
    return None


def snapshot_url(page_url: str) -> str | None:
    """Newest archived copy of a page, as raw bytes (the id_ modifier).

    Two sources, because the availability API returns an empty
    "archived_snapshots" object under load rather than an error, which is
    indistinguishable from "never archived" -- 2016 ALJ came back empty on one
    run and full of 260 decisions on the next. CDX is slower and does not lie.
    """
    quoted = urllib.parse.quote(page_url, safe="")
    body = fetch(AVAIL + quoted)
    if body:
        try:
            snap = (json.loads(body).get("archived_snapshots") or {}).get("closest")
        except json.JSONDecodeError:
            snap = None
        if snap:
            # /web/TIMESTAMP/ -> /web/TIMESTAMPid_/ returns the original bytes,
            # not the Archive's page with its own navigation injected.
            return re.sub(r"(/web/\d+)/", r"\1id_/", snap["url"], count=1)

    body = fetch(CDX + quoted)
    if not body or not body.strip():
        return None
    try:
        rows = json.loads(body)
    except json.JSONDecodeError:
        return None
    rows = rows[1:] if rows and rows[0][:1] == ["timestamp"] else rows
    if not rows:
        return None
    return f"http://web.archive.org/web/{rows[-1][0]}id_/{page_url}"


def parse_index(page: str, division: str, year: int) -> list[dict]:
    out, seen = [], set()
    for href, text in LINK.findall(page):
        pdf = urllib.parse.urljoin(f"{BASE}/{DIVISIONS[division]}/{year}/", href)
        if pdf in seen or SELF_LINK.search(pdf):
            continue
        seen.add(pdf)
        caption = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(text))).strip()
        # Captions render the number three ways: "CR4685", "DAB2740" (no "No."),
        # and "Decision No. 1550". Requiring "No." after DAB dropped every
        # Appellate decision on the page.
        m = re.search(r"\b(CR\s?\d{1,5}|DAB\s?(?:No\.?\s?)?\d{1,5}"
                      r"|Decision\s+No\.?\s?\d{1,5}|No\.\s?\d{1,5})\b",
                      caption, re.IGNORECASE)
        out.append({
            "division": division,
            "year": year,
            "decision_no": re.sub(r"[\s.]|No", "", m.group(1), flags=re.I).upper() if m else None,
            "caption": caption,
            "url": pdf,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("decisions_index.jsonl"))
    ap.add_argument("--from-year", type=int, default=1974)
    ap.add_argument("--to-year", type=int, default=2026)
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args()

    rows, missing = [], []
    for division in DIVISIONS:
        for year in range(args.from_year, args.to_year + 1):
            page_url = f"{BASE}/{DIVISIONS[division]}/{year}/index.html"
            snap = snapshot_url(page_url)
            time.sleep(args.delay)
            page = fetch(snap) if snap else None
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
