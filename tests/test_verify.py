"""Named verdicts for a fetched file. HTTP 200 is not the test; content is."""
import verify

DECISION = ("<html><body><h1>Decision No. CR4685</h1>"
            "<p>Department of Health and Human Services DEPARTMENTAL APPEALS BOARD "
            "Civil Remedies Division</p><p>" + "The decision text continues. " * 60 +
            "</p></body></html>").encode()


def test_a_decision_is_ok():
    assert verify.verdict(DECISION, "cr4685.html")[0] == "OK"


def test_a_block_page_is_a_retry_not_a_data_problem():
    body = b"<html><head><title>Access Denied</title></head><body>" + b"x" * 6000
    assert verify.verdict(body, "cr1.html")[0] == "CHALLENGE"


def test_an_archive_miss_served_with_200():
    body = (b"<html><body>Wayback Machine has not archived that URL"
            + b"x" * 6000 + b"</body></html>")
    assert verify.verdict(body, "cr1.html")[0] == "ARCHIVE_MISS"


def test_the_landing_page_is_not_a_decision():
    # A redirect to the section landing page returns a large, healthy-looking
    # document with no decision in it.
    body = ("<html><body>" + "Browse decisions by year. " * 200 +
            "</body></html>").encode()
    assert verify.verdict(body, "cr1.html")[0] == "NOT_A_DECISION"


def test_a_thin_page_with_the_letterhead_is_thin():
    body = b"<html><body>DEPARTMENTAL APPEALS BOARD Civil Remedies Division</body></html>"
    assert verify.verdict(body, "cr1.html")[0] == "THIN"


def test_pdfs_are_judged_on_magic_bytes_and_size():
    assert verify.verdict(b"%PDF-1.6" + b"x" * 5000, "cr1.pdf")[0] == "OK"
    assert verify.verdict(b"%PDF-1.6" + b"x" * 50, "cr1.pdf")[0] == "THIN"
    assert verify.verdict(b"<html>" + b"x" * 6000, "cr1.pdf")[0] == "NOT_A_DECISION"


def test_empty():
    assert verify.verdict(b"", "cr1.html")[0] == "EMPTY"
    assert verify.verdict(b"   \n ", "cr1.html")[0] == "EMPTY"


def test_the_grant_appeals_board_era_counts_as_a_decision():
    # 1982-1986 reprints head with "GAB Decision 245" and never spell out the
    # Board's name. A marker set built from the modern template rejected 159
    # real decisions of ~51,000 characters each.
    body = ("<html><body>1982.01.12 DAB245 California Department of Social "
            "Services, DAB No, 245 (1982) GAB Decision 245 January 12, 1982 "
            + "The decision text continues. " * 60 + "</body></html>").encode()
    assert verify.verdict(body, "dab245.html")[0] == "OK"


def test_letterhead_variants_across_eras_and_typos():
    # Four real decisions the first marker set rejected. The letterhead varies
    # by era and by scanning typo, so a numbered decision line counts too.
    for head in ("GAB Drecision 247 January 19, 1982",          # typo in source
                 "DAB Decision 577 Docket No. 84-20",           # DAB, not GAB
                 "DAB No. 1148 Department of Health and Human Services",
                 "IN THE MATTER OF THE DISAPPROVAL OF IOWA'S AFDC PLAN "
                 "AMENDMENT, DAB NO. 1215"):
        body = ("<html><body>" + head + " " +
                "The decision text continues. " * 60 + "</body></html>").encode()
        assert verify.verdict(body, "d.html")[0] == "OK", head


def test_a_page_that_is_only_a_decision_number_is_not_ok():
    # 1983_dab437: 5 KB of markup, six visible characters, "DAB437". A real
    # failed fetch, and the only one in 1,729 files.
    body = b"<html><body><p>DAB437</p></body></html>" + b" " * 5000
    assert verify.verdict(body, "dab437.html")[0] != "OK"
