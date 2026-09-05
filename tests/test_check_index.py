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


def test_an_unfetched_year_is_unknown_not_lost():
    # The Archive dropped ALJ 1989 on one run and served all 46 on the next.
    # Counted as zero, one flaky request reads as "46 decisions lost" and fails
    # the daily job; the year has to be excluded, not counted.
    lost, gained = check_index.compare({"alj:1989": 46}, {}, unfetched={"alj:1989"})
    assert not lost and not gained


def test_a_year_that_was_fetched_and_shrank_still_fails():
    lost, _ = check_index.compare({"alj:1989": 46}, {"alj:1989": 3},
                                  unfetched={"dab:1975"})
    assert lost == ["alj:1989: 46 -> 3 (-43)"]


def test_unfetched_does_not_suppress_other_years():
    lost, _ = check_index.compare({"alj:1989": 46, "dab:2020": 30},
                                  {"dab:2020": 0}, unfetched={"alj:1989"})
    assert lost == ["dab:2020: 30 -> 0 (-30)"]


def test_update_keeps_the_previous_count_for_an_unfetched_year(tmp_path):
    # A run with a flaky fetch would otherwise write zero for that year and
    # disarm the guard on exactly the years most likely to fail again.
    import json, subprocess, sys, pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    idx = tmp_path / "i.jsonl"
    jsonl.write(idx, [{"division": "dab", "year": 2020, "decision_no": "1"}])
    (tmp_path / "i.meta.json").write_text(json.dumps({"unfetched": ["alj:1989"]}))
    base = tmp_path / "b.json"
    base.write_text(json.dumps({"alj:1989": 46, "dab:2020": 1}))
    subprocess.run([sys.executable, str(root / "check_index.py"), str(idx),
                    "--baseline", str(base), "--update"], check=True,
                   capture_output=True)
    after = json.loads(base.read_text())
    assert after["alj:1989"] == 46          # preserved, not zeroed
    assert after["dab:2020"] == 1
