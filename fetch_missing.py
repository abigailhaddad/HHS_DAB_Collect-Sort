"""Fetch the decisions audit_completeness.py found missing, via the Archive.

The URLs in missing.jsonl point at dab.hhs.gov, which returns 403 to automated
requests, so each one is fetched through the Internet Archive instead. Resumable:
a file that is already on disk and passes the guards is not fetched again.

    python fetch_missing.py missing.jsonl --out-dir decisions/

Failures are transient often enough to matter -- the Archive rate-limits under a
long run, and the same URL that returned nothing succeeds a minute later. They
are logged to <out-dir>/_failures.jsonl in the same format as the input, so a
second pass is just:

    python fetch_missing.py decisions/_failures.jsonl --out-dir decisions/

A 200 is not evidence of success. Two ways this goes wrong here:

  - "web/2026id_/<url>" looks like it asks for the newest snapshot and instead
    redirects to the live site, which is the thing behind the 403. The response
    is a 403 page from HHS, delivered under an archive.org URL. The snapshot
    has to be addressed by its exact timestamp, which is what
    collect_index.snapshot_url resolves.
  - The Archive serves its own HTML error page with a 200 status when it has no
    snapshot, and a truncated PDF is still a PDF.

So every response is checked for shape and size before it is kept. Otherwise the
junk lands on disk, the resume logic counts it as done, and the corpus grows by
files that extract to nothing.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import collect_index

UA = collect_index.UA

MIN_PDF_BYTES = 2000
MIN_HTML_BYTES = 1500
# The Archive says this with a 200.
ARCHIVE_ERROR = re.compile(
    rb"Wayback Machine has not archived|Got an HTTP \d+ response|"
    rb"This page is not available on the web|<title>\s*Wayback Machine\s*</title>",
    re.IGNORECASE)


def is_good(body: bytes, url: str) -> tuple[bool, str]:
    if not body:
        return False, "empty response"
    if ARCHIVE_ERROR.search(body[:4000]):
        return False, "archive error page"
    if url.lower().endswith((".pdf",)):
        if not body.startswith(b"%PDF"):
            return False, "not a PDF"
        if len(body) < MIN_PDF_BYTES:
            return False, f"PDF too small ({len(body)} bytes)"
        return True, ""
    if len(body) < MIN_HTML_BYTES:
        return False, f"HTML too small ({len(body)} bytes)"
    return True, ""


def out_name(rec: dict) -> str:
    """A stable filename that keeps the decision number and the extension."""
    tail = rec["url"].rstrip("/").split("/")[-1]
    if tail.lower().startswith("index."):          # per-decision page directory
        tail = rec["url"].rstrip("/").split("/")[-2] + ".html"
    no = rec.get("decision_no") or Path(tail).stem
    ext = Path(tail).suffix.lower() or ".html"
    return f"{rec['year']}_{no}{ext}"


def fetch(url: str, timeout: int = 60, tries: int = 5) -> bytes | None:
    snap = collect_index.snapshot_url(url)
    if not snap:
        return None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(snap, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 410):
                return None
            if attempt == tries - 1:
                return None
            time.sleep(2 ** attempt + random.uniform(0, 1))
        except Exception:
            if attempt == tries - 1:
                return None
            time.sleep(2 ** attempt + random.uniform(0, 1))
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("missing", type=Path)
    ap.add_argument("--out-dir", type=Path, default=Path("decisions"))
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--year-from", type=int, default=None)
    ap.add_argument("--year-to", type=int, default=None)
    args = ap.parse_args()

    records = [json.loads(l) for l in args.missing.open(encoding="utf-8") if l.strip()]
    if args.year_from:
        records = [r for r in records if r["year"] >= args.year_from]
    if args.year_to:
        records = [r for r in records if r["year"] <= args.year_to]
    if args.limit:
        records = records[:args.limit]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    failures = args.out_dir / "_failures.jsonl"
    got = skipped = failed = 0
    with failures.open("a", encoding="utf-8") as flog:
        for i, rec in enumerate(records, 1):
            dest = args.out_dir / out_name(rec)
            if dest.exists() and dest.stat().st_size > MIN_PDF_BYTES:
                skipped += 1
                continue
            body = fetch(rec["url"])
            ok, why = is_good(body or b"", rec["url"])
            if ok:
                dest.write_bytes(body)
                got += 1
            else:
                failed += 1
                flog.write(json.dumps({**rec, "error": why or "fetch failed"}) + "\n")
                flog.flush()
            if i % 25 == 0:
                print(f"  {i}/{len(records)}  got {got}  skipped {skipped}  failed {failed}",
                      flush=True)
            # Jitter, so a long run does not look like a metronome.
            time.sleep(args.delay * random.uniform(0.7, 1.4))

    print(f"\n{got} fetched, {skipped} already present, {failed} failed "
          f"-> {args.out_dir}")
    if failed:
        print(f"failures logged to {failures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
