# HHS DAB decisions

Every published decision of the HHS Departmental Appeals Board, collected from
the Board's own year-by-year index and sorted by the statutory basis the case
was decided under. Two tribunals: the Appellate Division and its predecessor
Grant Appeals Board (3,300 decisions, 1974 to present) and the Civil Remedies
Division ALJs (4,946 decisions, 1981 to present).

PDFs and HTML in, typed Parquet out, with the header parsed into columns you can
filter on and sixteen category slices cut by legal basis.

## Where the data comes from

Decisions are published on dab.hhs.gov. That site sits behind an Akamai edge
block that returns 403 to everything — the year index pages, the decision files,
even `robots.txt` — regardless of user agent, so collection goes through the
Internet Archive instead. `collect_index.py` reads the archived per-year index
page for each division, which lists every decision the Board published that year
with a link to it, and that list is what makes a completeness check possible:
the corpus gets diffed against the publisher's own index rather than against a
guess about which decision numbers ought to exist.

Older decisions are served as HTML (`board-decisions/1995/dab1550.html`) and
newer ones as PDF (`alj-decisions/2016/cr4685.pdf`).

## Running it

```bash
pip install -e .                                    # add [ocr] for --ocr

python collect_index.py --out decisions_index.jsonl   # what the Board published
python extract.py ./decisions -o dab.jsonl           # PDF and HTML -> text
python build_dataset.py dab.jsonl --corpus dab -o out/
python slice_jsonl.py dab.jsonl out/ --all           # -> 16 category slices
python build_manifests.py --dir out/

# what is published but missing, then fetch it
python audit_completeness.py decisions_index.jsonl out/*.parquet
python fetch_missing.py missing.jsonl --out-dir decisions/

python run_checks.py && python -m pytest tests/     # bug ledger + test suite
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

- **Both corpora are incomplete, unevenly.** Counting CR numbers present per
  block of a thousand: CR5000–5999 is 96% there and CR4000–4999 is 27%. A rate
  computed over time inherits that shape. `audit_completeness.py` measures it
  against the published index.
- **A category label is a heuristic, not a reading.** `label.py` decides from
  where a citation appears and how often, which is a much better proxy than a
  substring match and is still a proxy. No precision or recall figure is claimed
  anywhere, because there is no hand-labelled sample to compute one from.
- **The slices are not a partition.** 1,244 of 8,246 decisions land in at least
  one slice; 9 land in more than one; there is no residual category.
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
