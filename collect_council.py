"""List the Medicare Appeals Council decisions the Board posts.

The Council is the third component of the DAB and is indexed differently from
the other two: no year pages, just one landing page linking every posted PDF.

What that page is, in its own words, is the thing to keep hold of -- these are
"certain significant decisions and actions ... selected for posting since they
involve the adjudication of issues that may be of interest to various
stakeholders". A curated compendium, not the Council's output. So unlike
collect_index.py, this list cannot be used as a completeness check: it is the
publisher's selection, and there is no published denominator to diff against.

    python collect_council.py --out council_index.jsonl
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

import archive
import jsonl

PAGE = "https://www.hhs.gov/about/agencies/dab/decisions/council-decisions/index.html"
LINK = re.compile(r'href="([^"]*council-decisions/[^"]+\.pdf)"[^>]*>(.*?)</a>',
                  re.IGNORECASE | re.DOTALL)
# "m-11-2450.pdf", "12-1251.pdf" carry a docket; "eagle_air_med.pdf" does not.
DOCKET = re.compile(r"^(?:m[-_])?((?:19|20)?\d{2}[-_]\d{1,4})$", re.IGNORECASE)


def parse(page: str) -> list[dict]:
    out, seen = [], set()
    for href, text in LINK.findall(page):
        url = "https://www.hhs.gov" + href if href.startswith("/") else href
        if url in seen:
            continue
        seen.add(url)
        caption = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(text))).strip()
        stem = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        m = DOCKET.match(stem)
        out.append({
            "division": "council",
            "docket_no": m.group(1).replace("_", "-").upper() if m else None,
            "caption": caption,
            "url": url,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("council_index.jsonl"))
    args = ap.parse_args()

    snap = archive.snapshot_url(PAGE)
    page = archive.get_text(snap) if snap else None
    if not page:
        print("could not read the Council landing page")
        return 1
    rows = parse(page)
    jsonl.write(args.out, rows)
    numbered = sum(1 for r in rows if r["docket_no"])
    print(f"{len(rows)} posted decisions -> {args.out} ({numbered} with a docket "
          f"number in the filename)")
    print("These are a curated selection, not the Council's full output; there is "
          "no published denominator to check completeness against.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
