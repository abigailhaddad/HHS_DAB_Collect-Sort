"""Strip the HHS website furniture that print-to-PDF baked into the decision text.

About a quarter of the corpus was captured from the dab.hhs.gov page rather than
a real PDF, so the extracted text carries the site's navigation with it. Two
generations of the template are represented:

  2018-present  "BreadcrumbHome </>About HHS </about/index.html>...", the
                "An official website of the United States government" banner,
                "Skip to main content", "Page sharing options", and whatever
                promo box HHS was running that month ("Freedom 250").
  1990-2006     a "CASE | DECISION | JUDGE | FOOTNOTES" tab bar and "...TO TOP"
                anchors sprinkled through the body.

Left in, this text is indistinguishable from the decision itself: it inflates
num_chars, it pollutes full-text search, and the breadcrumb repeats the case
caption often enough to skew any term count.
"""
from __future__ import annotations

import re

# Whole blocks. Every breadcrumb link is a bare site path -- "</about/agencies>"
# -- and the labels between them are short, so the run is matched with bounded
# lengths. An unbounded "(?:[^<]*<[^>]*>)*" looks equivalent and is not: the HHS
# page has links scattered through the body too, so it chains from the
# breadcrumb to the last link in the document and eats the decision. That cost
# 6.9 MB of real text before it was caught, which is what GUARD_MAX_REMOVED and
# the DAB2980 case in run_checks.py exist to prevent recurring.
BLOCKS = [
    re.compile(r"Breadcrumb\s*Home\s*<\s*/[^<>]{0,200}>"
               r"(?:[^<>]{0,120}<\s*/[^<>]{0,200}>)*", re.IGNORECASE),
    re.compile(r"An official website of the United States government"
               r"(?:\s*Here.{0,3}s how you know)?", re.IGNORECASE | re.DOTALL),
    re.compile(r"Join HHS in Celebrating Freedom 250\s*<[^<>]{0,200}>", re.IGNORECASE),
]

# Single lines / short runs, removed wherever they appear.
LINES = [
    re.compile(r"^\s*Page sharing options\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*Navigate to:\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"Skip\s*\n?\s*to\s*\n?\s*main\s*\n?\s*content", re.IGNORECASE),
    re.compile(r"^\s*CASE\s*\|\s*DECISION\s*\|\s*JUDGE\s*\|\s*FOOTNOTES\s*$",
               re.MULTILINE | re.IGNORECASE),
    re.compile(r"\.\.\.\s*TO TOP", re.IGNORECASE),
    # Residual bare links the breadcrumb pattern didn't swallow.
    re.compile(r"<\s*/[a-z0-9][^<>]{0,200}>", re.IGNORECASE),
]

MARKERS = re.compile(
    r"BreadcrumbHome|Breadcrumb\s*Home"
    r"|An official website of the United States government"
    r"|Skip\s*\n?\s*to\s*\n?\s*main\s*\n?\s*content"
    r"|Page sharing options"
    r"|CASE\s*\|\s*DECISION\s*\|\s*JUDGE"
    r"|\.\.\.\s*TO TOP",
    re.IGNORECASE,
)


def has_chrome(text: str) -> bool:
    """True if any website furniture is present."""
    return bool(MARKERS.search(text))


def clean(text: str) -> str:
    """Remove website furniture. Safe to run on text that has none."""
    for rx in BLOCKS:
        text = rx.sub(" ", text)
    for rx in LINES:
        text = rx.sub(" ", text)
    # Collapse the blank-line drifts the removals leave behind, but keep
    # paragraph structure -- page-break blank runs matter for locating headers.
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# A record is at most a few KB of furniture. Anything past this is a runaway
# pattern eating the decision, so the original is kept and flagged instead.
GUARD_MAX_REMOVED = 0.25


def clean_guarded(text: str) -> tuple[str, bool]:
    """clean(), but refuse the result if it deleted an implausible share.

    Returns (text, ok). ok is False when the guard tripped, in which case the
    text comes back untouched -- silently returning a gutted decision is worse
    than returning a dirty one.
    """
    if not text.strip():
        return text, True
    out = clean(text)
    if len(out) < len(text) * (1 - GUARD_MAX_REMOVED):
        return text, False
    return out, True
