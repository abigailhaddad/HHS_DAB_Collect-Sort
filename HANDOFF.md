# HHS DAB decisions: handoff

## What this is

Every decision the HHS Departmental Appeals Board publishes, collected daily into a Hugging Face dataset, with a searchable website on top. It's a fork of KMisener90/HHS_DAB_Collect-Sort, which built the first corpus. MIT (`LICENSE.txt`).

- Code: https://github.com/abigailhaddad/HHS_DAB_Collect-Sort
- Data: https://huggingface.co/datasets/abigailhaddad/hhs-dab-decisions (the card is built by `build_card.py`)
- Site: https://hhs-dab.abigailhaddad.com
- What the data can and can't tell you: `LIMITATIONS.md` and `METHODS.md`

## What runs on its own

- `.github/workflows/daily.yml`: collects the Board's index, fetches new decisions, updates the dataset and the site's data file, and deploys the site. The schedule is at the top of the file. The job commits `index_baseline.json` and `index_cache.jsonl` back to the repo, so don't edit those by hand.
- `.github/workflows/checks.yml`: runs `run_checks.py` on every push and pull request.

## Secrets and variables

Settings > Secrets and variables > Actions.

- `HF_TOKEN`: write access to the dataset.
- `CF_R2_ACCOUNT_ID`, `CF_R2_ACCESS_KEY_ID`, `CF_R2_SECRET_ACCESS_KEY`: upload the site's data file to R2.
- `CLOUDFLARE_API_TOKEN`: deploys the site.
- `CLOUDFLARE_ACCOUNT_ID` (variable): `daily.yml` falls back to the current owner's id when it's unset, which fails for anyone else. Set it.

## If you take it over

- Find every place that names the current owner: `grep -rn "abigailhaddad\|KMisener90" . --exclude-dir=.git`
- `config.py` has the dataset, GitHub repo and R2 bucket names, with environment overrides (`HHS_DAB_HF_REPO`, `HHS_DAB_GITHUB_REPO`, `HHS_DAB_R2_BUCKET`).
- The rest can't read `config.py`: `wrangler.jsonc` (Worker name and domain), `web/index.html` (footer links), the fallback account id in `daily.yml`, and the User-Agent in `archive.py`, which names the upstream repo.
- `web/app.js` hardcodes `PARQUET_URL`, the address of a public R2 bucket holding the site's 62 MB data file. It lives on R2 because Cloudflare Pages caps single files at 25 MiB. Make your own bucket with a public address, run `python build_web_data.py && python upload_web_data.py`, and paste the new address in.
- On GitHub the default branch is `cleanup`, not `main`. `main` is stale. The daily job commits to the default branch.
- Copy the existing dataset to your account instead of starting empty. `daily_update.py` downloads the files in `HF_FILES` from the dataset first, and nothing in the repo creates it.

## When it breaks

- Look at the Actions tab, "daily collection". The failing step says why, and warnings that don't fail the run go in the run summary.
- `check_index.py` fails the run if any division-year has fewer decisions than the baseline, or if the index is empty. The Board doesn't unpublish decisions, so a drop means the collector broke.
- The Internet Archive step has a 60-minute budget. A division-year it can't serve comes from `index_cache.jsonl`, and the summary says so.
- hhs.gov refuses plain HTTP clients, so the collector drives a real Chrome window under `xvfb-run`.
- Hand-checked corrections to the Board's index and to corpus rows go in `errata.json`.

## Costs

No model calls. The only cost is GitHub Actions time and your Cloudflare account.

## Run it yourself

`pip install -r requirements-dev.txt`, then `python run_checks.py && python -m pytest tests/`. The README has the commands for each stage.
