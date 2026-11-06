"""The names a new owner changes live in config.py, and the scripts read them."""
import importlib
import json

import pytest

import config


@pytest.fixture
def reload_config(monkeypatch):
    def _reload(**env):
        for k in ("HHS_DAB_HF_REPO", "HHS_DAB_GITHUB_REPO", "HHS_DAB_R2_BUCKET"):
            monkeypatch.delenv(k, raising=False)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        return importlib.reload(config)
    yield _reload
    for k in ("HHS_DAB_HF_REPO", "HHS_DAB_GITHUB_REPO", "HHS_DAB_R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    importlib.reload(config)


def test_defaults_are_the_current_owners(reload_config):
    c = reload_config()
    assert c.HF_REPO == "abigailhaddad/hhs-dab-decisions"
    assert c.GITHUB_REPO == "abigailhaddad/HHS_DAB_Collect-Sort"
    assert c.GITHUB_URL == "https://github.com/abigailhaddad/HHS_DAB_Collect-Sort"
    assert c.R2_BUCKET == "hhs-dab-data"


def test_environment_overrides_every_name(reload_config):
    c = reload_config(HHS_DAB_HF_REPO="them/dab", HHS_DAB_GITHUB_REPO="them/code",
                      HHS_DAB_R2_BUCKET="their-bucket")
    assert (c.HF_REPO, c.GITHUB_REPO, c.R2_BUCKET) == ("them/dab", "them/code", "their-bucket")
    assert c.GITHUB_URL == "https://github.com/them/code"


def test_the_scripts_take_their_names_from_config():
    import daily_update
    import upload_web_data
    assert daily_update.HF_REPO == config.HF_REPO
    assert upload_web_data.BUCKET == config.R2_BUCKET


def test_the_dataset_card_names_the_configured_repo(tmp_path, reload_config):
    import build_card
    from test_build_card import _corpus
    reload_config(HHS_DAB_GITHUB_REPO="them/code")
    importlib.reload(build_card)
    _corpus(tmp_path, "dab", [("2740", "2020-01-02", ["A Judge"], ["affirmed"])])
    d = _corpus(tmp_path, "alj", [("CR1", "1999-05-06", [], [])])
    idx = tmp_path / "index.jsonl"
    idx.write_text(json.dumps({"division": "dab", "year": 2020, "decision_no": "2740"}) + "\n")
    card = build_card.render(d, idx)
    assert "[them/code](https://github.com/them/code)" in card
    assert "abigailhaddad" not in card
    reload_config()
    importlib.reload(build_card)
