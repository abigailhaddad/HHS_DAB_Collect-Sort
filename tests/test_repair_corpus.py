"""Corpus repair, errata, and the index-duplicate audit (2026-11-01).

Every case is a real decision. The faults: the Board's index swapped TB8312 and
CR6510, typed TB5804 as tb58047 in a URL, listed two decisions as DAB942 and
two as TB8762; 252 ALJ rows built before the TB prefix was parsed had no
number, and 250 of those decisions had since been fetched again.
"""
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

import build_dataset
import errata
import repair_corpus

ROOT = Path(__file__).resolve().parents[1]

FIXES = {
    "index": [
        {"division": "alj", "decision_no": "TB8312", "url_contains": "alj-cr6510",
         "url": "https://example/2024/alj-tb8312/index.html"},
        {"division": "dab", "decision_no": "942", "year": 1987,
         "url_contains": "dab924.html", "set_decision_no": "924"},
        {"division": "alj", "decision_no": "CR3031", "year": 2014,
         "url_contains": "2014/cr3031.pdf", "skip": True},
    ],
    "corpus": [
        {"corpus": "alj", "id": "2024.07.22, CR6510, Complete Care at Arbors v. CMS",
         "decision_no": "TB8312"},
    ],
}


def row(id_, no, text, date=None, url=None, source=None, year=None):
    return {**{f.name: None for f in build_dataset.SCHEMA},
            "id": id_, "corpus": "alj", "decision_no": no, "decision_no_source": source,
            "text": text, "decision_date": date, "source_url": url,
            "year": year or (date.year if date else None)}


def table(rows):
    return pa.Table.from_pylist(rows, schema=build_dataset.SCHEMA)


VAPOR = ("DIY Vapor Supply LLC d/b/a DIY Vapor Supply, DAB TB8312 (2024)\n"
         "DIY Vapor Supply LLC d/b/a DIY Vapor Supply, DAB TB8312 (2024)\n"
         "Department of Health and Human Services")
ARBORS = "Complete Care at Arbors, CR6510 (2024)\nDepartment of Health and Human Services"
SAMEE_OLD = ("Samee Crown, Inc. d/b/a Marathon, DAB TB9003\n(2025)\n"
             " Samee Crown, Inc. d/b/a Marathon, DAB TB9003 (2025)\nDepartment of")
SAMEE_NEW = ("Samee Crown, Inc. d/b/a Marathon, DAB TB9003 (2025)\n\n \n"
             "Department of Health and Human Services")


def test_index_errata_fix_a_swap_a_duplicate_and_drop_a_double_listing():
    rows = [
        {"division": "alj", "year": 2024, "decision_no": "TB8312",
         "url": "https://example/2024/alj-cr6510/index.html"},
        {"division": "dab", "year": 1987, "decision_no": "942",
         "url": "http://example/1987/dab924.html"},
        {"division": "dab", "year": 1988, "decision_no": "942",
         "url": "http://example/1988/dab942.html"},
        {"division": "alj", "year": 2013, "decision_no": "CR3031",
         "url": "http://example/2013/cr3031.pdf"},
        {"division": "alj", "year": 2014, "decision_no": "CR3031",
         "url": "http://example/2014/cr3031.pdf"},
    ]
    out, fixed = errata.apply_to_index(rows, FIXES)
    assert fixed == 3
    assert out[0]["url"].endswith("alj-tb8312/index.html")
    assert [r["decision_no"] for r in out[1:3]] == ["924", "942"]
    assert [r["year"] for r in out if r["decision_no"] == "CR3031"] == [2013]


def test_a_stale_erratum_says_so(capsys):
    errata.apply_to_index([], FIXES)
    assert "matched 0 rows" in capsys.readouterr().out


def test_repair_applies_errata_renumbers_and_drops_the_older_copy():
    t = table([
        row("2024.07.22, CR6510, Complete Care at Arbors v. CMS", "CR6510", VAPOR,
            dt.date(2024, 7, 23), source="filename"),
        row("2024_alj-cr6510", "CR6510", ARBORS, dt.date(2024, 7, 22),
            url="https://example/2024/alj-cr6510/index.html", source="index"),
        row("2025.01.24, TB9003, CTP v. Samee Crown, Inc. d_b_a Marathon", None,
            SAMEE_OLD, dt.date(2025, 1, 24)),
        row("2025_alj-tb9003", "TB9003", SAMEE_NEW, None,
            url="https://example/2025/alj-tb9003/index.html", source="index", year=2025),
    ])
    new, rep = repair_corpus.repair(t, "alj", FIXES)
    got = {r["id"]: r for r in new.to_pylist()}
    assert got["2024.07.22, CR6510, Complete Care at Arbors v. CMS"]["decision_no"] == "TB8312"
    assert got["2024_alj-cr6510"]["decision_no"] == "CR6510"
    # Same number, same caption, one fetched from the index: one decision.
    assert "2025.01.24, TB9003, CTP v. Samee Crown, Inc. d_b_a Marathon" not in got
    # ...and the date the kept copy lacked comes over from the dropped one.
    assert got["2025_alj-tb9003"]["decision_date"] == dt.date(2025, 1, 24)
    assert len(rep["renumbered_from_filename"]) == 1
    assert rep["needs_review"] == [] and rep["duplicates_unresolved"] == []
    again, rep2 = repair_corpus.repair(new, "alj", FIXES)
    assert not repair_corpus.changed(rep2) and again.num_rows == new.num_rows


def test_two_decisions_sharing_a_number_are_reported_not_merged():
    # The index's two TB8762s, before the Sonia and Ami erratum existed.
    t = table([
        row("2025.02.05, TB8762, CTP v. Sonia and Ami, Inc.", None,
            "Sonia and Ami, Inc. d/b/a Charlie's Food Mart, DAB TB9064 (2025)",
            dt.date(2025, 2, 5)),
        row("2025_alj-tb8762", "TB8762",
            "MNG Halsted Mart Inc. d/b/a Citgo, DAB TB8762 (2025)", dt.date(2025, 1, 13),
            url="https://example/2025/alj-tb8762/index.html", source="index"),
    ])
    new, rep = repair_corpus.repair(t, "alj", {"index": [], "corpus": []})
    assert new.num_rows == 2
    assert len(rep["duplicates_unresolved"]) == 1
    assert rep["needs_review"][0]["decision_says"] == "TB9064"


def test_the_number_check_reads_only_the_leading_citation():
    # An Appellate decision opens with the Board's header and cites the ALJ
    # decision it reviews further down; that citation is not its number.
    appellate = ("Department of Health and Human Services DEPARTMENTAL APPEALS BOARD "
                 "Appellate Division Robert Young, M.D. Docket No. A-11-1, upholding "
                 "Robert Young, M.D., CR2227 (2011)")
    assert repair_corpus.leading_citation(appellate) is None
    assert repair_corpus.leading_citation(VAPOR) == ("TB8312", 2024)
    # The print drops the series prefix sometimes, and a reconsideration's R.
    assert repair_corpus.same_number("8956", "TB8956")
    assert repair_corpus.same_number("725", "725R")
    assert not repair_corpus.same_number("TB5804", "TB58047")


def test_audit_matches_a_twice_listed_number_on_year(tmp_path):
    # Invented numbers, so errata.json's real entries don't touch them: the
    # shape is the DAB942 case, where a 1987 decision held under 942 made the
    # 1988 DAB 942 look present.
    index = tmp_path / "index.jsonl"
    index.write_text("".join(json.dumps(r) + "\n" for r in [
        {"division": "dab", "year": 1987, "decision_no": "9942",
         "caption": "1987.12.11 DAB9942 One", "url": "http://e/1987/dab9924.html"},
        {"division": "dab", "year": 1988, "decision_no": "9942",
         "caption": "1988.03.23 DAB9942 Two", "url": "http://e/1988/dab9942.html"},
    ]))
    corpus = tmp_path / "dab.parquet"
    pq.write_table(pa.table({"decision_no": ["9942"], "corpus": ["dab"], "year": [1987]}),
                   corpus)
    missing = tmp_path / "missing.jsonl"
    r = subprocess.run([sys.executable, "audit_completeness.py", str(index), str(corpus),
                        "--missing-out", str(missing)], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "lists 1 number(s) more than once" in r.stdout
    years = [json.loads(l)["year"] for l in missing.read_text().splitlines()]
    assert years == [1988]
