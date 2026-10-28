"""push_to_hf's timeout handling, against a fake HfApi (no network).

Regression for 2026-10-24 / 2026-10-28: the commit POST timed out after HF
had already committed, and the run died half-pushed."""
from types import SimpleNamespace

import httpx
import huggingface_hub
import pytest

import daily_update


class FakeApi:
    def __init__(self, token=None, outcomes=()):
        self.commits = [SimpleNamespace(commit_id="old", title="Daily update: new decisions")]
        self.outcomes = list(outcomes)
        self.calls = 0

    def list_repo_commits(self, repo, repo_type):
        return list(reversed(self.commits))

    def create_commit(self, repo_id, repo_type, operations, commit_message):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if outcome in ("ok", "landed_then_timeout"):
            self.commits.append(SimpleNamespace(commit_id=f"c{self.calls}", title=commit_message))
        if outcome != "ok":
            raise httpx.ReadTimeout("The read operation timed out")


@pytest.fixture
def out_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "x")
    monkeypatch.setattr("time.sleep", lambda s: None)
    for name in ("alj.parquet", "README.md"):
        (tmp_path / name).write_text(name)
    return tmp_path


def run(monkeypatch, out_dir, outcomes):
    api = FakeApi(outcomes=outcomes)
    monkeypatch.setattr(huggingface_hub, "HfApi", lambda token=None: api)
    daily_update.push_to_hf(out_dir)
    return api


def test_timeout_after_commit_landed_is_not_retried(monkeypatch, out_dir):
    api = run(monkeypatch, out_dir, ["landed_then_timeout"])
    assert api.calls == 1 and len(api.commits) == 2


def test_timeout_without_commit_retries(monkeypatch, out_dir):
    api = run(monkeypatch, out_dir, ["timeout", "ok"])
    assert api.calls == 2 and len(api.commits) == 2


def test_gives_up_after_all_attempts(monkeypatch, out_dir):
    with pytest.raises(httpx.ReadTimeout):
        run(monkeypatch, out_dir, ["timeout"] * 4)


def test_all_present_files_go_in_one_commit(monkeypatch, out_dir):
    seen = {}
    api = FakeApi(outcomes=["ok"])
    orig = api.create_commit
    def spy(**kw):
        seen["paths"] = [op.path_in_repo for op in kw["operations"]]
        return orig(**kw)
    api.create_commit = spy
    monkeypatch.setattr(huggingface_hub, "HfApi", lambda token=None: api)
    daily_update.push_to_hf(out_dir)
    assert seen["paths"] == ["alj.parquet", "README.md"]
