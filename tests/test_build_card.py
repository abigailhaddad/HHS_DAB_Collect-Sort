"""The card's numbers have to come from the data, not from prose."""
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import build_card
import build_dataset


def _corpus(tmp_path, corpus, rows):
    """A minimal corpus with the columns the card reads."""
    import datetime as dt
    cols = {f.name: [] for f in build_dataset.SCHEMA}
    for i, (no, date, judges, disp) in enumerate(rows):
        for f in build_dataset.SCHEMA:
            cols[f.name].append(None)
        for k, v in (("id", f"{corpus}-{i}"), ("corpus", corpus),
                     ("decision_no", no),
                     ("decision_date", dt.date.fromisoformat(date)),
                     ("judges", judges), ("dispositions", disp),
                     ("provider_ids", []), ("text", "x")):
            cols[k][-1] = v
    t = pa.Table.from_pydict({f.name: cols[f.name] for f in build_dataset.SCHEMA},
                             schema=build_dataset.SCHEMA)
    d = tmp_path / "out"
    d.mkdir(exist_ok=True)
    pq.write_table(t, d / f"{corpus}.parquet")
    return d


@pytest.fixture
def built(tmp_path):
    _corpus(tmp_path, "dab", [("2740", "2020-01-02", ["A Judge"], ["affirmed"]),
                              ("2741", "2021-03-04", [], [])])
    d = _corpus(tmp_path, "alj", [("CR1", "1999-05-06", ["B Judge"], [])])
    idx = tmp_path / "index.jsonl"
    idx.write_text("\n".join(json.dumps(r) for r in [
        {"division": "dab", "year": 2020, "decision_no": "2740"},
        {"division": "dab", "year": 2021, "decision_no": "2741"},
        {"division": "alj", "year": 1999, "decision_no": "CR1"},
        {"division": "alj", "year": 1999, "decision_no": None},   # unnumbered
    ]) + "\n")
    return d, idx


def test_counts_and_spans_come_from_the_parquet(built):
    card = build_card.render(*built)
    assert "| 2 |" in card and "2020-01-02 – 2021-03-04" in card
    assert "| 1 |" in card and "1999-05-06 – 1999-05-06" in card


def test_completeness_is_computed_against_the_index(built):
    card = build_card.render(*built)
    # 4 listed, 3 numbered, 3 present, 1 outside the check.
    assert "of the 4 listings" in card
    assert "all 3 of the 3 that carry an identifiable decision number" in card
    assert "the other 1 sit outside the check" in card


def test_field_coverage_is_measured_not_asserted(built):
    card = build_card.render(*built)
    assert "50% of Appellate, 100% of ALJ" in card or "50%" in card


def test_a_missing_index_does_not_fake_a_completeness_claim(built):
    d, _ = built
    card = build_card.render(d, d / "nope.jsonl")
    assert "not measured in this build" in card
    assert "identifiable decision number are here" not in card
