# HHS DAB decisions — collect and sort

Every published decision of the HHS Departmental Appeals Board, in two corpora:
the Appellate Division and its predecessor Grant Appeals Board (3,300
decisions, Decision No. 1 through 3225, 1974 to present) and the Civil Remedies
Division ALJs (4,946 decisions, CR1 through CR6778, 1981 to present). PDFs in, typed Parquet out, with
the header parsed into fields you can filter on and sixteen category slices cut
by statutory basis.

## The pipeline

```bash
python pdf_to_jsonl.py ./dab_pdfs -o dab.jsonl --ocr   # PDFs -> text
python build_dataset.py dab.jsonl --corpus dab -o out/ # -> typed Parquet
python slice_jsonl.py dab.jsonl out/ --all             # -> category slices
python build_manifests.py --dir out/                   # -> manifest per corpus
python run_checks.py                                   # regression checks
```

`categories.py` holds the sixteen categories — pattern, description and legal
citation together in one table. Adding a category means adding it there.

## What each step does

`pdf_to_jsonl.py` reads the text layer and, with `--ocr`, re-OCRs any PDF that
fails a quality test. The test is chars-per-page and the share of words with no
vowel, not an absolute character count: the 1980s scans in this corpus have text
layers that are present, long and garbled, and a character floor passes them.

`clean.py` strips the HHS website furniture. About a quarter of the corpus was
captured from dab.hhs.gov rather than a PDF, so the extracted text carries the
site's breadcrumb, the "official website of the United States government"
banner and whatever promo box HHS was running — 19% of Appellate Division
decisions and 42% of ALJ decisions, 1.6 MB in total.

`metadata.py` parses the header into decision number, docket numbers, date,
tribunal and respondent agency, across the four template generations the corpus
spans. Coverage: decision number 98.6% / 87.9% (Appellate / ALJ), docket 92.1% /
98.1%, date 94.2% / 99.9%, tribunal 89.9% / 97.5%, respondent 72.8% / 83.3%.
Dates come from the text, not the filename — 101 filenames disagree with the
decision they contain, and some are simply typed wrong (`0980.02.25DAB083`).

`label.py` decides whether a decision is *about* a category rather than whether
it mentions one. See [METHODS.md](./METHODS.md).

`build_dataset.py` writes one Parquet file per corpus, zstd-compressed. 284 MB
of JSONL becomes 53 MB, which is the difference between a dataset you can
range-query over HTTP and one you have to download.

## Data

The corpora are not committed. They live on Hugging Face; `.gitignore` keeps
`*.jsonl` and `*.parquet` out of the repo.

## Limitations

[LIMITATIONS.md](./LIMITATIONS.md) — what would have to be true for the slices
to be wrong, written before anyone relies on them.
