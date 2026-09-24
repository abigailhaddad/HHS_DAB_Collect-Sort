"""Build the authoritative list of published decisions from archived index pages.

dab.hhs.gov sits behind an Akamai edge block that returns 403 to everything --
the year index pages, the decision PDFs, even robots.txt -- regardless of user
agent. The Internet Archive has both, so collection goes through there.

Each per-year index page lists every decision the Board published that year with
a direct link to its PDF, which is what makes a completeness check possible at
all: the corpus can be diffed against the publisher's own list rather than
against a guess about which decision numbers ought to exist.

    python collect_index.py --out decisions_index.jsonl

The Archive's crawl of a year still in progress can sit for months between
visits -- the 2026 index pages were captured once, in May, and nothing since.
That's invisible to the loss check above because it never reads as zero: 33
decisions is a perfectly plausible-looking answer for a year that has actually
published 196. --cdp (attach to a Chrome you started by hand) or
--launch-browser (a throwaway one, headless=False, for CI) tops up the
current year(s) live instead of trusting that stale snapshot.

    python collect_index.py --out decisions_index.jsonl --cdp http://localhost:9222
    python collect_index.py --out decisions_index.jsonl --launch-browser

--launch-browser works unattended -- confirmed against hhs.gov itself, same
as the dod repo's scrape.py already runs daily against war.gov -- because
Akamai's block here keys off headless indicators, not the deeper page-level
fingerprinting Cloudflare's challenge does; a real Chrome (headless=False,
just running under Xvfb in CI with no display of its own) reads the same as
one a person is sitting in front of. --cdp remains for interactive local use.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.parse

import archive
import jsonl
import metadata
from fetch_via_browser import BLOCKED
from pathlib import Path

BASE = "https://www.hhs.gov/about/agencies/dab/decisions"
DIVISIONS = {"alj": "alj-decisions", "dab": "board-decisions"}
# First year each division published. Probing outside these costs two failed
# lookups per year and returns nothing: the Civil Remedies Division did not
# exist before 1981, and asking the Archive for its 1974 index just burns the
# retry budget.
# The Civil Remedies Division's first decision is CR1, 1985. Probing 1981-84
# cost two failed lookups a year and put four permanent entries in the
# "could not fetch" list, where they read like a collection problem.
FIRST_YEAR = {"alj": 1985, "dab": 1974}

# Decisions are linked three different ways depending on when they were
# published, and a parser that knows only one returns an empty list for the
# other two -- which looks exactly like a year with no decisions:
#
#   to ~1999   .../static/dab/decisions/board-decisions/1995/dab1550.html
#   ~2000-2016 .../static/dab/decisions/alj-decisions/2016/cr4685.pdf
#   2017-2018  /sites/default/files/alj-cr5002.pdf?language=en
#   2019 on    .../decisions/board-decisions/2020/board-dab-3027/index.html
#              .../decisions/alj-decisions/2020/alj-cr5791/index.html
#
# The 2017-18 form has no year in the path and no "-decisions/" segment at all,
# so a pattern anchored on those matched nothing and three years -- dab 2017,
# dab 2018, alj 2017, some 500 decisions -- were invisible to the index while
# their pages fetched perfectly well. A year that parses to zero is the thing
# this collector is least able to notice about itself.
#
# The last era gives each decision its own page, so the filename is "index.html"
# and only the directory identifies it.
LINK = re.compile(
    r'href="([^"]*?(?:'
    r'/(?:alj|board)-decisions/\d{4}/(?:[^"/]+\.(?:pdf|html?)|[^"/]+/index\.html?)'
    r'|/sites/default/files/(?:alj|board)-(?:cr|dab)[^"/]*\.(?:pdf|html?)'
    r')(?:\?[^"]*)?)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL)
# The year page links to itself. Matching any /index.html would also throw away
# every decision published from 2017 on.
SELF_LINK = re.compile(r"/(?:alj|board)-decisions/\d{4}/index\.html?$", re.IGNORECASE)


def decision_no_from_caption(caption: str, url: str = "") -> str | None:
    """The decision number a listing gives, from its caption or its URL slug.

    Delegates to metadata.decision_no_from_text so the index and the corpus
    identify decisions the same way. They did not, and the differences were all
    in the index's favour of being wrong.
    """
    no = metadata.decision_no_from_text(caption)
    if no:
        return no
    m = re.search(r"/(?:board|alj)-((?:dab|cr)-?\d{1,5}R?)/", url, re.IGNORECASE)
    return metadata.decision_no_from_text(m.group(1)) if m else None


def parse_index(page: str, division: str, year: int) -> list[dict]:
    out, seen = [], set()
    for href, text in LINK.findall(page):
        url = urllib.parse.urljoin(f"{BASE}/{DIVISIONS[division]}/{year}/", href)
        if url in seen or SELF_LINK.search(url):
            continue
        seen.add(url)
        caption = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(text))).strip()
        out.append({
            "division": division,
            "year": year,
            "decision_no": decision_no_from_caption(caption, url),
            "caption": caption,
            "url": url,
        })
    return out


def fetch_live(page, url: str) -> str | None:
    """The index page as a real, hand-started Chrome sees it, over CDP.

    Status is not the test -- a block page returns 200 through a browser just
    as happily as anything else -- so this is the same content check
    fetch_via_browser.py uses for individual decisions, applied to a listing.
    """
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(800)
        body = page.content()
    except Exception:
        return None
    if not body or len(body) < 5000 or BLOCKED.search(body[:4000]):
        return None
    return body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("decisions_index.jsonl"))
    ap.add_argument("--from-year", type=int, default=None,
                    help="override the per-division first year")
    ap.add_argument("--to-year", type=int, default=2026)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--baseline", type=Path, default=Path("index_baseline.json"),
                    help="retry a division-year that comes back below its last "
                         "committed count, not just an empty one")
    ap.add_argument("--cdp", default=None,
                    help="http://localhost:9222 of a Chrome started with "
                         "--remote-debugging-port; tops up --live-years of "
                         "the index live instead of trusting the Archive's "
                         "snapshot of a year still being published")
    ap.add_argument("--launch-browser", action="store_true",
                    help="same live top-up as --cdp, but launches its own "
                         "throwaway headless=False Chrome instead of "
                         "attaching to one you started -- for CI, under Xvfb")
    ap.add_argument("--live-years", type=int, default=1,
                    help="how many years back from --to-year to top up "
                         "live when --cdp or --launch-browser is set")
    args = ap.parse_args()

    baseline = {}
    if args.baseline.exists():
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))

    by_key: dict[str, list[dict]] = {}
    unfetched = []
    for division in DIVISIONS:
        start = args.from_year or FIRST_YEAR[division]
        for year in range(start, args.to_year + 1):
            page_url = f"{BASE}/{DIVISIONS[division]}/{year}/index.html"
            expected = baseline.get(f"{division}:{year}", 0)
            found = None
            # A year page that exists always lists decisions, so a parse of zero
            # is a failure and not a fact. Retrying separates the two: the
            # Archive dropped ALJ 1989 on one run and served all 46 on the next,
            # and recorded as a zero that reads exactly like a year in which the
            # Board published nothing.
            #
            # The same thing happens without ever hitting zero: the Archive
            # served a snapshot missing the newest ALJ 2026 decision -- 32
            # instead of the 33 already on record -- with no error to catch,
            # because "some decisions" looks exactly as valid as "all of them".
            # A fresh lookup a minute later returned the full 33 from the same
            # single archived snapshot, so the miss was in the fetch, not the
            # page. Retrying below the last committed count catches that the
            # same way the zero case is caught.
            for attempt in range(2):
                snap = archive.snapshot_url(page_url)
                time.sleep(args.delay)
                page = archive.get_text(snap) if snap else None
                if page:
                    found = parse_index(page, division, year)
                    if found and len(found) >= expected:
                        break
                time.sleep(args.delay)
            if not found:
                unfetched.append(f"{division}:{year}")
                print(f"{division} {year}: NOT COLLECTED", flush=True)
                continue
            by_key[f"{division}:{year}"] = found
            print(f"{division} {year}: {len(found)}", flush=True)

    if args.cdp or args.launch_browser:
        from playwright.sync_api import sync_playwright

        live_from = args.to_year - args.live_years + 1
        with sync_playwright() as pw:
            if args.cdp:
                browser = pw.chromium.connect_over_cdp(args.cdp)
                if not browser.contexts:
                    print("no browser context; is Chrome running with "
                          "--remote-debugging-port?")
                    return 1
            else:
                browser = pw.chromium.launch(headless=False)
            browser_page = browser.new_page()
            try:
                for division in DIVISIONS:
                    for year in range(max(args.from_year or FIRST_YEAR[division],
                                           live_from), args.to_year + 1):
                        key = f"{division}:{year}"
                        page_url = f"{BASE}/{DIVISIONS[division]}/{year}/index.html"
                        body = fetch_live(browser_page, page_url)
                        time.sleep(args.delay)
                        if not body:
                            print(f"{division} {year}: live fetch failed, "
                                  f"keeping Archive's {len(by_key.get(key, []))}",
                                  flush=True)
                            continue
                        live = parse_index(body, division, year)
                        # Union by URL: the live page is the freshest source but
                        # a transient miss there shouldn't drop something only
                        # the Archive still has.
                        merged = {r["url"]: r for r in by_key.get(key, [])}
                        merged.update({r["url"]: r for r in live})
                        merged_list = list(merged.values())
                        if key in unfetched and merged_list:
                            unfetched.remove(key)
                        gain = len(merged_list) - len(by_key.get(key, []))
                        by_key[key] = merged_list
                        print(f"{division} {year}: {len(merged_list)} live "
                              f"(+{gain} over Archive)", flush=True)
            finally:
                browser_page.close()

    rows = [r for found in by_key.values() for r in found]

    jsonl.write(args.out, rows)
    # A sidecar, so that a year nobody could fetch is distinguishable downstream
    # from a year with no decisions in it. Without this, check_index.py reads a
    # failed fetch as decisions having been lost.
    meta = args.out.with_suffix(".meta.json")
    meta.write_text(json.dumps({"unfetched": sorted(unfetched),
                                "decisions": len(rows),
                                "cdp": bool(args.cdp)}, indent=2) + "\n",
                    encoding="utf-8")
    print(f"\n{len(rows)} decisions listed -> {args.out}")
    if unfetched:
        print(f"{len(unfetched)} division-year(s) could not be fetched and are "
              f"recorded in {meta.name}: {', '.join(unfetched)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
