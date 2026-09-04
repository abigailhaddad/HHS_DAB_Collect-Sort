# What would have to be true for this to be wrong

Written before anyone relies on the slices, not after.

The figures here are a snapshot, taken against the corpus as built on
2026-09-04. Re-run `audit_completeness.py` and `build_manifests.py` for current
ones; the counts in this file will drift as the collector picks up new
decisions.

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

Of the 6,061 decisions that land in at least one slice, 1,357 land in more than
one. There is no residual "other" category, and the 38 categories are not a
taxonomy of what the Board decides — they are the subject areas that produce
bounded sets. The 6,061 are 65% of the 9,391 decisions in the corpora; the other
35% are unsliced, and 8 of the 76 category/corpus pairs are empty.

## The text-quality gate catches empty layers, not garbled ones

`extract.py` gates on characters per page, which reliably catches a PDF
that yielded nothing. Three decisions in the corpus extract at about one
character per page and are effectively empty: DAB No. 2307 (Tennessee Department
of Children's Services), DAB No. 2212 (Ocean Springs Nursing Center) and DAB No.
2217 (Abstinence for Singles).

It does not catch a text layer that is dense and wrong. DAB No. 88 (1980)
extracts at a normal length and reads "Financisl", "yesr", "t:rsotee's" — about
50% of its words are not in a dictionary, against a 22% baseline for legal prose.
A shape test cannot see that; it needs a wordlist, which is not wired in.

A first version of the gate also rejected text whose words were more than 4%
vowel-free. That is not a garbling detector: the corpus median is 1.5%, the 95th
percentile is 4.5%, and the three highest-scoring decisions are *In re LCD
Complaint* cases, dense with CPT codes and extracted perfectly well. It was
removed after it rejected a clean decision on the first end-to-end run.

Repair needs the original PDFs, which are not in this repo either way.

## Completeness is measured against the index, and is not total

Both corpora hold every decision the Board's own year-by-year index lists and
gives an identifiable number to: 8,897 of 8,897. `audit_completeness.py` runs
that diff against the publisher's own list, rather than against a guess about
which decision numbers ought to exist.

The remaining 323 index listings carry no parseable decision number and sit
outside the check entirely. They are mostly reconsideration decisions and
rulings with irregular captions.

Two decisions are absent for reasons at the source. DAB No. 437 (1983) is
published as a page containing the six characters "DAB437" and nothing else,
which a live fetch reproduces. Three more extract to about one character per
page and are flagged by `text_layer_ok`.

Before this collection the same audit put the ALJ corpus at 76%, with 971 of the
decisions issued between 1999 and 2006 missing entirely. A rate computed over
time on that corpus would have inherited the hole.

## No outcome field

The header parses. The disposition — affirmed, reversed, modified, dismissed —
does not, and neither does the exclusion period where one is imposed. Any
analysis of what the Board *did*, as opposed to what it was deciding about,
needs work that has not been done.
