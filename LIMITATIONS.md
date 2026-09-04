# What would have to be true for this to be wrong

Written before anyone relies on the slices, not after.

## The labels are a heuristic, not a reading

`label.py` decides membership from where a citation appears and how often. That
is a much better proxy than a substring match, and it is still a proxy. Nothing
here reads the decision and reports what the action was actually taken under.

About fifteen decisions were checked by hand — the ones named in METHODS.md,
plus a random sample of records the evidence test dropped. That is enough to
show the failure modes are real. It is not enough to state a precision or a
recall, and no number for either appears anywhere in this repo.

Both thresholds were set against the same published slices they were then
measured on. A held-out sample would need hand labels, which do not exist.

## Known misses

*Cathy Statler*, DAB No. 2241 (2009) is dropped from `excl_b7_fraud_kickback`.
The exclusion is real — a settlement in which she "agree[d] to be permanently
excluded under 42 U.S.C. § 1320a-7(a)(1) and § 1320a-7(b)(7)" — but the appeal
is about whether she can contest it, and the subsection appears once, deep in a
quoted agreement. The evidence test cannot tell that from a passing mention.

Decisions whose procedural history runs past 6,000 characters before reaching
the issue will be missed unless the basis recurs three times.

## Slices overlap, and they are not a partition

Of the 1,244 decisions that land in at least one slice, 9 land in more than
one. There is no residual "other" category, and the sixteen categories are not a
taxonomy of what the Board decides — they are the subject areas that happened to
produce bounded sets. The 1,244 are 15% of the 8,246 decisions in the corpora;
the other 85% are unsliced.

## Bad text is detected, not repaired

`pdf_to_jsonl.py` flags a text layer as poor and can re-OCR it, but only if you
have the original PDFs. The corpus as published carries the layers it was built
with, and some of the pre-1990 scans are badly garbled — DAB No. 88 (1980) reads
"Financisl", "yesr", "t:rsotee's". Those decisions are in the corpus and their
text is partly unusable. Nothing downstream knows that.

## The corpora are not complete, and the gaps are uneven

Neither corpus has been checked against the Board's own published index, but the
decision numbers themselves say enough: they are not contiguous.

The Appellate Division corpus holds 3,009 distinct decision numbers spanning 1
to 3,225 — 216 numbers in that range are absent, 7%.

The ALJ corpus is worse and, more importantly, uneven. Counting how many CR
numbers in each block of a thousand appear anywhere in the corpus:

| block | present |
|---|---|
| CR1–999 | 450 |
| CR1000–1999 | 393 |
| CR2000–2999 | 864 |
| CR3000–3999 | 579 |
| CR4000–4999 | 272 |
| CR5000–5999 | 964 |
| CR6000–6999 | 736 |

A collection that is 96% complete for CR5000–5999 and 27% complete for
CR4000–4999 is not missing decisions at random, and any count of decisions per
year, per basis or per outcome will inherit that shape. Some of this is
measurement — 596 ALJ records (12%) have no decision number parsed and are
invisible to this table — but redistributing all 596 evenly would not close a
gap that size.

Until someone reconciles both corpora against the published index, treat them as
a large collection, not the population, and do not compute a rate over time from
them.

## No outcome field

The header parses. The disposition — affirmed, reversed, modified, dismissed —
does not, and neither does the exclusion period where one is imposed. Any
analysis of what the Board *did*, as opposed to what it was deciding about,
needs work that has not been done.
