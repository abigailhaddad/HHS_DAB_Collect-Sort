# HHS DAB decisions: operator guide

For whoever keeps this running. You don't need to be a developer to read it, but fixing a break takes one.

## What it does

Every day a GitHub Action checks the HHS Departmental Appeals Board's list of published decisions. It fetches any decision the dataset doesn't have yet, parses it into columns, pushes the result to Hugging Face, and redeploys the website.

It makes no model calls and uses no API that bills per request. The only cost is GitHub Actions time: the last ten daily runs took 6 to 12 minutes each.

## Where things live

| What | Where |
|---|---|
| The data | Hugging Face: `abigailhaddad/hhs-dab-decisions` (`alj.parquet`, `dab.parquet`, `council.parquet`, `slices.parquet`, manifests, dataset card) |
| The code | GitHub: `abigailhaddad/HHS_DAB_Collect-Sort`. A fork of `KMisener90/HHS_DAB_Collect-Sort`, which built the first corpus |
| The website | `hhs-dab.abigailhaddad.com`, a Cloudflare Worker serving `web/` |
| The website's data file | A 63 MB Parquet file in a public Cloudflare R2 bucket (`hhs-dab-data`). Too big for Cloudflare Pages, which caps one file at 25 MiB |
| Daily run results | The repo's Actions tab, and the run summary page |

## The daily job

`.github/workflows/daily.yml`, 06:17 UTC, with a 120-minute limit. In order:

1. Run the tests. A broken parser stops the run here, before it touches anything.
2. `collect_index.py` rebuilds the Board's own index from the Internet Archive, then tops up the current year from hhs.gov through a real Chrome (under Xvfb). hhs.gov returns 403 to automated clients, and the Archive is slow, so the Archive walk gets a 60-minute budget.
3. `check_index.py` compares the index with `index_baseline.json`. **It fails the run if any division-year has fewer decisions than before, or if the index is empty.** The Board doesn't unpublish decisions, so a drop means the collector broke.
4. `daily_update.py` fetches what's missing, rebuilds the Parquet files and dataset card, pushes everything to Hugging Face in one commit, rebuilds the website's data file and uploads it to R2.
5. `npx wrangler deploy` publishes the site.

`index_baseline.json` and `index_cache.jsonl` are committed back to the repo by the job (a "Baseline: newly published decisions" commit). Don't edit them by hand.

## Secrets and variables

Set under the repo's Settings, Secrets and variables, Actions.

| Name | Used for |
|---|---|
| `HF_TOKEN` (secret) | Pushing to the Hugging Face dataset. Needs write access |
| `CF_R2_ACCOUNT_ID`, `CF_R2_ACCESS_KEY_ID`, `CF_R2_SECRET_ACCESS_KEY` (secrets) | Uploading the website's data file to R2 |
| `CLOUDFLARE_API_TOKEN` (secret) | Deploying the site with wrangler |
| `CLOUDFLARE_ACCOUNT_ID` (variable, optional) | Your Cloudflare account. If unset, the workflow uses the current owner's id, which will fail for you. Set it |

## Moving it to a new owner

Everything below is a place that names the current owner.

1. **`config.py`.** The Hugging Face dataset, the GitHub repo and the R2 bucket. Edit the defaults or set `HHS_DAB_HF_REPO`, `HHS_DAB_GITHUB_REPO`, `HHS_DAB_R2_BUCKET`. This also fixes the links in the generated dataset card.
2. **`wrangler.jsonc`.** The Worker name (`hhs-dab`) and the route `hhs-dab.abigailhaddad.com`.
3. **`web/app.js`.** `PARQUET_URL` is the current owner's public R2 address. Create your own bucket, turn on its public address, upload once with `python build_web_data.py && python upload_web_data.py`, and paste the new address in.
4. **`web/index.html`.** The footer links to the dataset, the GitHub repo and the author.
5. **`.github/workflows/daily.yml`.** The Cloudflare account id (see the variable above).
6. **`archive.py`.** The User-Agent still names the upstream repo (`KMisener90/...`). Change it to yours so the Internet Archive knows who is asking.
7. **The default branch.** On GitHub the default branch is `cleanup`, not `main`. `main` is four commits from 2026-10-09 and is stale. The daily job commits to the default branch, so keep the real code on whichever branch GitHub treats as default.
8. **The dataset.** Create the Hugging Face dataset and push the data files and manifests once from a built `out/` directory (the list is `HF_FILES` in `daily_update.py`). The daily job downloads the existing corpus first and can't start from empty.

## When it fails

A failed run turns the Actions tab red and the failing step says why. The common causes, from the repo's history:

- **The Archive is slow or missing a year.** The Archive step runs out of its 60 minutes. A division-year it can't serve comes from `index_cache.jsonl` instead, and the run summary lists those as `from_cache`.
- **hhs.gov blocks the browser.** The live top-up fails. The failure shows in the collect step.
- **A year "lost decisions."** `check_index.py` names the division-year. Look at whether the Archive or the parser changed before touching the baseline.
- **Two index entries point at one decision.** `daily_update.py` warns and drops the duplicate. Add the fix to `errata.json`.
- **A push to Hugging Face times out.** The push retries and checks whether the commit landed. It's one commit, so the dataset is never half-updated.

Warnings that don't stop the run are written to the run summary page. Read it now and then.

## What to know about the data

Read `LIMITATIONS.md` and `METHODS.md` before citing anything. In short:

- The Appellate and ALJ files are checked against the Board's own index. The Council file is a selection the Board chose to post (224 decisions, 2001 to 2015), not everything the Council decided.
- Category labels (`slices.parquet`) are a heuristic. No precision or recall is claimed.
- Nothing in the data is model-generated.
- Some old scans extract as garbled text without being flagged.
- The code is MIT (`LICENSE.txt`, copyright Kevin Misener and contributors). The decisions are US government works and not subject to copyright.

## Running it yourself

```
pip install -r requirements-dev.txt
playwright install chromium
python run_checks.py && python -m pytest tests/
```

The README has the step-by-step commands for each stage. `python daily_update.py --skip-push` builds everything locally without pushing to Hugging Face. It still needs the Hugging Face corpus to start from.
