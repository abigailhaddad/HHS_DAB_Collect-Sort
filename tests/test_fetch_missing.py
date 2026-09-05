"""Naming and guards for the Archive fetcher. Offline."""
import json

import fetch_missing as fm

RULINGS = [
    {"year": 2014, "decision_no": "2014", "division": "alj",
     "url": "https://www.hhs.gov/sites/default/files/static/dab/decisions/"
            "alj-decisions/2014/alj2014-17.pdf"},
    {"year": 2014, "decision_no": "2014", "division": "alj",
     "url": "https://www.hhs.gov/sites/default/files/static/dab/decisions/"
            "alj-decisions/2014/alj2014-16.pdf"},
]


def test_names_do_not_collide_when_decision_numbers_do():
    # Both of these parsed to decision number "2014"; naming by it meant the
    # second overwrote the first, and the resume check called it done.
    assert len({fm.out_name(r) for r in RULINGS}) == 2


def test_per_decision_pages_are_named_from_their_directory():
    rec = {"year": 2019, "decision_no": "CR5411", "division": "alj",
           "url": "https://www.hhs.gov/about/agencies/dab/decisions/"
                  "alj-decisions/2019/alj-cr5411/index.html"}
    assert fm.out_name(rec) == "2019_alj-cr5411.html"


def test_archive_error_page_is_rejected_despite_a_200():
    body = b"<html><title>Wayback Machine</title>Got an HTTP 404 response" + b"x" * 3000
    ok, why = fm.is_good(body, "http://x/cr1.html")
    assert not ok and "archive error" in why


def test_truncated_pdf_is_rejected():
    ok, why = fm.is_good(b"%PDF-1.6" + b"x" * 50, "http://x/cr1.pdf")
    assert not ok and "too small" in why


def test_html_served_for_a_pdf_url_is_rejected():
    ok, why = fm.is_good(b"<html>" + b"x" * 5000, "http://x/cr1.pdf")
    assert not ok and "not a PDF" in why


def test_a_real_pdf_passes():
    ok, _ = fm.is_good(b"%PDF-1.6" + b"x" * 5000, "http://x/cr1.pdf")
    assert ok


def test_resume_floor_is_per_type():
    # The PDF floor applied to HTML made any 1,500-1,999 byte page fail the
    # resume check on every run.
    assert fm.min_bytes("2002_cr853.html") < fm.MIN_PDF_BYTES
    assert fm.min_bytes("1989_cr18.pdf") == fm.MIN_PDF_BYTES


def test_a_query_string_never_reaches_the_filename():
    # Path(".../alj-cr5002.pdf?language=en").suffix is ".pdf?language=en", so
    # the file lands with an extension no suffix filter matches and the
    # extractor skips it silently.
    rec = {"year": 2017, "decision_no": "CR5002", "division": "alj",
           "url": "https://www.hhs.gov/sites/default/files/alj-cr5002.pdf?language=en"}
    assert fm.out_name(rec) == "2017_alj-cr5002.pdf"


def test_a_fragment_is_stripped_too():
    rec = {"year": 2017, "decision_no": "CR1", "division": "alj",
           "url": "https://www.hhs.gov/sites/default/files/alj-cr1.pdf#page=2"}
    assert fm.out_name(rec) == "2017_alj-cr1.pdf"


def test_the_pdf_check_looks_at_the_path_not_the_raw_url():
    # ".../alj-cr5002.pdf?language=en" does not end in ".pdf", so the strict
    # magic-byte check was skipped for exactly the URL era most likely to need
    # it, and any HTML over the 1,500-byte floor saved cleanly as a .pdf.
    url = "https://www.hhs.gov/sites/default/files/alj-cr5002.pdf?language=en"
    ok, why = fm.is_good(b"<html>Redirecting</html>" + b"y" * 2000, url)
    assert not ok and "not a PDF" in why
    assert fm.is_good(b"%PDF-1.6" + b"x" * 5000, url)[0]
