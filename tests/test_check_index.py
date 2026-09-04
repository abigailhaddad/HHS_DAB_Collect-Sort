"""The guard that stops a broken collector from being accepted as a small one."""
import json

import check_index
import jsonl

ROWS = [{"division": "alj", "year": 2020, "decision_no": "CR5791"},
        {"division": "alj", "year": 2020, "decision_no": "CR5790"},
        {"division": "dab", "year": 2020, "decision_no": "3027"}]


def test_counts_are_per_division_year(tmp_path):
    f = tmp_path / "i.jsonl"
    jsonl.write(f, ROWS)
    assert check_index.counts(f) == {"alj:2020": 2, "dab:2020": 1}


def test_new_decisions_are_a_gain_not_a_failure():
    lost, gained = check_index.compare({"alj:2020": 2}, {"alj:2020": 5})
    assert not lost
    assert gained == ["alj:2020: 2 -> 5 (+3)"]


def test_a_year_losing_decisions_is_a_failure():
    # This is the shape of every silent failure this repo has had: a pattern
    # stops matching and the year comes back smaller, or empty.
    lost, _ = check_index.compare({"alj:2020": 347}, {"alj:2020": 0})
    assert lost == ["alj:2020: 347 -> 0 (-347)"]


def test_a_year_disappearing_entirely_is_a_failure():
    lost, _ = check_index.compare({"alj:2020": 5, "dab:2020": 1}, {"dab:2020": 1})
    assert lost == ["alj:2020: 5 -> 0 (-5)"]


def test_a_brand_new_year_is_a_gain():
    lost, gained = check_index.compare({"alj:2025": 3}, {"alj:2025": 3, "alj:2026": 9})
    assert not lost
    assert gained == ["alj:2026: 0 -> 9 (+9)"]


def test_the_committed_baseline_matches_the_committed_index_shape():
    # The baseline is data in the repo; a malformed one would pass every run.
    baseline = json.loads(check_index.Path("index_baseline.json").read_text())
    assert baseline
    assert all(":" in k and isinstance(v, int) and v > 0 for k, v in baseline.items())
    assert {k.split(":")[0] for k in baseline} == {"alj", "dab"}
