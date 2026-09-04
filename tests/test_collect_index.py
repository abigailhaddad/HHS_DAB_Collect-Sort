"""Index-page parsing. Offline: fixtures only, no Archive requests."""
import collect_index as ci


def test_parses_the_pdf_era(index_pages):
    rows = ci.parse_index(index_pages["alj_2016"], "alj", 2016)
    assert len(rows) == 2
    assert [r["decision_no"] for r in rows] == ["CR4685", "CR4684"]
    assert rows[0]["url"].endswith("/alj-decisions/2016/cr4685.pdf")
    assert rows[0]["caption"].startswith("2016.08.17 CR4685 Rochelle Gardens")


def test_parses_the_html_era(index_pages):
    # HHS serves pre-2000 decisions as .html. Matching only .pdf returned an
    # empty list for every one of those years, which looks like a clean result.
    rows = ci.parse_index(index_pages["dab_1995"], "dab", 1995)
    assert len(rows) == 2
    assert [r["decision_no"] for r in rows] == ["DAB1550", "DAB1549"]
    assert rows[0]["url"].endswith("/board-decisions/1995/dab1550.html")


def test_parses_a_dab_number_without_the_word_no(index_pages):
    # Captions render it "DAB2740". Requiring "No." nulled every one of them.
    rows = ci.parse_index(index_pages["dab_2016"], "dab", 2016)
    assert rows[0]["decision_no"] == "DAB2740"


def test_skips_the_pages_own_navigation(index_pages):
    rows = ci.parse_index(index_pages["alj_2016"], "alj", 2016)
    assert not any("index.html" in r["url"] for r in rows)


def test_urls_are_absolute(index_pages):
    for key, div, year in (("alj_2016", "alj", 2016), ("dab_1995", "dab", 1995)):
        for r in ci.parse_index(index_pages[key], div, year):
            assert r["url"].startswith("https://www.hhs.gov/")


def test_division_year_are_recorded(index_pages):
    rows = ci.parse_index(index_pages["dab_1995"], "dab", 1995)
    assert {r["division"] for r in rows} == {"dab"}
    assert {r["year"] for r in rows} == {1995}


def test_first_year_bounds_are_set_per_division():
    # Probing outside them costs two failed lookups a year and returns nothing;
    # the collector spent six minutes on ALJ 1974-1980 before these existed.
    assert ci.FIRST_YEAR["alj"] > ci.FIRST_YEAR["dab"]
    assert set(ci.FIRST_YEAR) == set(ci.DIVISIONS)
