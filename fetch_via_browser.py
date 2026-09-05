"""Fetch decisions through a Chrome you started yourself, over the DevTools protocol.

www.hhs.gov returns 403 to automated clients -- every path, any user agent,
including robots.txt -- so the Internet Archive is the normal route (see
fetch_missing.py). It has a ceiling: the Archive's most recent crawl of a page
may be months old, and Save Page Now now requires an account. Anything the
Board published since that crawl is reachable only from a real browser.

Attaching out-of-process is what makes this work. The automation lives outside
the page, so there is no in-page automation fingerprint to detect; launching a
browser from code is not the same thing and does not behave the same way.

    # in one terminal, started by hand:
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \\
        --remote-debugging-port=9222 --user-data-dir="$HOME/chrome-debug"

    python fetch_via_browser.py missing_2026.jsonl --out-dir decisions/

One scraping process per browser. Two jobs against the same Chrome fight over
tabs and produce interleaved or truncated results.
"""
from __future__ import annotations

import argparse
import random
import re
import time
from pathlib import Path

import json

import jsonl

# A block page returns HTTP 200 through a browser just as happily as anything
# else, so status is not the test; content is.
BLOCKED = re.compile(r"Access Denied|just a moment|verifying you are human|"
                     r"cloudflare ray id|<title>\s*403", re.I)
# A real decision page carries the Board's letterhead. Without this check a
# redirect to the section landing page saves cleanly and counts as done.
LOOKS_LIKE_DECISION = re.compile(
    r"DEPARTMENTAL APPEALS BOARD|Civil Remedies Division|Appellate Division", re.I)
MIN_BYTES = 5000


def out_name(rec: dict) -> str:
    # Strip the query string before anything else. The 2017-18 URLs end
    # "...alj-cr5002.pdf?language=en", and Path().suffix on that is
    # ".pdf?language=en" -- so the file saved with an extension no suffix
    # filter matches, and extract.py skipped 232 of them without a word.
    tail = rec["url"].rstrip("/").split("/")[-1].split("?", 1)[0].split("#", 1)[0]
    if tail.lower().startswith("index."):
        tail = rec["url"].rstrip("/").split("/")[-2] + ".html"
    ext = Path(tail).suffix.lower() or ".html"
    return f"{rec['year']}_{Path(tail).stem}{ext}"


def is_good(html: str) -> tuple[bool, str]:
    if not html or len(html) < MIN_BYTES:
        return False, f"too small ({len(html)} bytes)"
    if BLOCKED.search(html[:4000]):
        return False, "block page"
    if not LOOKS_LIKE_DECISION.search(html):
        return False, "not a decision page"
    return True, ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("records", type=Path, help="JSONL with url/year fields")
    ap.add_argument("--out-dir", type=Path, default=Path("decisions"))
    ap.add_argument("--cdp", default="http://localhost:9222")
    ap.add_argument("--delay", type=float, default=1.5)
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    records = list(jsonl.read(args.records))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    failures = args.out_dir / "_browser_failures.jsonl"
    got = skipped = failed = 0

    with sync_playwright() as pw, failures.open("a", encoding="utf-8") as flog:
        browser = pw.chromium.connect_over_cdp(args.cdp)
        if not browser.contexts:
            print("no browser context; is Chrome running with "
                  "--remote-debugging-port?")
            return 1
        page = browser.contexts[0].new_page()
        try:
            for i, rec in enumerate(records, 1):
                dest = args.out_dir / out_name(rec)
                if dest.exists() and dest.stat().st_size > MIN_BYTES:
                    skipped += 1
                    continue
                try:
                    page.goto(rec["url"], wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(800)
                    html = page.content()
                except Exception as e:
                    html, why = "", str(e)[:120]
                else:
                    ok, why = is_good(html)
                    if ok:
                        dest.write_text(html, encoding="utf-8")
                        got += 1
                    else:
                        html = ""
                if not html:
                    failed += 1
                    flog.write(json.dumps({**rec, "error": why}) + "\n")
                    flog.flush()
                if i % 20 == 0:
                    print(f"  {i}/{len(records)}  got {got}  skipped {skipped} "
                          f"failed {failed}", flush=True)
                time.sleep(args.delay * random.uniform(0.7, 1.4))
        finally:
            page.close()

    print(f"\n{got} fetched, {skipped} already present, {failed} failed "
          f"-> {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
