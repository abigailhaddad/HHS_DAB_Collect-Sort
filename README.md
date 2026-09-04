# HHS DAB decisions

Every published decision of the HHS Departmental Appeals Board — an
administrative tribunal inside HHS whose ALJs hear a case first and whose
Appellate Division reviews them. PDFs and HTML in, typed Parquet out, with the
header and parts of the body parsed into columns and 38 category slices cut by
legal basis.

**This is a cleanup of [KMisener90/HHS_DAB_Collect-Sort](https://github.com/KMisener90/HHS_DAB_Collect-Sort)**,
which assembled the original corpus and wrote the first version of the
extraction and slicing scripts. That work is the reason this exists.

| | decisions | span |
|---|---|---|
| Appellate Division, and the Grant Appeals Board before it | 3,309 | 1974-03-07 – 2026-08-21 |
| Civil Remedies Division (ALJs) | 6,082 | 1985-05-14 – 2026-07-28 |

## What this adds

- **A collector, and a completeness check with something to check against.**
  `collect_index.py` reads the Board's own year-by-year index, so the corpus is
  diffed against the publisher's list rather than a guess about which decision
  numbers ought to exist. That found 1,773 published decisions the corpus did
  not have — all of 1999–2006 on the ALJ side, and most of 2026.
- **Membership by evidence rather than substring.** Matching a citation anywhere
  in the full text answers a different question than a category name asks; see
  [METHODS.md](./METHODS.md).
- **Parsed fields**: decision and docket numbers, date, tribunal, respondent,
  judges, the ALJ decision an Appellate decision reviews, provider identifiers,
  and a conservative disposition.
- **Website furniture stripped.** Some decisions were captured from the web page
  rather than the file and carry the site's navigation as prose.
- **Tests.** `run_checks.py` is a case per bug found by hand; `tests/` covers
  module contracts, an end-to-end run and integrity checks over a built corpus.

## Where the data comes from

Decisions are published at
[hhs.gov/about/agencies/dab/decisions](https://www.hhs.gov/about/agencies/dab/decisions/).
The whole of www.hhs.gov returns 403 to automated clients — every path, any user
agent, `robots.txt` included — so collection routes through the Internet
Archive, and through a browser you start yourself for anything published since
its last crawl. Older decisions are served as HTML, newer ones as PDF, and since
2017 each decision has its own page.

## Running it

```bash
pip install -r requirements.txt      # -r requirements-ocr.txt for --ocr

python collect_index.py --out decisions_index.jsonl   # what the Board published
python extract.py ./decisions -o dab.jsonl            # PDF and HTML -> text
python build_dataset.py dab.jsonl --corpus dab -o out/
python slice_jsonl.py dab.jsonl out/ --all            # -> 38 category slices
python build_manifests.py --dir out/
python link_corpora.py out/dab.parquet out/alj.parquet # who appealed what

# what is published but missing, then fetch it
python audit_completeness.py decisions_index.jsonl out/*.parquet
python fetch_missing.py missing.jsonl --out-dir decisions/
python fetch_via_browser.py missing.jsonl --out-dir decisions/   # needs your Chrome

python verify.py decisions/                           # did we actually get them?
python run_checks.py && python -m pytest tests/
```

`categories.yaml` holds the 38 categories — pattern, description and legal
citation in one table, and a category missing any of the three is refused at
load. The rest divide up as `archive.py` (the Internet Archive), `extract.py`
(files to text), `clean.py` (website furniture), `metadata.py` (the header),
`fields.py` (the body), `label.py` (category membership), `jsonl.py` (record IO).

The corpora are not committed; `.gitignore` keeps `*.jsonl` and `*.parquet` out.

## What the data doesn't tell you

- **A 200 is not evidence of a decision.** The block page, the Archive's miss
  page and a redirect to the section landing page all return 200 with a full
  HTML skeleton and nothing in it. `verify.py` gives every fetched file a named
  verdict so that checking is a command rather than a habit.
- **Completeness is measured, and it is not total.** All 8,897 index listings
  that carry an identifiable decision number are here. The other 323 sit outside
  that check entirely.
- **Category labels and dispositions are heuristics.** No precision or recall is
  claimed; there is no hand-labelled sample to compute one from. Dispositions
  are empty on most decisions, and empty means "not stated unambiguously here".
- **The slices are not a partition.** 6,061 of 9,391 decisions land in at least
  one of 68; 1,357 land in more than one; there is no residual category.
- **Some text is wrong rather than missing.** Three decisions extract to about
  one character per page and are flagged. Others extract at normal length and
  are garbled — DAB No. 88 (1980) reads "Financisl", "yesr" — and nothing
  flags those.

[LIMITATIONS.md](./LIMITATIONS.md) has the rest, with numbers.

## License

Code under the [MIT License](./LICENSE.txt). The decisions are works of the
United States government and are not subject to copyright.
