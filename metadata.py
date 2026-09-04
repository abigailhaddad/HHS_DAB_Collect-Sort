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

import json
import re
import sys
from datetime import date

import clean

MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}
# OCR of the older scans mangles month names; these are the ones actually seen.
MONTH_FIXES = {"harch": "march", "sep": "september", "jan": "january",
               "feb": "february", "mar": "march", "apr": "april",
               "jun": "june", "jul": "july", "aug": "august",
               "oct": "october", "nov": "november", "dec": "december"}

# "DATE: April 7, 2006" / "Date~ SEP. 28, 1978" / a bare "June 30, 2015" line.
DATE_RE = re.compile(
    r"(?:date\s*[:~.]?\s*)?"
    r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})\s*,\s*(\d{4})\b", re.IGNORECASE)
DATE_LABELLED_RE = re.compile(
    r"date\s*[:~.]?\s*([A-Za-z]{3,9})\.?\s+(\d{1,2})\s*,\s*(\d{4})", re.IGNORECASE)

# "Decision No. 2024", "Decision No. CR1723", "DAB No. 3117", "DAB CR6187"
DECISION_RE = re.compile(
    r"decision\s+nos?\.?\s*((?:CR)?\s*\d{1,5})", re.IGNORECASE)
DAB_NO_RE = re.compile(r"\bDAB\s+(?:No\.\s*)?((?:CR)?\s*\d{1,5})", re.IGNORECASE)

# "Docket No. C-07-429", "Docket Nos. 77-7, 77-8, and 77-9", "Docket No. A-15-44"
DOCKET_RE = re.compile(
    r"docket\s+nos?\.?\s*([A-Za-z0-9][A-Za-z0-9\-‐-―]*"
    r"(?:\s*(?:,|and)\s*[A-Za-z0-9][A-Za-z0-9\-‐-―]*)*)", re.IGNORECASE)

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


def _to_date(mon: str, day: str, year: str) -> str | None:
    m = mon.lower().rstrip(".")
    m = MONTH_FIXES.get(m, m)
    idx = MONTHS.get(m)
    if idx is None:
        for name, i in MONTHS.items():          # tolerate "Septeraber"-class OCR
            if len(m) >= 3 and name.startswith(m[:3]):
                idx = i
                break
    if idx is None:
        return None
    try:
        return date(int(year), idx, int(day)).isoformat()
    except ValueError:
        return None


def _norm_no(raw: str) -> str:
    return re.sub(r"\s+", "", raw).upper()


def parse(text: str, record_id: str = "") -> dict:
    """Pull header fields out of one decision. Missing fields come back None."""
    body = clean.clean_guarded(text)[0]
    head = body[:4000]                   # the header always sits in the first pages

    decision_no = None
    for rx in (DECISION_RE, DAB_NO_RE):
        m = rx.search(head)
        if m:
            decision_no = _norm_no(m.group(1))
            break

    dockets = []
    m = DOCKET_RE.search(head)
    if m:
        dockets = [_norm_no(d) for d in re.split(r"\s*(?:,|and)\s*", m.group(1)) if d.strip()]

    # Prefer the date on the labelled "DATE:" line; fall back to the first
    # date-looking string in the header, then to the filename.
    decision_date = None
    for rx in (DATE_LABELLED_RE, DATE_RE):
        for m in rx.finditer(head):
            decision_date = _to_date(*m.groups())
            if decision_date:
                break
        if decision_date:
            break

    tribunal = next((name for name, rx in TRIBUNALS if rx.search(head)), None)
    respondent = next((name for name, rx in RESPONDENTS if rx.search(head)), None)

    fm = re.match(r"\D*(\d{4})[.\s]*(\d{2})?[.\s]*(\d{2})?", record_id)
    filename_year = int(fm.group(1)) if fm else None

    return {
        "decision_no": decision_no,
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
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
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
