"""Hand-checked corrections to the Board's index and to corpus rows.

The Board's index is the best source of a decision's number this pipeline has
-- the header parses wrong or not at all for ~30% of decisions (see
build_dataset.py) -- but it is typed by hand and it has errors. Found on
2026-11-01, all invisible to every existing check:

  * TB8312 and CR6510 linked to each other's pages, so a CR6510 row held the
    DIY Vapor Supply tobacco decision and TB8312 was in the corpus under no
    number of its own;
  * two decisions listed as DAB942 and two as TB8762, so the audit counted the
    1988 Florida DAB 942 as present because a 1987 decision sat under its
    number, and the daily run re-fetched two "missing" decisions every day and
    merged neither.

Each correction lives in errata.json with the evidence for it. Nothing here
guesses: an entry is a reviewed fact, and anything a check merely suspects is
reported (repair_corpus.py) for someone to add here or not.
"""
from __future__ import annotations

import json
from pathlib import Path

ERRATA = Path(__file__).with_name("errata.json")


def load(path: Path = ERRATA) -> dict:
    if not path.exists():
        return {"index": [], "corpus": [], "number_check_ok": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"index": data.get("index", []), "corpus": data.get("corpus", []),
            "number_check_ok": data.get("number_check_ok", [])}


def _matches(entry: dict, row: dict) -> bool:
    if entry["division"] != row.get("division"):
        return False
    if entry["decision_no"] != row.get("decision_no"):
        return False
    if "year" in entry and entry["year"] != row.get("year"):
        return False
    return entry["url_contains"] in (row.get("url") or "")


def apply_to_index(rows: list[dict], errata: dict | None = None) -> tuple[list[dict], int]:
    """The index rows with errata applied, and how many were corrected.

    An entry moves a row to the right URL (a swapped link), gives it the right
    number (a duplicate or a typo), or drops it (skip: the same decision
    listed twice). Each entry must match exactly one
    row; one that matches none means the Board fixed its index, or the entry is
    stale, and it says so rather than passing silently.
    """
    errata = errata if errata is not None else load()
    out, fixed = [], 0
    used = [0] * len(errata["index"])
    for row in rows:
        row = dict(row)
        for i, e in enumerate(errata["index"]):
            if _matches(e, row):
                used[i] += 1
                fixed += 1
                if e.get("skip"):
                    # A duplicate listing of a decision held under another.
                    row = None
                    break
                if "url" in e:
                    row["url"] = e["url"]
                if "set_decision_no" in e:
                    row["decision_no"] = e["set_decision_no"]
                row["erratum"] = True
                break
        if row is not None:
            out.append(row)
    for e, n in zip(errata["index"], used):
        if n != 1:
            print(f"errata.json: index entry {e['division']} {e['decision_no']} "
                  f"({e['url_contains']}) matched {n} rows, expected 1 -- has the "
                  f"Board corrected its index?", flush=True)
    return out, fixed


def corpus_overrides(corpus: str, errata: dict | None = None) -> dict[str, dict]:
    """{row id: fields to set} for one corpus."""
    errata = errata if errata is not None else load()
    return {e["id"]: {k: v for k, v in e.items()
                      if k in ("decision_no", "source_url", "drop")}
            for e in errata["corpus"] if e["corpus"] == corpus}


def number_check_ok(corpus: str, errata: dict | None = None) -> set[str]:
    """Row ids whose number the check disputes but a person has confirmed --
    the decision's own citation carries the Board's typo."""
    errata = errata if errata is not None else load()
    return {e["id"] for e in errata.get("number_check_ok", []) if e["corpus"] == corpus}
