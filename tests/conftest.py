"""Shared fixtures. Everything here is offline: no test touches the network."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Real index-page shapes, reduced to the parts the parser reads. Both eras are
# represented because HHS serves pre-2000 decisions as HTML and later ones as
# PDF, and a parser that only knows one returns an empty list for the other.
ALJ_2016_INDEX = """
<html><body>
<a href="/about/agencies/dab/decisions/alj-decisions/index.html">ALJ Decisions</a>
<a href="/sites/default/files/static/dab/decisions/alj-decisions/2016/cr4685.pdf">
  2016.08.17 CR4685 Rochelle Gardens Care Center, v. CMS</a>
<a href="/sites/default/files/static/dab/decisions/alj-decisions/2016/cr4684.pdf">
  2016.08.16 CR4684 Joseph Peet, v. The Inspector General</a>
<a href="/about/agencies/dab/decisions/alj-decisions/2016/index.html">2016</a>
</body></html>
"""

DAB_1995_INDEX = """
<html><body>
<a href="/sites/default/files/static/dab/decisions/board-decisions/1995/dab1550.html">
  1995.11.27 DAB1550 Neil R. Hirsch, M.D. vs. The Inspector General</a>
<a href="/sites/default/files/static/dab/decisions/board-decisions/1995/dab1549.html">
  1995.11.20 DAB1549 New Jersey Department of Human Services</a>
</body></html>
"""

DAB_2016_INDEX = """
<html><body>
<a href="/sites/default/files/static/dab/decisions/board-decisions/2016/dab2740.pdf">
  2016.10.03; DAB2740; Robert C. Hartnett</a>
</body></html>
"""


@pytest.fixture
def index_pages():
    return {"alj_2016": ALJ_2016_INDEX,
            "dab_1995": DAB_1995_INDEX,
            "dab_2016": DAB_2016_INDEX}


@pytest.fixture
def built_corpus():
    """A built Parquet corpus, or None. Data lives on Hugging Face, not in git,
    so the integrity tests skip rather than fail on a fresh clone."""
    for candidate in (Path("out"), Path("../out"), Path(__file__).parent / "out"):
        files = sorted(candidate.glob("*.parquet")) if candidate.is_dir() else []
        if files:
            return files
    return None
