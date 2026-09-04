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
    # Bare number for the Appellate series, "CR" kept for Civil Remedies --
    # the same shape the corpus stores, so the two join without a translation.
    assert [r["decision_no"] for r in rows] == ["1550", "1549"]
    assert rows[0]["url"].endswith("/board-decisions/1995/dab1550.html")


def test_parses_a_dab_number_without_the_word_no(index_pages):
    # Captions render it "DAB2740". Requiring "No." nulled every one of them.
    rows = ci.parse_index(index_pages["dab_2016"], "dab", 2016)
    assert rows[0]["decision_no"] == "2740"


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


def test_parses_the_per_decision_page_era(index_pages):
    # From 2017 the filename is index.html and only the directory names the
    # decision. Rejecting every /index.html threw all of these away.
    rows = ci.parse_index(index_pages["dab_2020"], "dab", 2020)
    assert [r["decision_no"] for r in rows] == ["3027", "CR5791"]
    assert rows[0]["url"].endswith("/board-decisions/2020/board-dab-3027/index.html")


def test_still_skips_the_year_index_in_the_new_era(index_pages):
    rows = ci.parse_index(index_pages["dab_2020"], "dab", 2020)
    assert not any(r["url"].endswith("/board-decisions/2020/index.html") for r in rows)


ALJ_RULING_INDEX = """
<html><body>
<a href="/sites/default/files/static/dab/decisions/alj-decisions/2014/alj2014-17.pdf">
  2013.12.13 ALJ Ruling No. 2014-17 Lynda L. Hook v. The Inspector General</a>
<a href="/sites/default/files/static/dab/decisions/alj-decisions/2014/alj2014-16.pdf">
  2013.12.06 ALJ Ruling No. 2014-16 CTP v. Guevara LLC</a>
</body></html>
"""


def test_alj_rulings_are_not_numbered_by_their_year():
    # "ALJ Ruling No. 2014-17" hit the generic "No. NNNN" branch and parsed as
    # decision 2014, so all 23 of a year's rulings shared one identifier.
    rows = ci.parse_index(ALJ_RULING_INDEX, "alj", 2014)
    assert [r["decision_no"] for r in rows] == ["RULING2014-17", "RULING2014-16"]


def test_a_bare_year_is_never_a_decision_number():
    page = ('<a href="/sites/default/files/static/dab/decisions/alj-decisions/'
            '2014/alj2014-99.pdf">2014.01.02 Some Order No. 2014 concerning X</a>')
    rows = ci.parse_index(page, "alj", 2014)
    assert rows[0]["decision_no"] is None


def test_caption_and_filename_agree_on_the_same_decision():
    # These were two implementations and diverged. The caption side required a
    # word boundary before "CR" (never true in "2004.07.08CR1196"), demanded
    # "Ruling No." where captions also write "ALJ Ruling 2013-2", and dropped
    # the R suffix -- 394 published decisions ended up with no identifier.
    import metadata
    for fragment in ("2004.07.08CR1196 Alden-Princeton Rehabilitation",
                     "1988.05.02 CR10R The Inspector General v. Frank P. Silver",
                     "2012.12.13. ALJ Ruling 2013-2 Willow Tree Nursing Center",
                     "1995.11.27 DAB1550 Neil R. Hirsch, M.D."):
        assert ci.decision_no_from_caption(fragment) == \
               metadata.decision_no_from_text(fragment), fragment


def test_the_previously_unidentifiable_captions_now_parse():
    assert ci.decision_no_from_caption("2004.07.08CR1196 Alden-Princeton") == "CR1196"
    assert ci.decision_no_from_caption("1988.05.02 CR10R The Inspector General") == "CR10R"
    assert ci.decision_no_from_caption("2012.12.13. ALJ Ruling 2013-2 Willow Tree") == "RULING2013-2"
