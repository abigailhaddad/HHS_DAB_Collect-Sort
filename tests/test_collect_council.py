"""The Council landing page: one flat list, not year indexes."""
import collect_council as cc

PAGE = """
<html><body>
<a href="/sites/default/files/static/dab/decisions/council-decisions/m-11-2450.pdf">
  In the Case of W.K.</a>
<a href="/sites/default/files/static/dab/decisions/council-decisions/12-1251.pdf">
  In the Case of North Country Ambulance</a>
<a href="/sites/default/files/static/dab/decisions/council-decisions/eagle_air_med.pdf">
  In the Case of Eagle Air Med</a>
<a href="/sites/default/files/static/dab/decisions/council-decisions/m-11-2450.pdf">
  duplicate link to the same decision</a>
<a href="/about/agencies/dab/decisions/council-decisions/index.html">Council Decisions</a>
</body></html>
"""


def test_lists_each_decision_once():
    rows = cc.parse(PAGE)
    assert len(rows) == 3
    assert all(r["url"].endswith(".pdf") for r in rows)
    assert all(r["url"].startswith("https://www.hhs.gov/") for r in rows)


def test_docket_numbers_come_from_the_filename_where_there_is_one():
    rows = {r["url"].rsplit("/", 1)[-1]: r for r in cc.parse(PAGE)}
    assert rows["m-11-2450.pdf"]["docket_no"] == "11-2450"
    assert rows["12-1251.pdf"]["docket_no"] == "12-1251"
    # Many are named after the party instead; a docket is not invented for those.
    assert rows["eagle_air_med.pdf"]["docket_no"] is None


def test_captions_are_kept():
    rows = {r["url"].rsplit("/", 1)[-1]: r for r in cc.parse(PAGE)}
    assert rows["eagle_air_med.pdf"]["caption"] == "In the Case of Eagle Air Med"
