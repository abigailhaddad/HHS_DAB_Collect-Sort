"""Website furniture removal."""
import clean

BREADCRUMB = (
    "Pennsylvania Physicians, P.C., DAB No. 2980 (2019) BreadcrumbHome </>About "
    "HHS </about/index.html>Agencies </about/agencies>DAB </about/agencies/dab/"
    "index.html>2019 </about/agencies/dab/decisions/board-decisions/2019/index.html>"
    "Pennsylvania Physicians, P.C. An official website of the United States "
    "government Skip to main content Page sharing options DECISION The Board "
    "reviews the revocation of billing privileges under section 424.535(a)(3). "
    "We conclude that CMS had a legitimate basis to revoke Petitioner's Medicare "
    "enrollment and billing privileges, and we affirm the ALJ's decision "
    "sustaining that revocation. Petitioner was convicted of a felony offense "
    "that CMS determined to be detrimental to the best interests of the program "
    "and its beneficiaries, and the record supports that determination."
)


def test_removes_every_furniture_marker():
    out = clean.clean(BREADCRUMB)
    for marker in ("BreadcrumbHome", "official website", "Page sharing options",
                   "Skip to main content", "/about/agencies"):
        assert marker not in out


def test_keeps_the_decision():
    out = clean.clean(BREADCRUMB)
    assert "revocation of billing privileges" in out
    assert "424.535(a)(3)" in out


def test_is_a_no_op_without_furniture():
    body = "The Board affirms the ALJ decision.\n\nAnalysis follows."
    assert clean.clean(body) == body


def test_is_idempotent():
    once = clean.clean(BREADCRUMB)
    assert clean.clean(once) == once


def test_has_chrome_agrees_with_clean():
    assert clean.has_chrome(BREADCRUMB)
    assert not clean.has_chrome("An ordinary paragraph of a decision.")


def test_guard_rejects_a_runaway_removal():
    # The first breadcrumb pattern was unbounded and chained from the breadcrumb
    # to the last link in the document, deleting 6.9 MB of decision text.
    runaway = "BreadcrumbHome </a>" + " ".join(f"word{i} </p{i}>" for i in range(1200))
    text, ok = clean.clean_guarded(runaway)
    assert not ok
    assert text == runaway, "a tripped guard must return the input untouched"


def test_guard_passes_a_normal_removal():
    text, ok = clean.clean_guarded(BREADCRUMB)
    assert ok
    assert len(text) < len(BREADCRUMB)


def test_guard_cleans_a_short_mostly_furniture_record():
    # A proportional-only guard refused to clean exactly the records that
    # carried the most furniture relative to their length.
    # Proportions taken from the real short orders this used to reject, e.g.
    # DAB No. 2993, where the furniture is about 40% of the visible characters.
    short = ("BreadcrumbHome </>DAB </about/agencies/dab/index.html> "
             "An official website of the United States government "
             "ORDER Petitioner's request for hearing is dismissed as untimely. "
             "Petitioner filed the request more than 60 days after receiving "
             "notice of the initial determination and has shown no good cause "
             "for the delay, so there is no right to a hearing before an ALJ.")
    text, ok = clean.clean_guarded(short)
    assert ok
    assert "BreadcrumbHome" not in text
    assert "request for hearing is dismissed" in text


def test_guard_handles_empty_input():
    assert clean.clean_guarded("") == ("", True)


def test_removes_the_old_tab_bar_without_the_footnotes_tab():
    # MARKERS accepted "CASE | DECISION | JUDGE" while the removal pattern
    # required "| FOOTNOTES" as well, so 21 decisions were flagged dirty and
    # then left dirty. Whatever has_chrome() detects, clean() must remove.
    for bar in ("CASE | DECISION | JUDGE",
                "CASE | DECISION | JUDGE | FOOTNOTES"):
        text = f"{bar}\nDepartment of Health and Human Services\nDECISION follows."
        assert clean.has_chrome(text)
        out = clean.clean(text)
        assert "CASE" not in out
        assert "DECISION follows." in out


def test_every_marker_the_detector_finds_is_actually_removed():
    samples = [
        "BreadcrumbHome </>DAB </about/agencies/dab/index.html> body text here",
        "An official website of the United States government body text here",
        "Skip to main content body text here",
        "Page sharing options body text here",
        "CASE | DECISION | JUDGE body text here",
        "some text ...TO TOP more body text here",
    ]
    for s in samples:
        assert clean.has_chrome(s), s
        assert not clean.has_chrome(clean.clean(s)), f"survived cleaning: {s}"


DOT_GOV_BLOCK = (
    "William S. Strauss, M.D., DAB CR5411 (2019) | HHS.gov Here’s how you know "
    "Official websites use .gov A .gov website belongs to an official government "
    "organization in the United States. Secure .gov websites use HTTPS A lock ( "
    "Lock A locked padlock ) or https:// means you've safely connected to the "
    ".gov website. DECISION I sustain the determination of CMS."
)
SKIP_NAVIGATION = (
    "1999.12.29 CR636 T.L.C. Mental Health Center vs. Health Care Financing "
    "Administration Skip Navigation Decision No. CR 636 Department of Health and "
    "Human Services DEPARTMENTAL APPEALS BOARD Civil Remedies Division"
)


def test_removes_the_dot_gov_reassurance_block():
    # ~300 characters of boilerplate on every per-decision page from 2017.
    assert clean.has_chrome(DOT_GOV_BLOCK)
    out = clean.clean(DOT_GOV_BLOCK)
    assert "locked padlock" not in out
    assert "how you know" not in out
    assert "I sustain the determination of CMS." in out


def test_removes_the_older_skip_navigation():
    # The 1999-2006 pages say "Skip Navigation", not "Skip to main content".
    assert clean.has_chrome(SKIP_NAVIGATION)
    out = clean.clean(SKIP_NAVIGATION)
    assert "Skip Navigation" not in out
    assert "Decision No. CR 636" in out
