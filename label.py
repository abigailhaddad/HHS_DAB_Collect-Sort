r"""Decide whether a decision is *about* a category, not whether it mentions one.

The original slices matched a citation anywhere in the full text. Three things
break that, all of them observed in the published slices:

1. Precedent. "Head Start of New Hanover County, Inc., Decision No. 65,
   September 26, 1979" is the Board's standing cite on documenting costs, so the
   253-record head_start slice swept in cost-disallowance appeals by Washington
   State University, Oglala Sioux Community College and the New York and South
   Dakota social services departments -- none of them Head Start disputes.
2. Enumeration. Friedman (DAB 1281) is a licence-revocation case that lists
   "(sections 1128(b)(6), (7), (8))" in a parenthetical about the IG's powers.
   It landed in the quality-of-care slice.
3. Losing arguments. Chang (DAB 1198) is a section 1128(a) conviction case in
   which the petitioner argued 1128(b)(6) should apply instead, and lost.

So: blank out case citations first, then require the surviving matches to carry
weight -- either the basis is named where the decision frames what it is
deciding, or it recurs enough that the decision is plainly working with it.
"""
from __future__ import annotations

import re

# A case citation: a capitalised party run, then a reporter number, closing on a
# parenthesised year or a bare date. Bounded lengths throughout -- an unbounded
# name run walks backwards across sentence boundaries and swallows the operative
# text along with the citation.
CITATION = re.compile(
    r"[A-Z][A-Za-z.,&'’\-’ ]{2,80}?,\s*"
    r"(?:DAB|DGAB|GAB)?\s*"
    r"(?:Docket\s+Nos?\.|Decision\s+Nos?\.|No\.|CR)\s*"
    r"[^;()]{0,90}?"
    r"(?:\(\s*\d{4}\s*\)|[A-Z][a-z]+\s+\d{1,2},\s*\d{4})",
)

# Where a decision says what it is deciding. The header plus the opening
# recitation; past this the decision is reasoning, and reasoning cites.
OPENING_CHARS = 6000

# Enough repetition that the decision is working with the provision, not
# glancing at it. Calibrated on the published slices; see run_checks.py.
MIN_RECURRENCE = 3


def normalize(text: str) -> str:
    """Collapse every run of whitespace to one space before matching.

    clean() deliberately keeps line structure, because metadata.py needs it to
    find the header. Matching must not see it: PDF extraction breaks citations
    and even ordinary phrases across lines, so "Head\nStart" and
    "1128(b)\n(7)" are common. Matching the un-normalized text silently loses
    them -- it dropped Topeka Public Schools (DAB 47) out of head_start, a real
    Head Start cost appeal, because the phrase spanned a line break.
    """
    return re.sub(r"\s+", " ", text)


def citation_spans(text: str) -> list[tuple[int, int]]:
    return [m.span() for m in CITATION.finditer(text)]


def _inside(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in spans)


class Prepared:
    """Normalized text plus its citation spans, computed once per document.

    Both are per-document, not per-category, and the citation scan is the
    expensive part. Recomputing them inside evidence() made a full 16-category
    pass over 8,246 decisions take minutes instead of seconds.
    """

    __slots__ = ("text", "spans")

    def __init__(self, text: str):
        self.text = normalize(text)
        self.spans = citation_spans(self.text)


def evidence(doc: "Prepared | str", pattern: re.Pattern) -> dict:
    """Count matches, separating the ones that only appear inside citations."""
    if not isinstance(doc, Prepared):
        doc = Prepared(doc)
    text, spans = doc.text, doc.spans
    hits, in_cite = [], 0
    for m in pattern.finditer(text):
        if _inside(m.start(), spans):
            in_cite += 1
        else:
            hits.append(m.start())
    return {
        "n_matches": len(hits),
        "n_in_citation": in_cite,
        "n_in_opening": sum(1 for p in hits if p < OPENING_CHARS),
        "first_match_char": hits[0] if hits else None,
    }


def is_member(ev: dict) -> bool:
    """Named where the decision frames itself, or worked with throughout."""
    return ev["n_in_opening"] >= 1 or ev["n_matches"] >= MIN_RECURRENCE


def label(doc: "Prepared | str", pattern: re.Pattern) -> tuple[bool, dict]:
    ev = evidence(doc, pattern)
    return is_member(ev), ev
