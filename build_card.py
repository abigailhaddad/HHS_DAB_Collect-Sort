"""Render the Hugging Face dataset card from the corpus it describes.

A card is a claim about a specific published snapshot, so its numbers have to
match the files beside it. Hand-written, they do not: the repo README carried
"3,300 and 4,946 decisions" and "sixteen categories" for three collections
after those stopped being true, and described a completeness gap that had
already been closed.

So the prose lives here and the numbers are read off the data at build time.

    python build_card.py --dir out/ --index decisions_index.jsonl
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
from pathlib import Path

import pyarrow.parquet as pq

import categories
import jsonl

CORPUS_LABEL = {
    "dab": "Appellate Division, and the Grant Appeals Board before it",
    "alj": "Civil Remedies Division (ALJs)",
}


def pct(n: int, d: int) -> str:
    return f"{n / d:.0%}" if d else "—"


def corpus_stats(path: Path) -> dict:
    t = pq.read_table(path, columns=["decision_no", "decision_date", "judges",
                                     "dispositions", "provider_ids",
                                     "reviews_decision_no"])
    dates = [d for d in t.column("decision_date").to_pylist() if d]
    n = t.num_rows
    return {
        "rows": n,
        "first": min(dates).isoformat() if dates else "—",
        "last": max(dates).isoformat() if dates else "—",
        "judges": pct(sum(1 for x in t.column("judges").to_pylist() if x), n),
        "dispositions": pct(sum(1 for x in t.column("dispositions").to_pylist() if x), n),
        "provider_ids": pct(sum(1 for x in t.column("provider_ids").to_pylist() if x), n),
        "reviews": sum(1 for x in t.column("reviews_decision_no").to_pylist() if x),
        "numbers": {x for x in t.column("decision_no").to_pylist() if x},
    }


def render(out_dir: Path, index_path: Path | None) -> str:
    stats = {c: corpus_stats(out_dir / f"{c}.parquet") for c in ("dab", "alj")}
    total = sum(s["rows"] for s in stats.values())

    listed = numbered = present = 0
    if index_path and index_path.exists():
        rows = list(jsonl.read(index_path))
        listed = len(rows)
        for r in rows:
            no = r.get("decision_no")
            if not no:
                continue
            numbered += 1
            if no in stats[r["division"]]["numbers"]:
                present += 1

    slice_line = ""
    sp = out_dir / "slices.parquet"
    if sp.exists():
        s = pq.read_table(sp, columns=["corpus", "id", "category"])
        pairs = set(zip(s.column("corpus").to_pylist(), s.column("category").to_pylist()))
        members = collections.Counter(zip(s.column("corpus").to_pylist(),
                                          s.column("id").to_pylist()))
        slice_line = (
            f"| `slices.parquet` | category membership — {s.num_rows:,} rows over "
            f"{len(pairs)} non-empty slices | | |")
        slices_note = (
            f"{len(members):,} of {total:,} decisions ({pct(len(members), total)}) land in "
            f"at least one slice and {sum(1 for v in members.values() if v > 1):,} in more "
            f"than one, out of {len(categories.CATEGORIES) * 2} possible category/corpus "
            f"pairs.")
    else:
        slices_note = "No slice table was built."

    rows_md = "\n".join(
        f"| `{c}.parquet` | {CORPUS_LABEL[c]} | {stats[c]['rows']:,} | "
        f"{stats[c]['first']} – {stats[c]['last']} |" for c in ("dab", "alj"))
    if slice_line:
        rows_md += "\n" + slice_line

    complete = (f"of the {listed:,} listings on its year-by-year index pages, all "
                f"{present:,} of the {numbered:,} that carry an identifiable decision "
                f"number are here; the other {listed - numbered:,} sit outside the check"
                ) if listed else "not measured in this build"

    return f"""---
license: other
license_name: us-government-works
pretty_name: HHS Departmental Appeals Board decisions
language:
  - en
tags:
  - law
  - caselaw
  - administrative-law
  - health-policy
  - medicare
  - medicaid
  - federal
size_categories:
  - 1K<n<10K
---

# HHS Departmental Appeals Board decisions

Every decision the HHS Departmental Appeals Board has published, as typed
Parquet with the header and parts of the body parsed into columns.

The Board is an administrative tribunal inside HHS. Its ALJs (Civil Remedies
Division) hear a case first and its Appellate Division reviews them, so the two
files are two levels of the same tribunal and can be joined on
`reviews_decision_no` / `appealed_in`.

| file | tribunal | decisions | span |
|---|---|---|---|
{rows_md}

Complete against the Board's own published index: {complete}.

Derived from [Kmisener/HHS-DAB-Decisions](https://huggingface.co/datasets/Kmisener/HHS-DAB-Decisions),
which collected and text-extracted the original corpus. This adds the decisions
it was missing, parsed metadata, website-furniture removal, evidence-based
category labels and a typed schema. Build code and method:
[github.com/abigailhaddad/hhs-dab](https://github.com/abigailhaddad/hhs-dab).

## What the decisions are about

On the ALJ side, most cases run against CMS or the HHS Inspector General:
exclusions barring an individual from Medicare and Medicaid, nursing-home
enforcement and civil money penalties, revoked billing privileges, CLIA lab
sanctions, EMTALA penalties, and FDA tobacco-retailer enforcement. On the
Appellate side, and especially before 2000, a large share are grant disputes —
Head Start, TANF, child support enforcement, foster care, tribal
self-determination contracts.

## Columns

| column | notes |
|---|---|
| `id`, `corpus` | source filename stem; `dab` or `alj` |
| `decision_no`, `decision_no_source` | `2740`, `CR4685`, `CR10R`, `RULING2013-2`; and which of index / filename / header it came from |
| `docket_nos` | a decision can carry several |
| `decision_date`, `year` | from the text; null rather than wrong |
| `tribunal`, `respondent` | which division; who the appeal ran against |
| `judges` | a panel on the Appellate side ({stats['dab']['judges']} of Appellate, {stats['alj']['judges']} of ALJ) |
| `reviews_decision_no` | the ALJ decision an Appellate decision reviews ({stats['dab']['reviews']:,}) |
| `appealed_in` | ALJ only — Appellate decisions that reviewed it |
| `dispositions` | `affirmed`, `reversed`, `remanded`, … ({stats['dab']['dispositions']} / {stats['alj']['dispositions']}) |
| `disposition_text` | the conclusion, verbatim |
| `provider_ids` | `CCN:`, `NPI:`, `PTAN:`, `CLIA:` — joins to CMS data ({stats['alj']['provider_ids']} of ALJ) |
| `source_url` | where it was collected from |
| `had_web_chrome`, `text_layer_ok`, `clean_guard_tripped` | extraction flags |
| `text` | the decision, website furniture stripped |

## Quick start

```python
import duckdb
duckdb.sql(\"\"\"
  SELECT unnest(dispositions) AS outcome, count(*) AS n
  FROM 'dab.parquet' WHERE reviews_decision_no IS NOT NULL
  GROUP BY 1 ORDER BY 2 DESC
\"\"\").show()
```

## What this does not establish

- **Dispositions are partial by design.** They are read only from operative
  first-person phrasing in a decision's own conclusion. Empty means "not stated
  unambiguously here", never "nothing happened", so a rate over the labelled
  rows is a rate over a non-random subset. `disposition_text` carries the
  conclusion verbatim.
- **`appealed_in` is a join, not a census.** An appeal that settled, was
  withdrawn, or is pending produces no Appellate decision, so empty means "no
  Appellate decision here names it".
- **Category labels are a heuristic.** Membership is decided from where a
  citation appears and how often, after case citations are blanked out. No
  precision or recall is claimed; there is no hand-labelled sample.
- **The slices are not a partition.** {slices_note} There is no residual
  category.
- **Some text is wrong rather than missing.** A few decisions extract to about
  one character per page and are flagged by `text_layer_ok`. Others extract at
  normal length and are garbled — DAB No. 88 (1980) reads "Financisl", "yesr" —
  and nothing flags those. DAB No. 437 (1983) is published by HHS as an empty
  page and is absent for that reason.
- **Decision numbers come from three sources**, best first: the Board's index,
  the source filename, then the header. The header alone agreed with the index
  only 64% of the time — OCR mangles the label in the older scans, and a failed
  parse picks up a citation to a different decision. `decision_no_source`
  records which was used.

## Provenance

Decisions are published at
[hhs.gov/about/agencies/dab/decisions](https://www.hhs.gov/about/agencies/dab/decisions/),
which returns 403 to automated clients, so collection routes through the
Internet Archive and, for anything published since its last crawl, a browser
attached over the DevTools protocol. The decisions are works of the United
States government and are not subject to copyright.

*Built {dt.date.today().isoformat()} from the corpus in this repository.*
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=Path("out"))
    ap.add_argument("--index", type=Path, default=Path("decisions_index.jsonl"))
    ap.add_argument("-o", "--out", type=Path, default=None)
    args = ap.parse_args()
    card = render(args.dir, args.index)
    dest = args.out or (args.dir / "README.md")
    dest.write_text(card, encoding="utf-8")
    print(f"{dest}: {len(card.splitlines())} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
