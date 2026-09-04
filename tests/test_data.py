"""Integrity of a built corpus.

Skipped when there is no Parquet to check: the data lives on Hugging Face, not
in git, so a fresh clone has nothing to test until build_dataset.py has run.
"""
import re

import pytest

pq = pytest.importorskip("pyarrow.parquet")

import build_dataset  # noqa: E402


@pytest.fixture
def table(built_corpus):
    if not built_corpus:
        pytest.skip("no built corpus; run build_dataset.py first")
    import pyarrow as pa
    return pa.concat_tables([pq.read_table(p) for p in built_corpus])


def col(t, name):
    return t.column(name).to_pylist()


def test_schema_matches_the_declared_one(table):
    assert set(table.column_names) == {f.name for f in build_dataset.SCHEMA}


def test_ids_are_unique(table):
    ids = col(table, "id")
    assert len(ids) == len(set(ids))


def test_empty_text_is_flagged_not_hidden(table):
    # Three decisions extract to roughly one character per page. They stay in
    # the corpus -- dropping them would hide the gap -- but nothing downstream
    # should mistake them for a decision with no matches.
    for text, ok in zip(col(table, "text"), col(table, "text_layer_ok")):
        if not (text and text.strip()):
            assert ok is False


def test_no_website_furniture_survives(table):
    import clean
    dirty = [i for i, t, g in zip(col(table, "id"), col(table, "text"),
                                  col(table, "clean_guard_tripped"))
             if clean.has_chrome(t) and not g]
    assert not dirty, f"{len(dirty)} records still carry site chrome, e.g. {dirty[:3]}"


def test_years_are_plausible(table):
    # The Board's first decisions are 1974; nothing predates that.
    years = [y for y in col(table, "year") if y is not None]
    assert years
    assert min(years) >= 1974
    assert max(years) <= 2027


def test_dates_agree_with_years(table):
    for d, y in zip(col(table, "decision_date"), col(table, "year")):
        if d is not None:
            assert d.year == y


def test_decision_numbers_are_well_formed(table):
    bad = [n for n in col(table, "decision_no")
           if n is not None and not re.fullmatch(r"(CR)?\d{1,5}", n)]
    assert not bad, f"malformed decision numbers: {bad[:5]}"


def test_alj_numbers_carry_the_cr_prefix(table):
    for corpus, no in zip(col(table, "corpus"), col(table, "decision_no")):
        if corpus == "alj" and no is not None and no.startswith("CR"):
            assert no[2:].isdigit()


def test_docket_numbers_are_never_the_word_and(table):
    # ", and 77-9" used to parse "and" as a docket number.
    for dockets in col(table, "docket_nos"):
        assert "AND" not in (dockets or [])


def test_header_coverage_has_not_regressed(table):
    n = table.num_rows
    for field, floor in (("decision_no", 0.85), ("decision_date", 0.90),
                         ("tribunal", 0.85), ("docket_nos", 0.85)):
        got = sum(1 for v in col(table, field) if v)
        assert got / n >= floor, f"{field} coverage {got/n:.1%} below {floor:.0%}"
