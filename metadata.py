"""Parse the decision header into fields you can filter on.

Every decision opens with the same furniture -- tribunal, docket number,
decision number, date -- across four template generations (Grant Appeals Board
1976-1987, Appellate Division, Civil Remedies Division, and the 2018+ web
capture). The filename is not a substitute: ids in the source corpus are
hand-typed and carry real typos ("0980.02.25DAB083" for 1980), so dates and
numbers are read from the text and the filename is only a fallback.

Run `python metadata.py CORPUS.jsonl` to print coverage rates.
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from datetime import date
from pathlib import Path

import jsonl

MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}
# OCR of the older scans mangles month names; these are the ones actually seen.
MONTH_FIXES = {"harch": "march", "sep": "september", "jan": "january",
               "feb": "february", "mar": "march", "apr": "april",
               "jun": "june", "jul": "july", "aug": "august",
               "oct": "october", "nov": "november", "dec": "december"}

# "DATE: April 7, 2006" / "Date~ SEP. 28, 1978" / a bare "June 30, 2015" line.
# The separator before the year is not always a comma: 1970s scans yield
# "August 14 I 1978" and "October 31 1978?". The permitted characters include
# I and l because OCR reads a comma as either -- excluding letters outright
# dropped "August 14 I 1978". The year must not run into more digits, so a
# five-digit smear is not read as a day plus a year.
_DAY_YEAR = r"(\d{1,2})[\s,.;:|Il]{0,4}(\d{4})(?!\d)"
DATE_RE = re.compile(rf"\b([A-Za-z~][A-Za-z.~]{{1,9}})\.?\s+{_DAY_YEAR}\b",
                     re.IGNORECASE)
DATE_LABELLED_RE = re.compile(
    rf"date\s*[:~.]?\s*([A-Za-z~][A-Za-z.~]{{1,9}})\.?\s+{_DAY_YEAR}",
    re.IGNORECASE)
# Is there a DATE label at all? If there is and it will not parse, the answer is
# "unknown", not "some other date from the page".
DATE_LABEL_PRESENT = re.compile(r"\bdate\s*[:~.]", re.IGNORECASE)

# "Decision No. 2024", "Decision No. CR1723", "DAB No. 3117", "DAB CR6187"
#
# Deliberately strict. The 1970s-80s scans mangle the label itself -- "Decis ion
# No. 33", "Decision 110. 27", "recision No. 146", "Decision ~o. 195", "Decision
# No .3~" -- and loosening the pattern enough to catch those was measured
# against the Board's published index over 1,566 decisions: agreement rose one
# point while wrong answers rose by 96, because a loose pattern picks a fragment
# ("No .3~" -> 3) or a citation to another decision. A null is recoverable; a
# plausible wrong number is not. Where the number matters, take it from the
# published index -- see build_dataset.py.
DECISION_RE = re.compile(
    r"decision\s+nos?\.?\s*((?:CR)?\s*\d{1,5})", re.IGNORECASE)
DAB_NO_RE = re.compile(r"\bDAB\s+(?:No\.\s*)?((?:CR)?\s*\d{1,5})", re.IGNORECASE)

# "Docket No. C-07-429", "Docket Nos. 77-7, 77-8, and 77-9", "Docket No. A-15-44"
#
# The separator is spelled out rather than "(?:,|and)". A docket number is
# alphanumeric, so with a loose separator the word "and" in ", and 77-9" is
# itself a valid token: the run matched "77-7, 77-8, and", stopped, and the
# third docket was silently lost.
DOCKET_SEP = r"\s*(?:,\s*and\s+|,\s*|\s+and\s+)"
# The connectives are excluded from being tokens. A docket number is
# alphanumeric, so without this "Docket No. 84-228, and $1,032,130 in..."
# captures the trailing "and" as a docket -- the run has to end on a real one.
DOCKET_TOKEN = r"(?!and\b|or\b)[A-Za-z0-9][A-Za-z0-9\-‐-―]*"
DOCKET_RE = re.compile(
    rf"docket\s+nos?\.?\s*({DOCKET_TOKEN}(?:{DOCKET_SEP}{DOCKET_TOKEN})*)",
    re.IGNORECASE)

TRIBUNALS = [
    ("Civil Remedies Division", re.compile(r"civil\s+remedies\s+division", re.I)),
    ("Appellate Division", re.compile(r"appellate\s+division", re.I)),
    # Pre-1987 the whole body was the Grant Appeals Board; "DGAB"/"GAB Decision"
    # also appear in the 1980s reprints.
    ("Grant Appeals Board", re.compile(
        r"grant\s+appeals\s+board|\bDGAB\b|\bGAB\s+Decision\b", re.I)),
]

# Who the appeal ran against. Ordered: the specific names before the generic
# department, because every decision says "Department of Health and Human
# Services" in its letterhead and that would swallow all of them.
RESPONDENTS = [
    # Two alternatives, deliberately not one: the phrase is case-insensitive,
    # the "I.G." abbreviation is not. Under IGNORECASE "\bI\.?G\.?\b" matches
    # the bare word "ig" and tags unrelated decisions.
    ("Inspector General", re.compile(
        r"(?i:\bthe\s+inspector\s+general\b)|\bI\.\s?G\.\b")),
    ("CMS", re.compile(r"centers\s+for\s+medicare\s*&?\s*(?:and\s*)?medicaid\s+services|\bCMS\b", re.I)),
    ("HCFA", re.compile(r"health\s+care\s+financing\s+administration|\bHCFA\b", re.I)),
    ("ACF", re.compile(r"administration\s+for\s+children\s+and\s+families|\bACF\b", re.I)),
    ("OHDS", re.compile(r"office\s+of\s+human\s+development\s+services|\bOHDS\b", re.I)),
    ("ORI", re.compile(r"office\s+of\s+research\s+integrity|\bORI\b", re.I)),
]


# Words that appear in a decision header and are close enough to a month name
# for difflib to accept them. "Decision" scores against "December", which turned
# "Decision 3 1978" into 3 December 1978.
NOT_MONTHS = {"decision", "decisions", "december3", "docket", "dockets",
              "department", "departmental", "division", "subject", "appeals",
              "appellate", "remedies", "medicare", "medicaid", "petitioner"}


def _month(raw: str) -> int | None:
    """Month number from a possibly OCR-damaged name.

    The 1970s scans render months as "~E.rch", "Nay", "Harch" and "SEP". An
    exact table misses all of those, and the cost of missing is not a null --
    it used to be a fall-through to the first date anywhere on the page, which
    is a date from the facts. DAB No. 33 (March 1977) was dated February 1969
    that way.
    """
    m = re.sub(r"[^a-z]", "", raw.lower())
    if not m or m in NOT_MONTHS:
        return None
    m = MONTH_FIXES.get(m, m)
    if m in MONTHS:
        return MONTHS[m]
    for name, i in MONTHS.items():
        if len(m) >= 3 and name.startswith(m[:3]):
            return i
    close = difflib.get_close_matches(m, MONTHS, n=1, cutoff=0.6)
    return MONTHS[close[0]] if close else None


def _to_date(mon: str, day: str, year: str) -> str | None:
    idx = _month(mon)
    if idx is None:
        return None
    try:
        return date(int(year), idx, int(day)).isoformat()
    except ValueError:
        return None


# The decision number as it appears in the source filename:
# "1990.10.15DAB1200 Sumter County", "2016.08.17 CR4685 Rochelle Gardens",
# "2005.01.25RUL2005-1 Oklahoma", "2012.07.17ALJRUL 2012-1 Douglas L. Clore".
# No leading \b: in "1990.10.15DAB1200" the digit and the D are both word
# characters, so there is no boundary between them and an anchored pattern
# matches nothing.
# "No." may sit between the word and the number -- "ALJ Ruling No. 2016-14" --
# and without it the ruling fell through to the header parse, which picked a
# number out of the body: four different rulings came back as 1771.
FILENAME_RULING = re.compile(
    r"(?:ALJ\s*)?RUL(?:ING)?[\s.,;_-]*(?:No\.?\s*)?(\d{4}-\d{1,3})",
    re.IGNORECASE)
# The trailing R is part of the number: CR10R is the decision on reconsideration
# of CR10, a different document. Dropping it merged the two. This also reads
# "Decision No. 1550" as well as "DAB1550" and "CR4685". No leading \b: in
# "2004.07.08CR1196" the digit and the C are both word characters.
FILENAME_NO = re.compile(
    r"(DAB|CR|Decision\s+No\.?|No\.)[\s;,._-]*0*(\d{1,5}R?)\b", re.IGNORECASE)


def decision_no_from_text(fragment: str) -> str | None:
    """The decision number named in a short fragment -- a filename or a caption.

    One implementation for both, because they diverged: the index-caption
    version required a word boundary before "CR", which never matches in
    "2004.07.08CR1196" (digit and C are both word characters); it required
    "Ruling No." where captions also write "ALJ Ruling 2013-2"; and it dropped
    the R suffix that distinguishes CR10R from CR10. Those three between them
    left 394 published decisions with no identifier at all.

    Measured against the 8,246-decision corpus this also beats parsing the
    header: 98% coverage for the Appellate Division against 99% for the text,
    but 35 numbers shared by more than one decision against 132. OCR mangles
    the label in the older scans -- "Decis ion No. 33", "recision No. 146" --
    and a failed parse then picks up a citation to some other decision, which
    is how 28 different decisions all came back as number 436.
    """
    if not fragment:
        return None
    m = FILENAME_RULING.search(fragment)
    if m:
        return "RULING" + m.group(1)
    m = FILENAME_NO.search(fragment)
    if not m:
        return None
    label = re.sub(r"[\s.]", "", m.group(1)).upper()
    prefix = "CR" if label == "CR" else ""
    no = f"{prefix}{m.group(2).upper()}"
    # A bare four-digit number after a naked "No." is a year far more often
    # than a decision -- "ALJ Ruling No. 2014-17" reduced to 2014 that way.
    # The guard applies only to that weakest form: DAB No. 2024 and Decision
    # No. 2016 are real Appellate decisions, and rejecting every number in
    # 1974-2026 cost 137 of them.
    if label == "NO" and re.fullmatch(r"(?:19|20)\d\d", no):
        return None
    return no


def decision_no_from_id(record_id: str) -> str | None:
    """The decision number in a source filename."""
    return decision_no_from_text(record_id)


def _norm_no(raw: str) -> str:
    return re.sub(r"\s+", "", raw).upper()


def parse(text: str, record_id: str = "") -> dict:
    """Pull header fields out of one decision. Missing fields come back None."""
    # Cleaning is the caller's job (build_dataset does it once per record);
    # running it again here doubled the work on every decision. Text that has
    # not been cleaned still parses -- the header sits above the furniture.
    head = text[:4000]                   # the header always sits in the first pages

    decision_no = None
    for rx in (DECISION_RE, DAB_NO_RE):
        m = rx.search(head)
        if m:
            candidate = _norm_no(m.group(1))
            # A four-digit number next to "Decision" is a year far more often
            # than it is a decision number in this corpus.
            if not re.fullmatch(r"(?:19|20)\d\d", candidate):
                decision_no = candidate
                break

    dockets = []
    m = DOCKET_RE.search(head)
    if m:
        # IGNORECASE: DOCKET_RE has the flag, re.split does not inherit it, so
        # an uppercase "84-228 AND 84-229" was left unsplit and "AND" became a
        # docket number.
        dockets = [_norm_no(d) for d in
                   re.split(DOCKET_SEP, m.group(1), flags=re.IGNORECASE) if d.strip()]

    # The labelled "DATE:" line is the decision date. An unlabelled date in the
    # header is only trusted when there is no label to trust instead: the header
    # is full of dates from the facts -- audit periods, grant terms -- and
    # picking one of those is worse than returning nothing.
    decision_date = None
    for m in DATE_LABELLED_RE.finditer(head):
        decision_date = _to_date(*m.groups())
        if decision_date:
            break
    if decision_date is None and not DATE_LABEL_PRESENT.search(head):
        for m in DATE_RE.finditer(head):
            decision_date = _to_date(*m.groups())
            if decision_date:
                break

    tribunal = next((name for name, rx in TRIBUNALS if rx.search(head)), None)
    respondent = next((name for name, rx in RESPONDENTS if rx.search(head)), None)

    fm = re.match(r"\D*(\d{4})[.\s]*(\d{2})?[.\s]*(\d{2})?", record_id)
    filename_year = int(fm.group(1)) if fm else None

    return {
        "decision_no": decision_no,
        "decision_no_from_id": decision_no_from_id(record_id),
        "docket_nos": dockets,
        "decision_date": decision_date,
        "year": int(decision_date[:4]) if decision_date else filename_year,
        "tribunal": tribunal,
        "respondent": respondent,
        "filename_year": filename_year,
    }


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "dab.jsonl"
    fields = ["decision_no", "docket_nos", "decision_date", "tribunal", "respondent"]
    have = dict.fromkeys(fields, 0)
    n = mismatched_year = 0
    for r in jsonl.read(Path(path)):
        meta = parse(r["text"], r["id"])
        n += 1
        for f in fields:
            if meta[f]:
                have[f] += 1
        if (meta["decision_date"] and meta["filename_year"]
                and int(meta["decision_date"][:4]) != meta["filename_year"]):
            mismatched_year += 1
    print(f"{path}: {n} records")
    for f in fields:
        print(f"  {f:16} {have[f]:>5} ({have[f]/n:.1%})")
    print(f"  {'year disagrees with filename':16} {mismatched_year} ({mismatched_year/n:.1%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
