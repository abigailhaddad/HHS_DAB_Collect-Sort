# How a decision gets assigned to a category

## The problem with matching text

A decision belongs in the `head_start` slice if it is a Head Start dispute, and
in `excl_b6_quality_care` if the exclusion was imposed for failure to provide
quality care. Searching the full text for "head start" or "1128(b)(6)" answers a
different question — whether the string appears anywhere — and the two answers
come apart in three specific ways, all of them observed in the published slices.

**Precedent.** *Head Start of New Hanover County, Inc.*, DAB No. 65 (1979) is
the Board's standing cite on documenting costs, so it is quoted in cost-
disallowance appeals that have nothing to do with Head Start. Washington State
University, Oglala Sioux Community College, and the New York and South Dakota
social services departments all landed in a 253-record `head_start` slice on the
strength of that citation.

**Enumeration.** *Friedman*, DAB No. 1281 (1991) is a licence-revocation case
under 1128(b)(4). It lists "(sections 1128(b)(6), (7), (8))" in a parenthetical
about the scope of the IG's authority, and that put it in the quality-of-care
slice.

**Losing arguments.** *Chang*, DAB No. 1198 (1990) is a section 1128(a)
conviction case in which the petitioner argued 1128(b)(6) should apply instead.
The Board said "we find no merit in Petitioner's arguments." The slice counted
it anyway.

Of the three decisions in the published `dab_excl_b6_quality_care` slice, two
were *Chang* and *Friedman*.

## The test

`label.py` runs in three steps.

1. **Normalize whitespace.** PDF extraction breaks phrases and citations across
   lines, so "Head\\nStart" and "1320a-\\n7(b)(7)" are common. Matching without
   this loses real hits — it dropped Topeka Public Schools (DAB No. 47), a
   genuine Head Start cost appeal, because the program name wrapped.

2. **Blank out case citations.** A bounded pattern matches a capitalised party
   run followed by a reporter number and closing on a parenthesised year or a
   date: `Head Start of New Hanover County, Inc., Decision No. 65, September 26,
   1979`. Matches falling inside those spans are counted separately and do not
   support membership. The bounds matter — an unbounded party-name run walks
   backwards across sentence boundaries and swallows the holding along with the
   citation.

3. **Require the match to carry weight.** A decision is a member if the basis is
   named in the first 6,000 characters — the header and the opening recitation,
   where a decision says what it is deciding — or if it survives three or more
   times outside citations, meaning the decision is working with the provision
   rather than glancing at it.

## What it changes

Across the twenty-one slices that were published, 889 records become 749: 141
dropped, 1 added.

| slice | substring | evidence |
|---|---|---|
| `dab_head_start` | 253 | 221 |
| `dab_title_ivd_child_support` | 137 | 121 |
| `alj_enroll_a8_billing_abuse` | 93 | 80 |
| `dab_enroll_a3_felony` | 68 | 51 |
| `alj_clia` | 73 | 62 |
| `dab_excl_b4_license_revocation` | 37 | 27 |
| `alj_b7` | 33 | 26 |
| `dab_b7` | 13 | 10 |
| `alj_excl_b6_quality_care` | 6 | 2 |
| `dab_excl_b6_quality_care` | 3 | 1 |

*Chang* and *Friedman* are out; *Godreau*, DAB No. 1300 (1992), where the
exclusion was imposed "pursuant to section 1128(b)(6)(B)", is the one that
stays.

Running all 38 categories against both corpora rather than the ten and
eleven that were cut turns up substantial slices nobody had pulled:
`excl_b4_license_revocation` has 208 ALJ decisions, `enroll_a3_felony` 158,
`enroll_a5_nonoperational` 135 and `clia_lab_sanctions` 118.

Collecting the decisions the corpus was missing moved these again, and the
shape of the movement is what you would expect from filling a 1999-2006 hole:
`excl_b4_license_revocation` gained 65 and `clia_lab_sanctions` 56, while
`enroll_a3_felony` gained one, because revocation under 42 CFR 424.535(a)(3)
post-dates that window.

`samhsa_otp_cert` has no members in either corpus, and `opo_decert` none in the
Appellate Division.

## Calibration

Both thresholds — 6,000 characters and three recurrences — were set by hand
against the published slices and the decisions named above. They have not been
fitted to a held-out sample, because there isn't one. See LIMITATIONS.md.
