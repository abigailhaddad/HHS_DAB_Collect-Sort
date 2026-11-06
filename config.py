"""Where this project lives: the names a new owner changes.

Every value can be overridden with an environment variable, and the defaults
are the current owner's, so nothing changes until you set one. Files that can't
import Python (web/index.html, web/app.js, wrangler.jsonc, the workflow files)
have their own copies of some of these; HANDOFF.md lists every one.
"""
from __future__ import annotations

import os

# The Hugging Face dataset daily_update.py pushes to and build_card.py describes.
HF_REPO = os.environ.get("HHS_DAB_HF_REPO", "abigailhaddad/hhs-dab-decisions")

# The GitHub repo the dataset card points to as "build code and method".
GITHUB_REPO = os.environ.get("HHS_DAB_GITHUB_REPO", "abigailhaddad/HHS_DAB_Collect-Sort")
GITHUB_URL = f"https://github.com/{GITHUB_REPO}"

# The Cloudflare R2 bucket upload_web_data.py writes the site's data file to.
R2_BUCKET = os.environ.get("HHS_DAB_R2_BUCKET", "hhs-dab-data")
