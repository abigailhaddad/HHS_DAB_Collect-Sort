"""Bring the rows already in the corpus up to the current parse, and check them.

daily_update.py only ever appends: a row built by an older version of this
pipeline keeps whatever that version gave it. On 2026-11-01 that had left 252
ALJ rows with no decision_no -- tobacco (TB) decisions from the original
corpus, built before decision_no_from_text read the TB prefix. The audit could
not see them, so it called those decisions missing and the daily run fetched
each one again: 250 decisions were in the published ALJ file twice, ~4% of
it, concentrated in 2019-2026.

Run before the audit, every day. Idempotent; writes nothing if nothing changes.

  1. errata.json corrections by row id;
  2. decision_no filled from the filename for rows that have none, with the
     same metadata.decision_no_from_id a fresh build uses;
  3. a row dropped only when another row holds the same number, the same
     decision date and the same opening caption, and the row kept is the one
     fetched from the Board's index (it has a source_url). Anything short of
     that is reported, not dropped -- two different decisions have shared a
     number in this corpus before;
  4. a check of every row's number against the citation the decision opens
     with ("DIY Vapor Supply LLC ..., DAB TB8312 (2024)"). Only that strict
     leading form is used, because the header in general parses wrong too
     often to trust (build_dataset.py). A disagreement errata.json doesn't
     explain is reported for review, not changed.

    python repair_corpus.py out/alj.parquet out/dab.parquet --report repair_report.json
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

import errata
import metadata
from audit_completeness import norm

# The citation a decision opens with: caption, then "DAB TB8312 (2024)",
# "CR6510 (2024)" or "DAB No. 924 (1987)". Anchored at the start of the text,
# so a later citation to a different decision -- which is what made the
# header unreliable -- cannot match.
LEADING_CITATION = re.compile(
    r"^\s*(?P<party>.{2,200}?),\s+(?:DAB\s+)?(?:No\.?\s*)?"
    r"(?P<num>(?:CR|TB|C|A|M|T)?-?\d{1,5}[A-Z]?)\s*\((?P<year>(?:19|20)\d{2})\)")


def _head(text: str | None) -> str:
    # All whitespace to one space: the older copies wrap the caption
    # ("Woodstock Vape and Glass\nGallery, DAB TB4136 (2019)").
    return re.sub(r"\s+", " ", (text or "")[:400])


# A citation is only the decision's own when it comes before the Board's
# letterhead. Past it, the first "(2011)" is a citation to another decision --
# an Appellate decision citing the ALJ decision it reviews ("...upholding Robert
# Young, M.D., CR2227 (2011)") -- which is the failure that makes the header
# untrustworthy in general.
NOT_A_CAPTION = re.compile(
    r"DEPARTMENTAL\s+APPEALS\s+BOARD|Department\s+of\s+Health\s+and\s+Human|Docket\s+No",
    re.IGNORECASE)


def _leading(text: str | None):
    m = LEADING_CITATION.match(_head(text))
    return None if (not m or NOT_A_CAPTION.search(m["party"])) else m


def leading_citation(text: str | None) -> tuple[str, int] | None:
    m = _leading(text)
    return (m["num"], int(m["year"])) if m else None


def same_number(printed: str | None, stored: str | None) -> bool:
    """Whether a printed citation names the stored number.

    The print sometimes drops the series prefix ("DAB 8956 (2025)" for TB8956)
    and a reconsideration is stored with an R ("725R") its text doesn't carry.
    """
    a, b = norm(printed), norm(stored)
    if not a or not b:
        return True
    if a == b or (b.endswith("R") and b[:-1] == a):
        return True
    digits = lambda s: re.sub(r"^[A-Z]+", "", s)
    return a.isdigit() and digits(b) == a


def caption_key(text: str | None) -> str:
    """The opening of a decision, for telling two copies of one decision from
    two decisions that share a number: the leading citation (caption, number,
    year) where there is one, else the first 40 letters and digits. Not a
    fixed-length prefix alone -- the older copies repeat the caption line, so
    40 characters into "Samee Crown, Inc. d/b/a Marathon, DAB TB9003 (2025)"
    one copy reads "Samee" again and the other "Department"."""
    m = _leading(text)
    opening = m.group(0) if m else (text or "")[:200]
    return re.sub(r"[^a-z0-9]", "", opening.lower())[:120 if m else 40]


def repair(table: pa.Table, corpus: str, fixes: dict | None = None) -> tuple[pa.Table, dict]:
    fixes = fixes if fixes is not None else errata.load()
    overrides = errata.corpus_overrides(corpus, fixes)
    rows = table.to_pylist()
    report = {"corpus": corpus, "errata_applied": [], "renumbered_from_filename": [],
              "duplicates_dropped": [], "duplicates_unresolved": [], "needs_review": []}

    for r in rows:
        o = overrides.get(r["id"])
        if o and (r["decision_no"] != o["decision_no"]
                  or r["decision_no_source"] != "errata"
                  or ("source_url" in o and r["source_url"] != o["source_url"])):
            report["errata_applied"].append(
                {"id": r["id"], "from": r["decision_no"], "to": o["decision_no"]})
            r["decision_no"], r["decision_no_source"] = o["decision_no"], "errata"
            if "source_url" in o:
                r["source_url"] = o["source_url"]
        if not r["decision_no"]:
            n = metadata.decision_no_from_id(r["id"])
            if n:
                r["decision_no"], r["decision_no_source"] = n, "filename"
                report["renumbered_from_filename"].append({"id": r["id"], "decision_no": n})

    groups = collections.defaultdict(list)
    for i, r in enumerate(rows):
        if r["decision_no"]:
            groups[norm(r["decision_no"])].append(i)
    drop = set()
    for number, idx in groups.items():
        if len(idx) < 2:
            continue
        keepers = [i for i in idx if rows[i]["source_url"]]
        if len(keepers) != 1:
            report["duplicates_unresolved"].append(
                {"decision_no": number, "ids": [rows[i]["id"] for i in idx],
                 "why": f"{len(keepers)} rows fetched from the index"})
            continue
        k = rows[keepers[0]]
        for i in idx:
            if i == keepers[0]:
                continue
            r = rows[i]
            # A missing date doesn't disagree: rows fetched from the index
            # sometimes parse to none while the older copy has one.
            dates_agree = (r["decision_date"] == k["decision_date"]
                           or r["decision_date"] is None or k["decision_date"] is None)
            if dates_agree and caption_key(r["text"]) == caption_key(k["text"]):
                if k["decision_date"] is None and r["decision_date"] is not None:
                    k["decision_date"] = r["decision_date"]
                drop.add(i)
                report["duplicates_dropped"].append(
                    {"decision_no": number, "dropped": r["id"], "kept": k["id"]})
            else:
                report["duplicates_unresolved"].append(
                    {"decision_no": number, "ids": [r["id"], k["id"]],
                     "why": "same number, different date or opening -- two decisions?"})

    kept = [r for i, r in enumerate(rows) if i not in drop]
    confirmed = errata.number_check_ok(corpus, fixes)
    for r in kept:
        if r["id"] in confirmed:
            continue
        cite = leading_citation(r["text"])
        if cite and (not r["year"] or cite[1] == r["year"]) \
                and not same_number(cite[0], r["decision_no"]):
            report["needs_review"].append(
                {"id": r["id"], "decision_no": r["decision_no"],
                 "decision_says": cite[0], "source": r["decision_no_source"]})

    return pa.Table.from_pylist(kept, schema=table.schema), report


def changed(report: dict) -> bool:
    return bool(report["errata_applied"] or report["renumbered_from_filename"]
                or report["duplicates_dropped"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("parquets", type=Path, nargs="+")
    ap.add_argument("--report", type=Path, default=Path("repair_report.json"))
    args = ap.parse_args()

    reports, any_change = [], False
    for p in args.parquets:
        t = pq.read_table(p)
        corpus = t.column("corpus").to_pylist()[0] if t.num_rows else p.stem
        new, rep = repair(t, corpus)
        reports.append(rep)
        print(f"{corpus}: {len(rep['errata_applied'])} errata applied, "
              f"{len(rep['renumbered_from_filename'])} renumbered from filename, "
              f"{len(rep['duplicates_dropped'])} duplicate rows dropped "
              f"({t.num_rows} -> {new.num_rows}), "
              f"{len(rep['duplicates_unresolved'])} duplicate numbers unresolved, "
              f"{len(rep['needs_review'])} numbers the decision's own citation disputes",
              flush=True)
        for key in ("duplicates_unresolved", "needs_review"):
            for item in rep[key]:
                print(f"  NEEDS REVIEW ({key}): {item}", flush=True)
        if changed(rep):
            any_change = True
            pq.write_table(new, p, compression="zstd", compression_level=9)
    args.report.write_text(json.dumps(reports, indent=1, ensure_ascii=False, default=str))
    print(f"report -> {args.report}; corpus {'rewritten' if any_change else 'unchanged'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
