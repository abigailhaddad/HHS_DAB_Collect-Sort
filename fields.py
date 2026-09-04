"""Structured fields taken from the body of a decision, not its header.

metadata.py reads the header block -- number, docket, date, tribunal. This
reads things that sit further in: what the decision reviews, who signed it,
which provider it concerns, and where it states its conclusion.

Each of these is scoped rather than matched loosely, for the reason the rest of
this repo keeps running into: an unscoped match finds a plausible wrong answer
instead of nothing, and a plausible wrong answer does not announce itself.
"""
from __future__ import annotations

import re

# --- what this decision reviews ----------------------------------------------
# An Appellate decision names the ALJ decision under review, and says so:
#   "Tajammul H. Bhatti, M.D., DAB CR245 (1992) (ALJ Decision)"
#   "appeals the decision of an administrative law judge, captioned ... DAB CR6187"
#
# Matching "DAB CR\d+" anywhere instead would be wrong rather than merely noisy:
# it hits 28% of Appellate decisions and 53% of ALJ ones, and ALJ decisions do
# not review each other -- those are all precedent citations. Scoped, the same
# corpus gives 23% of Appellate decisions and one ALJ decision, which is the
# shape the tribunal actually has.
REVIEWED = re.compile(
    r"DAB\s+CR\s?(\d{1,5}R?)\s*\((?:19|20)\d\d\)\s*\(\s*ALJ\s+Decision", re.I)
REVIEWED_CAPTIONED = re.compile(
    r"(?:captioned|appeals the decision|ALJ Decision)[^.]{0,200}?"
    r"DAB\s+CR\s?(\d{1,5}R?)", re.I)

# --- provider identifiers -----------------------------------------------------
# Structured identifiers from the caption. These are the join keys to CMS
# provider data, which is most of why they are worth carrying.
PROVIDER_IDS = {
    "CCN": re.compile(r"\bCCN[:\s#]*([0-9]{2}[-\s]?[0-9]{4})", re.I),
    "NPI": re.compile(r"\bNPI[:\s#]*([0-9]{10})\b", re.I),
    "PTAN": re.compile(r"\bPTAN[:\s#]*([A-Z0-9\-]{4,15})", re.I),
    "CLIA": re.compile(r"\bCLIA\s*(?:ID|No\.?)?[:\s#]*([0-9]{2}[A-Z][0-9]{7})", re.I),
}

# --- who decided it -----------------------------------------------------------
# Three sign-off shapes, and in two of them the name comes after the marker, not
# before it. Requiring the name on the "/s/" line itself found 3% of ALJ
# decisions; allowing it on the following line finds 58%.
#
#   ALJ:       "/s/\nBill Thomas\nAdministrative Law Judge"
#   Appellate: "____/s/____\n Judith A. Ballard\n ... \n Presiding Board Member"
#   in text:   "a decision by Administrative Law Judge Charles E. Stratton"
#
# The Appellate Division sits in panels, so this returns a list.
_NAME = r"[A-Z][A-Za-z.\-']+(?:[^\S\n]+[A-Z][A-Za-z.\-']*[A-Za-z.\-'])" \
        r"{1,3}"
TITLE_AFTER = re.compile(
    rf"\n[^\S\n]*({_NAME})[^\S\n]*\n[^\S\n]*"
    r"(?:Administrative Law Judge|(?:Presiding )?Board Member|Panel Chairman)",
    re.MULTILINE)
SIGNATURE = re.compile(rf"/s/[_\s]*\n?[^\S\n]*({_NAME})")
NAMED_ALJ = re.compile(rf"Administrative Law Judge[^\S\n]+({_NAME})")

# --- where it states its conclusion -------------------------------------------
# The span is returned verbatim and is NOT a disposition label. A decision says
# "affirm" somewhere in 90% of cases, and "petitioner asks us to affirm" is not
# an affirmance -- classifying on a verb would put a confident wrong label on
# thousands of decisions. The text is given so a reader or a later, measured
# classifier can do that properly.
CONCLUSION = re.compile(r"(?:^|\n)[^\S\n]*(?:[IVX]+\.?[^\S\n]*)?"
                        r"(?:Conclusion and Order|Conclusion|ORDER)\b[.:]?"
                        r"[^\S\n]*\n", re.IGNORECASE)
CONCLUSION_MAX = 1200


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def reviews_decision_no(text: str) -> str | None:
    """The ALJ decision this decision reviews, if it names one."""
    head = _norm(text[:8000])
    m = REVIEWED.search(head) or REVIEWED_CAPTIONED.search(head)
    return f"CR{m.group(1).upper()}" if m else None


def provider_ids(text: str) -> list[str]:
    """Provider identifiers from the caption, as "TYPE:value"."""
    head = _norm(text[:6000])
    out = []
    for kind, rx in PROVIDER_IDS.items():
        for m in rx.finditer(head):
            value = re.sub(r"[\s-]", "", m.group(1)).upper()
            tagged = f"{kind}:{value}"
            if tagged not in out:
                out.append(tagged)
    return out


def judges(text: str) -> list[str]:
    """Who decided it. A list, because the Appellate Division sits in panels.

    Coverage is uneven by era, so a comparison across time inherits the
    coverage as well as the decisions.
    """
    # Both patterns, not the first that hits. An Appellate panel signs as
    # "/s/ Judith A. Ballard ... /s/ Donald F. Garrett ... /s/ Marc R. Hillson
    # Presiding Board Member": only the last name carries a title, so stopping
    # at TITLE_AFTER returned one member of three.
    out = []
    for rx in (TITLE_AFTER, SIGNATURE):
        for m in rx.finditer(text):
            name = _norm(m.group(1))
            if name and name not in out:
                out.append(name)
    if out:
        return out
    m = NAMED_ALJ.search(_norm(text[:20000]))
    return [_norm(m.group(1))] if m else []


def disposition_text(text: str) -> str | None:
    """The decision's own concluding passage, verbatim. Not a label.

    None when the decision has no conclusion heading, rather than falling back
    to the tail of the document -- the tail is usually a signature block, and
    returning it would look like a conclusion without being one.
    """
    matches = list(CONCLUSION.finditer(text))
    if not matches:
        return None
    span = text[matches[-1].end():]
    return _norm(span)[:CONCLUSION_MAX] or None
