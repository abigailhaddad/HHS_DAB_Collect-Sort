"""Did we actually get the decision? A named verdict per file.

HTTP 200 means nothing here. Both the Akamai block and the Internet Archive's
own miss page return 200 with a full HTML skeleton and no decision in it, and a
redirect to the section landing page returns a large, healthy-looking document
that is not a decision. Every one of those saves cleanly and the resume check
counts it as done.

The verdicts distinguish the two things you do about it:

  OK              a decision
  CHALLENGE       a block or interstitial -- RETRY after re-solving in the
                  browser; not a data problem
  ARCHIVE_MISS    the Archive served its own error page with a 200
  NOT_A_DECISION  a real page, but the landing page or a search result rather
                  than a decision -- the URL form is wrong, go find the link
  THIN            plausible shape, too little text to be a decision
  EMPTY           nothing at all

This exists as a module and a command so that checking is a command rather than
a habit -- every verification in this pipeline's history was written ad hoc and
thrown away, which is why the same class of failure kept coming back.

    python verify.py decisions/            # audit a fetched directory
"""
from __future__ import annotations

import argparse
import collections
import re
from pathlib import Path

CHALLENGE_MARKERS = ("access denied", "just a moment", "attention required",
                     "verifying you are human", "checking your browser",
                     "cloudflare ray id", "enable javascript and cookies")
ARCHIVE_MISS_MARKERS = ("wayback machine has not archived", "got an http",
                        "this page is not available on the web")
# The Board's letterhead. A decision page carries one of these; the section
# landing page, the search-results page and the year index carry none.
#
# The 1982-1986 reprints are the reason "GAB Decision N" is here: they head with
# that alone and never spell out the Board's name, so a marker set built from
# the modern template called 159 real decisions -- 51,000 characters each -- not
# decisions at all. The set has to cover every era the corpus spans.
# A numbered decision line counts too, and is the more durable signal: the
# letterhead varies by era and by typo ("GAB Drecision 247", "DAB Decision 577"),
# and the AFDC plan-disapproval decisions head with the department's name and
# never say "Appeals Board" at all.
DECISION_MARKERS = re.compile(
    r"DEPARTMENTAL\s+APPEALS\s+BOARD|DEPARTMENTAL\s+GRANT\s+APPEALS\s+BOARD|"
    r"Civil\s+Remedies\s+Division|Appellate\s+Division|Grant\s+Appeals\s+Board|"
    r"\b(?:D?GAB|DAB)\s+D\w*ecision\s*\d|"
    r"\bDAB\s+No\.?\s*\d|\bDecision\s+No\.?\s*(?:CR)?\s*\d", re.I)

MIN_PDF_BYTES = 2000
# A decision runs to thousands of characters of text. Below this it is a stub,
# whatever its byte size -- an HTML shell can be 50 KB and hold nothing.
MIN_TEXT_CHARS = 800


def verdict(raw: bytes, name: str = "") -> tuple[str, str]:
    """Classify one fetched file. Returns (verdict, detail)."""
    if not raw or not raw.strip():
        return "EMPTY", "no bytes"

    if raw[:4] == b"%PDF":
        if len(raw) < MIN_PDF_BYTES:
            return "THIN", f"PDF of {len(raw)} bytes"
        return "OK", ""
    if name.lower().endswith(".pdf"):
        return "NOT_A_DECISION", "served HTML for a PDF URL"

    text = raw.decode("utf-8", "replace")
    low = text[:6000].lower()
    if any(m in low for m in CHALLENGE_MARKERS):
        return "CHALLENGE", "block or interstitial page"
    if any(m in low for m in ARCHIVE_MISS_MARKERS):
        return "ARCHIVE_MISS", "archive error page served with 200"

    visible = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1\s*>", " ",
                                             text, flags=re.S | re.I))
    visible = re.sub(r"\s+", " ", visible).strip()
    if not DECISION_MARKERS.search(visible):
        return "NOT_A_DECISION", "no Board letterhead"
    if len(visible) < MIN_TEXT_CHARS:
        return "THIN", f"{len(visible)} chars of visible text"
    return "OK", ""


def verdict_for(path: Path) -> tuple[str, str]:
    try:
        return verdict(path.read_bytes(), path.name)
    except Exception as e:                      # unreadable is a result too
        return "ERROR", str(e)[:100]


def main() -> int:
    ap = argparse.ArgumentParser(description="audit a directory of fetched decisions")
    ap.add_argument("directory", type=Path)
    ap.add_argument("--list", action="store_true", help="name every non-OK file")
    args = ap.parse_args()

    counts: collections.Counter[str] = collections.Counter()
    bad: list[tuple[str, str, str]] = []
    for p in sorted(args.directory.iterdir()):
        if not p.is_file() or p.name.startswith("_"):
            continue
        v, detail = verdict_for(p)
        counts[v] += 1
        if v != "OK":
            bad.append((v, p.name, detail))

    total = sum(counts.values())
    print(f"{total} files in {args.directory}")
    for v, n in counts.most_common():
        print(f"  {v:16} {n:>5}")
    if bad and args.list:
        print()
        for v, name, detail in bad:
            print(f"  {v:16} {name:44} {detail}")
    if counts["CHALLENGE"]:
        print(f"\n{counts['CHALLENGE']} blocked -- re-solve in the debug Chrome "
              f"and re-run the fetch; these are retryable, not missing.")
    # A non-zero exit means something needs doing, which is what makes this
    # usable from a scheduled job.
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
