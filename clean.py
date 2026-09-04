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
    # Not anchored to a line. Removing the breadcrumb above joins these onto
    # the surrounding text, so by the time they are reached they are mid-line.
    re.compile(r"Page sharing options", re.IGNORECASE),
    re.compile(r"Navigate to:", re.IGNORECASE),
    # Both spellings: "Skip to main content" on the modern template, "Skip
    # Navigation" on the 1999-2006 pages.
    re.compile(r"Skip\s*\n?\s*to\s*\n?\s*main\s*\n?\s*content", re.IGNORECASE),
    re.compile(r"Skip\s+Navigation", re.IGNORECASE),
    # "| FOOTNOTES" is optional and the anchors are gone, so that this matches
    # exactly what MARKERS detects. They disagreed: the detector accepted
    # "CASE | DECISION | JUDGE" while the remover demanded the FOOTNOTES tab as
    # well, so 21 decisions were correctly flagged as dirty and then not cleaned.
    re.compile(r"CASE\s*\|\s*DECISION\s*\|\s*JUDGE(?:\s*\|\s*FOOTNOTES)?",
               re.IGNORECASE),
    re.compile(r"\.\.\.\s*TO TOP", re.IGNORECASE),
    # Residual bare links the breadcrumb pattern didn't swallow.
    re.compile(r"<\s*/[a-z0-9][^<>]{0,200}>", re.IGNORECASE),
]

# The .gov reassurance block on the per-decision pages from 2017: about 300
# characters of boilerplate on every one of them. One sentence per pattern
# rather than one regex with optional groups -- written that way, the optional
# groups matched empty and only the first sentence was ever removed.
DOT_GOV_BLOCK = [
    re.compile(r"Here.{0,3}s how you know", re.IGNORECASE),
    re.compile(r"Official websites use\s*\.gov", re.IGNORECASE),
    re.compile(r"A\s*\.gov website belongs to an official government "
               r"organization in the United States\.?", re.IGNORECASE),
    re.compile(r"Secure\s*\.gov websites use HTTPS", re.IGNORECASE),
    re.compile(r"A lock \(\s*Lock\s*A locked padlock\s*\)\s*(?:or\s*)?"
               r"(?:https://)?\s*"
               r"(?:means you.{0,3}ve safely connected to the\s*\.gov website\.?)?",
               re.IGNORECASE),
]
LINES = LINES + DOT_GOV_BLOCK

MARKERS = re.compile(
    r"BreadcrumbHome|Breadcrumb\s*Home"
    r"|An official website of the United States government"
    r"|Skip\s*\n?\s*to\s*\n?\s*main\s*\n?\s*content"
    r"|Page sharing options"
    r"|Skip\s+Navigation"
    r"|Here.{0,3}s how you know"
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


# Two thresholds, because one does not work at both ends. The furniture is
# bounded -- the largest legitimate removal in the corpus is 2,972 characters --
# so anything past GUARD_MAX_CHARS is a pattern eating the decision. But a short
# order can be a third furniture by volume and still be cleaned correctly, which
# is why proportion alone is wrong: it kept the chrome on the very records that
# had the most of it.
GUARD_MAX_CHARS = 6000
GUARD_MAX_SHARE = 0.60


def _visible(text: str) -> int:
    """Length ignoring whitespace.

    The guard has to measure content, not characters. clean() also collapses
    the space padding PDF layout leaves behind, and on a heavily padded decision
    that alone runs to thousands of characters -- DAB No. 2783 and DAB No. 2814
    each shed about 7,000 characters of pure whitespace and were held back as
    runaway removals when nothing had been removed at all.
    """
    return len(re.sub(r"\s+", "", text))


def clean_guarded(text: str) -> tuple[str, bool]:
    """clean(), but refuse the result if it deleted an implausible share.

    Returns (text, ok). ok is False when the guard tripped, in which case the
    text comes back untouched -- silently returning a gutted decision is worse
    than returning a dirty one.
    """
    if not text.strip():
        return text, True
    out = clean(text)
    before, after = _visible(text), _visible(out)
    removed = before - after
    if removed > GUARD_MAX_CHARS or removed > before * GUARD_MAX_SHARE:
        return text, False
    return out, True
