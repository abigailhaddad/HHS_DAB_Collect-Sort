"""Regression checks. Every bug found by hand becomes a case here.

Run: python run_checks.py   (exits non-zero on failure)
"""
from __future__ import annotations

import sys

import categories
import clean
import label
import metadata

failures: list[str] = []


def check(name: str, got, want) -> None:
    if got != want:
        failures.append(f"{name}\n     got:  {got!r}\n     want: {want!r}")


# --- Citation stripping -------------------------------------------------------
# The Board's standing cite on documenting costs is a Head Start case, so a
# plain "head start" match pulled 30+ cost-disallowance appeals into the
# head_start slice -- Washington State University, Oglala Sioux Community
# College, the New York and South Dakota social services departments.
STRIP_CASES = [
    ("New Hanover, bare Decision No. form", True,
     "a fundamental principle of grant management. (Head Start of New Hanover "
     "County, Inc., Decision No. 65, September 26, 1979.) In the instant case"),
    ("New Hanover, DGAB docket form", True,
     "(Cf. Knox County Economic Opportunity Council, Inc., DGAB Docket No. 78-14, "
     "Decision No. 68, October 29, 1979, p.2; Head Start of New Hanover County, "
     "DGAB Docket No. 78-94, Decision No. 65, September 26, 1979, p. 3;"),
    # Note what this asserts: that a citation span exists somewhere in the
    # string. It does NOT assert that the 1128(b)(7) before it is inside one --
    # it is not, and tests/test_label.py pins that as a known limitation.
    ("DAB No. with pincite and year", True,
     'quoted in Keith Michael Everman, D.C., DAB No. 1880, at 7 (2003).'),
    ("ALJ decision cite", True,
     "Tajammul H. Bhatti, M.D., DAB CR245 (1992) (ALJ Decision). In his decision"),
    # The stripper must not reach into ordinary prose. An unbounded party-name
    # run walks backwards across sentence boundaries and eats the holding.
    ("a real Head Start operator, not a citation", False,
     "William Smith, Sr. Tri-County Child Development Council, Inc. (the Council), "
     "a nonprofit corporation, operates Head Start and Early Head Start programs "
     "in Texas."),
    ("the operative basis, not a citation", False,
     "to exclude Petitioner from participation in the Medicare program and state "
     "health care programs for a period of ten years pursuant to section "
     "1128(b)(6)(B) of the Social Security Act."),
]
for name, should_strip, text in STRIP_CASES:
    check(f"citation_spans: {name}", bool(label.citation_spans(text)), should_strip)


# --- Whitespace normalization -------------------------------------------------
# PDF extraction breaks phrases and citations across lines. clean() keeps line
# structure on purpose (metadata.py needs it to find the header), so matching
# has to normalize first. Skipping that silently dropped Topeka Public Schools
# (DAB 47) -- a real Head Start cost appeal -- because the phrase wrapped.
WRAP_CASES = [
    ("head_start across a line break", "head_start",
     "children of low-income families who were previously enrolled in Head\nStart "
     "or similar programs, through provision of intensified activities"),
    ("b7 citation across a line break", "excl_b7_fraud_kickback",
     "permissive exclusions under section 1128(b)\n(7) of the Act were necessary"),
    ("b7 citation with the statutory form split", "excl_b7_fraud_kickback",
     "agree[s] to be permanently excluded under 42 U.S.C. § 1320a-\n7(b) (7) for "
     "the Covered Conduct"),
]
for name, cat, text in WRAP_CASES:
    ev = label.evidence(text, categories.CATEGORIES[cat].regex)
    check(f"normalize: {name}", ev["n_matches"] >= 1, True)


# --- Membership ---------------------------------------------------------------
# All three shipped in the 3-record dab_excl_b6_quality_care slice; only the
# last one is a quality-of-care case.
# In both false positives the mention sits deep in the reasoning, so the filler
# goes BEFORE it. Padding after would place the match at character 0, inside the
# opening window, and the case would pass for the wrong reason.
BODY = "Procedural history and findings of fact. " * 220

MEMBER_CASES = [
    ("Chang (DAB 1198): petitioner argued for b6 and lost", "excl_b6_quality_care", False,
     BODY + "Petitioner contended that such a finding should invoke the permissive "
     "provisions of section 1128(b)(6) of the Act, which are designed to address "
     "the specific offense of fraudulent billing. We find no merit in "
     "Petitioner's arguments. Petitioner pleaded guilty to fraud."),
    ("Friedman (DAB 1281): b6 inside an enumeration of IG powers", "excl_b6_quality_care", False,
     BODY + "agencies (section 1128(b)(5)), and state licensing authorities (section "
     "1128(b)(4)); or (B) to make an independent determination of improper "
     "conduct (sections 1128(b)(6), (7), (8)). By enacting section 1128(b)(4)(A), "
     "Congress granted the I.G. authority to rely on the fact of a revocation."),
    ("Godreau (DAB 1300): b6 is the basis of the exclusion", "excl_b6_quality_care", True,
     "determination to exclude Petitioner from participation in the Medicare "
     "program and state health care programs for a period of ten years pursuant "
     "to section 1128(b)(6)(B) of the Social Security Act."),
]
for name, cat, want, text in MEMBER_CASES:
    got, _ = label.label(text, categories.CATEGORIES[cat].regex)
    check(f"is_member: {name}", got, want)


# --- Website furniture --------------------------------------------------------
# A quarter of the corpus was captured from dab.hhs.gov rather than a PDF.
CHROME = (
    "Pennsylvania Physicians, P.C., DAB No. 2980 (2019) BreadcrumbHome </>About "
    "HHS </about/index.html>Agencies </about/agencies>DAB </about/agencies/dab/"
    "index.html>Decisions </about/agencies/dab/decisions/index.html>2019 "
    "</about/agencies/dab/decisions/board-decisions/2019/index.html>Pennsylvania "
    "Physicians, P.C. An official website of the United States government "
    "Skip to main content Page sharing options "
    "DECISION The Board reviews the revocation of a supplier's Medicare billing "
    "privileges under section 424.535(a)(3) of the regulations."
)
cleaned = clean.clean(CHROME)
check("clean: breadcrumb removed", "BreadcrumbHome" in cleaned, False)
check("clean: banner removed", "official website" in cleaned, False)
# The first version of the breadcrumb pattern was unbounded and chained from the
# breadcrumb to the last link in the document, eating 6.9 MB of real decision
# text across the corpus before the guard caught it.
check("clean: keeps the decision body", "billing privileges" in cleaned, True)
check("clean: keeps the operative citation", "424.535(a)(3)" in cleaned, True)
check("clean: no-op on text that has none",
      clean.clean("A plain decision paragraph."), "A plain decision paragraph.")
runaway = "BreadcrumbHome </a>" + " ".join(f"word{i} </p{i}>" for i in range(400))
_, ok = clean.clean_guarded(runaway)
check("clean_guarded: guard trips on a runaway removal", ok, False)


# --- Category table -----------------------------------------------------------
# categorize_counts.py had a "samhsa_otp_cert" pattern with no description in
# build_manifests.py, and called b7 "excl_b7_fraud_kickback" where the manifest
# looked up "b7". Both would have shipped a slice with a blank legal basis.
for name, cat in categories.CATEGORIES.items():
    check(f"categories: {name} has a description", bool(cat.description), True)
    check(f"categories: {name} has a citation", bool(cat.citation), True)
    check(f"categories: {name} key matches its name", cat.name, name)


# --- Header parsing -----------------------------------------------------------
# One case per template generation.
HEADERS = [
    ("Grant Appeals Board, 1978",
     "DEPARTI1ENTAL GRANT APPEALS BOARD\nDepartment of Health, Education, and "
     "Welfare\nSUBJECT: Topeka Public Schools, Topeka, Kansas\nDocket Nos. 77-7, "
     "77-8, and 77-9\nDecision No. 47\nDATE~ SEP. 28, 1978\nDECISION",
     {"decision_no": "47", "decision_date": "1978-09-28",
      "tribunal": "Grant Appeals Board"}),
    ("Appellate Division, 1993",
     "Department of Health and Human Services\nDEPARTMENTAL APPEALS BOARD\n"
     "Appellate Division\nIn the Case of:\nTajammul H. Bhatti, M.D.,\nPetitioner,\n"
     "- v. -\nThe Inspector General.\nDATE: June 1, 1993\nDocket No. C-92-045\n"
     "Decision No. 1415\n",
     {"decision_no": "1415", "decision_date": "1993-06-01",
      "tribunal": "Appellate Division", "respondent": "Inspector General"}),
    ("Civil Remedies Division, 2008",
     "Department of Health and Human Services\nDEPARTMENTAL APPEALS BOARD\n"
     "Civil Remedies Division\nIn the Case of:\nDaniel M. Stewart,\nPetitioner,\n"
     "- v. -\nCenters for Medicare & Medicaid Services.\nDate: January 9, 2008\n"
     "Docket No. C-07-429\nDecision No. CR1723\n",
     {"decision_no": "CR1723", "decision_date": "2008-01-09",
      "tribunal": "Civil Remedies Division", "respondent": "CMS"}),
    ("bare date line, 2015",
     "Department of Health and Human Services\nDEPARTMENTAL APPEALS BOARD\n"
     "Appellate Division\nWilliam Smith, Sr. Tri-County Child Development "
     "Council, Inc.\nDocket No. A-15-44\nDecision No. 2647\nJune 30, 2015\n"
     "DECISION",
     {"decision_no": "2647", "decision_date": "2015-06-30",
      "tribunal": "Appellate Division"}),
]
for name, text, want in HEADERS:
    got = metadata.parse(text)
    for field, value in want.items():
        check(f"metadata [{name}]: {field}", got[field], value)
# The filenames carry typos ("0980.02.25DAB083" for 1980), which is why the year
# comes from the text and the filename is only a fallback.
check("metadata: year comes from the text, not the filename",
      metadata.parse("Decision No. 83\nDATE: February 25, 1980\n",
                     "0980.02.25DAB083 New Mexico")["year"], 1980)


# --- Text-layer quality gate --------------------------------------------------
# The first version of this gate also rejected text whose words were more than
# 4% vowel-free. That reads like a garbling detector and is not one: the corpus
# median is 1.5%, the 95th percentile is 4.5%, and the three highest-scoring
# decisions are In re LCD Complaint cases dense with CPT codes and correctly
# extracted. It rejected a clean synthetic decision on its first end-to-end run.
import extract

DENSE_PAGE = ("I sustain the determination of CMS to revoke Petitioner's Medicare "
              "billing privileges under 42 C.F.R. section 424.535(a)(3) based on a "
              "felony conviction. ") * 12
check("text_quality: a normal page passes",
      extract.text_quality(DENSE_PAGE, 1)[0], True)
check("text_quality: abbreviation-dense text still passes",
      extract.text_quality("CPT HCPCS LCD CMS NCD " * 200, 1)[0], True)
check("text_quality: empty layer fails",
      extract.text_quality("   ", 3)[0], False)
check("text_quality: one character per page fails",
      extract.text_quality("x" * 12, 12)[0], False)


if failures:
    print(f"{len(failures)} FAILED\n")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("all checks passed")
