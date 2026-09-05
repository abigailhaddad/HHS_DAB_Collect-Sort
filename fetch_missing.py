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
    archive.snapshot_url resolves.
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
from pathlib import Path

import archive

MIN_PDF_BYTES = 2000
MIN_HTML_BYTES = 1500


def min_bytes(name: str) -> int:
    """The floor for a file of this type. Applying the PDF floor to HTML made
    any 1,500-1,999 byte page fail the resume check forever: it was written,
    then judged too small to count, then fetched again on every run."""
    return MIN_PDF_BYTES if name.lower().endswith(".pdf") else MIN_HTML_BYTES
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
    """A collision-free filename: the year plus the source file's own stem.

    Naming by decision number collides. 114 of the missing records are ALJ
    Rulings, a separate series whose captions read "ALJ Ruling No. 2014-17";
    every one of those parsed to the bare year, so 23 different rulings all
    wanted the name "2014_2014.pdf" and 22 of them would have been silently
    dropped by the resume check. The source stem is unique per URL -- verified
    across all 1,566 -- and the year keeps the directory readable.
    """
    # Strip the query string before anything else. The 2017-18 URLs end
    # "...alj-cr5002.pdf?language=en", and Path().suffix on that is
    # ".pdf?language=en" -- so the file saved with an extension no suffix
    # filter matches, and extract.py skipped 232 of them without a word.
    tail = rec["url"].rstrip("/").split("/")[-1].split("?", 1)[0].split("#", 1)[0]
    if tail.lower().startswith("index."):          # per-decision page directory
        tail = rec["url"].rstrip("/").split("/")[-2] + ".html"
    ext = Path(tail).suffix.lower() or ".html"
    return f"{rec['year']}_{Path(tail).stem}{ext}"


def fetch(url: str) -> bytes | None:
    snap = archive.snapshot_url(url)
    return archive.get(snap, timeout=60) if snap else None


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
            if dest.exists() and dest.stat().st_size >= min_bytes(dest.name):
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
