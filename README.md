# HHS DAB decisions

Every published decision of the HHS Departmental Appeals Board, collected from
the Board's own year-by-year index and sorted by the statutory basis the case
was decided under. Two tribunals: the Appellate Division and its predecessor
Grant Appeals Board (3,300 decisions, 1974 to present) and the Civil Remedies
Division ALJs (4,946 decisions, 1981 to present).

PDFs and HTML in, typed Parquet out, with the header parsed into columns you can
filter on and sixteen category slices cut by legal basis.

## Where the data comes from

Decisions are published at
[hhs.gov/about/agencies/dab/decisions](https://www.hhs.gov/about/agencies/dab/decisions/).
The whole of www.hhs.gov sits behind an Akamai edge block that returns 403 to
automated clients — every path, any user agent, `robots.txt` included — so
collection goes through the Internet Archive instead. `collect_index.py` reads the archived per-year index
page for each division, which lists every decision the Board published that year
with a link to it, and that list is what makes a completeness check possible:
the corpus gets diffed against the publisher's own index rather than against a
guess about which decision numbers ought to exist.

Older decisions are served as HTML (`board-decisions/1995/dab1550.html`) and
newer ones as PDF (`alj-decisions/2016/cr4685.pdf`).

## Running it

```bash
pip install -r requirements.txt      # -r requirements-ocr.txt for --ocr

python collect_index.py --out decisions_index.jsonl   # what the Board published
python extract.py ./decisions -o dab.jsonl           # PDF and HTML -> text
python build_dataset.py dab.jsonl --corpus dab -o out/
python slice_jsonl.py dab.jsonl out/ --all           # -> 16 category slices
python build_manifests.py --dir out/

# what is published but missing, then fetch it
python audit_completeness.py decisions_index.jsonl out/*.parquet
python fetch_missing.py missing.jsonl --out-dir decisions/

# anything published since the Archive last crawled: start Chrome yourself,
# then attach to it (see fetch_via_browser.py)
python fetch_via_browser.py missing_2026.jsonl --out-dir decisions/

python verify.py decisions/                          # did we actually get them?
python run_checks.py && python -m pytest tests/      # bug ledger + test suite
```

`categories.yaml` holds the sixteen categories — pattern, description and legal
citation in one table. Adding a category is a data edit; the slicer, the counter
and the manifest all read from it, and a category missing any of the three is
refused at load rather than shipping a slice with a blank legal basis.

The other modules divide up as: `archive.py` (everything that talks to the
Internet Archive), `jsonl.py` (record IO), `extract.py` (files to text),
`clean.py` (website furniture), `metadata.py` (the header), `label.py`
(category membership).

The corpora are not committed. `.gitignore` keeps `*.jsonl` and `*.parquet` out
of the repo; 284 MB of JSONL becomes 53 MB of zstd Parquet, which is the
difference between a dataset you can range-query over HTTP and one you have to
download.

## What the data doesn't tell you

- **A 200 is not evidence of a decision.** The Akamai block, the Archive's own
  miss page and a redirect to the section landing page all return 200 with a
  full HTML skeleton and no decision in it. `verify.py` gives each fetched file
  a named verdict — OK, CHALLENGE, ARCHIVE_MISS, NOT_A_DECISION, THIN, EMPTY —
  so that checking is a command rather than something rewritten ad hoc each
  time. CHALLENGE is a retry after re-solving in the browser, not missing data.
- **The Archive lags.** Its most recent crawl of a page can be months old and
  Save Page Now needs an account, so anything published since is reachable only
  from a real browser — `fetch_via_browser.py`, attaching to a Chrome you start
  yourself. `check_index.py` runs daily against a committed baseline and fails
  if any division-year loses decisions, because a collector that quietly returns
  less is the failure this repo keeps having.
- **Completeness is measured, not assumed, and it is not total.** Every
  decision the Board's index lists *and gives an identifiable number to* is in
  the corpus. 307 of its 9,042 listings carry no parseable number and sit
  outside that check entirely. `audit_completeness.py` runs the diff.
- **A category label is a heuristic, not a reading.** `label.py` decides from
  where a citation appears and how often, which is a much better proxy than a
  substring match and is still a proxy. No precision or recall figure is claimed
  anywhere, because there is no hand-labelled sample to compute one from.
- **The slices are not a partition.** 1,393 of 9,228 decisions (15%) land in at
  least one slice; 9 land in more than one; there is no residual category. Four
  category/corpus pairs are empty, `samhsa_otp_cert` in both.
- **A quarter of the corpus was captured from the web page, not the file.** The
  HHS breadcrumb, the "official website" banner and the rest come with it — 19%
  of Appellate Division and 42% of ALJ decisions. `clean.py` strips it.
- **Some text layers are wrong rather than missing.** Three decisions extract to
  about one character per page; DAB No. 88 (1980) extracts at normal length and
  reads "Financisl", "yesr", "t:rsotee's". Only the first kind is detected.
- **There is no outcome field.** The header parses; the disposition and any
  exclusion period do not.

[LIMITATIONS.md](./LIMITATIONS.md) has the detail and the numbers.

## How categories are assigned

[METHODS.md](./METHODS.md). Short version: matching a citation anywhere in the
full text answers a different question than the category name asks, because the
Board's standing cite on documenting costs is a Head Start case, because
decisions enumerate provisions they are not applying, and because petitioners
cite provisions they then lose on. `label.py` blanks out case citations and
requires the surviving matches to carry weight. Across the twenty-one slices
that were published from a plain substring match, 889 records become 749.

## License

Code under the [MIT License](./LICENSE.txt). The decisions are works of the
United States government and are not subject to copyright.
