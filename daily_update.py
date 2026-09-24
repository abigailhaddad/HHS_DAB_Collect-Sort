"""Everything daily.yml runs after collect_index.py: find what's new, fetch it,
fold it into the corpus, push to Hugging Face, and rebuild the site's data file.

Shells out to this repo's own scripts in the same order the manual run this
week used -- audit_completeness -> fetch_missing -> fetch_via_browser ->
extract -> build_dataset -> merge -> link_corpora -> build_slices ->
build_manifests -> build_card -> push -> build_web_data -- rather than
reimplementing any of them, so a change to one of those stays in one place.

    python daily_update.py --index decisions_index.jsonl

Needs HF_TOKEN in the environment to push. Fetching anything published since
the Archive's last crawl needs a browser; --launch-browser (headless=False,
confirmed working against hhs.gov directly -- see collect_index.py's
docstring) is what the daily workflow passes, under Xvfb.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

import build_dataset

CORPORA = ("alj", "dab")
HF_REPO = "abigailhaddad/hhs-dab-decisions"
HF_FILES = ["alj.parquet", "dab.parquet", "council.parquet", "slices.parquet",
            "manifest_alj.json", "manifest_dab.json", "manifest_council.json",
            "README.md"]


def run(cmd: list[str]) -> None:
    print(f"$ {' '.join(str(c) for c in cmd)}", flush=True)
    subprocess.run(cmd, check=True)


def ensure_corpus(out_dir: Path) -> None:
    """Download the published corpus from HF if this checkout doesn't have
    one -- true of every CI run, since out/ is gitignored by design."""
    if (out_dir / "alj.parquet").exists():
        return
    from huggingface_hub import hf_hub_download
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in HF_FILES:
        if name == "README.md":
            continue
        path = hf_hub_download(repo_id=HF_REPO, repo_type="dataset", filename=name)
        (out_dir / name).write_bytes(Path(path).read_bytes())
        print(f"downloaded {name}", flush=True)


def split_missing(missing_path: Path, tmp_dir: Path) -> dict[str, Path]:
    by_division: dict[str, list[dict]] = {c: [] for c in CORPORA}
    for line in missing_path.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        by_division.setdefault(r["division"], []).append(r)

    out = {}
    for division, rows in by_division.items():
        if not rows:
            continue
        path = tmp_dir / f"missing_{division}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        out[division] = path
    return out


def fetch_and_build(division: str, missing_path: Path, tmp_dir: Path,
                    index_path: Path, launch_browser: bool, delay: float) -> Path | None:
    decisions_dir = tmp_dir / f"decisions_{division}"
    run(["python3", "fetch_missing.py", str(missing_path),
         "--out-dir", str(decisions_dir), "--delay", str(delay)])

    failures = decisions_dir / "_failures.jsonl"
    if failures.exists() and failures.stat().st_size:
        still_missing = tmp_dir / f"still_missing_{division}.jsonl"
        still_missing.write_bytes(failures.read_bytes())
        failures.unlink()  # fetch_via_browser writes its own failure log
        cmd = ["python3", "fetch_via_browser.py", str(still_missing),
               "--out-dir", str(decisions_dir), "--delay", str(max(delay, 1.5))]
        cmd += ["--launch-browser"] if launch_browser else []
        run(cmd)

    fetched = [p for p in decisions_dir.iterdir()
              if p.is_file() and not p.name.startswith("_")]
    if not fetched:
        print(f"{division}: nothing actually fetched (all misses), skipping build")
        return None

    extracted = tmp_dir / f"extracted_{division}.jsonl"
    run(["python3", "extract.py", str(decisions_dir), "-o", str(extracted)])

    new_out = tmp_dir / f"new_out_{division}"
    run(["python3", "build_dataset.py", str(extracted), "--corpus", division,
         "-o", str(new_out), "--index", str(index_path)])
    return new_out / f"{division}.parquet"


def merge_into_corpus(out_dir: Path, division: str, new_parquet: Path) -> int:
    canonical = [f.name for f in build_dataset.SCHEMA]
    existing = pq.read_table(out_dir / f"{division}.parquet").select(canonical)
    new = pq.read_table(new_parquet).select(canonical)

    existing_ids = set(existing.column("id").to_pylist())
    keep_mask = [i not in existing_ids for i in new.column("id").to_pylist()]
    if not all(keep_mask):
        new = new.filter(pa.array(keep_mask))
    if new.num_rows == 0:
        return 0

    merged = pa.concat_tables([existing, new])
    pq.write_table(merged, out_dir / f"{division}.parquet",
                   compression="zstd", compression_level=9)
    return new.num_rows


def push_to_hf(out_dir: Path) -> None:
    import os
    from huggingface_hub import HfApi
    api = HfApi(token=os.environ["HF_TOKEN"])
    for name in HF_FILES:
        path = out_dir / name
        if not path.exists():
            continue
        api.upload_file(path_or_fileobj=str(path), path_in_repo=name,
                        repo_id=HF_REPO, repo_type="dataset",
                        commit_message="Daily update: new decisions")
        print(f"pushed {name} to {HF_REPO}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=Path, default=Path("decisions_index.jsonl"))
    ap.add_argument("--out-dir", type=Path, default=Path("out"))
    ap.add_argument("--tmp-dir", type=Path, default=Path("/tmp/daily_update"))
    ap.add_argument("--launch-browser", action="store_true")
    ap.add_argument("--delay", type=float, default=0.8)
    ap.add_argument("--skip-push", action="store_true",
                    help="build everything locally but don't push to HF "
                         "(for testing)")
    args = ap.parse_args()

    args.tmp_dir.mkdir(parents=True, exist_ok=True)
    ensure_corpus(args.out_dir)

    missing_path = args.tmp_dir / "missing.jsonl"
    run(["python3", "audit_completeness.py", str(args.index),
         str(args.out_dir / "dab.parquet"), str(args.out_dir / "alj.parquet"),
         "--missing-out", str(missing_path)])

    if not missing_path.exists() or missing_path.stat().st_size == 0:
        print("\nno missing decisions -- corpus already matches the index")
    else:
        by_division = split_missing(missing_path, args.tmp_dir)
        total_new = 0
        for division, path in by_division.items():
            new_parquet = fetch_and_build(division, path, args.tmp_dir, args.index,
                                          args.launch_browser, args.delay)
            if new_parquet is None:
                continue
            n = merge_into_corpus(args.out_dir, division, new_parquet)
            print(f"{division}: merged {n} new decision(s) into the corpus")
            total_new += n

        if total_new:
            run(["python3", "link_corpora.py", str(args.out_dir / "dab.parquet"),
                 str(args.out_dir / "alj.parquet")])
            corpus_files = [str(args.out_dir / f"{c}.parquet") for c in CORPORA]
            council = args.out_dir / "council.parquet"
            if council.exists():
                corpus_files.append(str(council))
            run(["python3", "build_slices.py", *corpus_files,
                 "-o", str(args.out_dir / "slices.parquet")])
            run(["python3", "build_manifests.py", "--dir", str(args.out_dir)])

    run(["python3", "build_card.py", "--dir", str(args.out_dir), "--index", str(args.index)])

    if not args.skip_push:
        push_to_hf(args.out_dir)
    else:
        print("--skip-push: built locally, not pushed to HF")

    run(["python3", "build_web_data.py", "--dir", str(args.out_dir),
         "-o", "web/data/decisions.parquet"])
    if not args.skip_push:
        run(["python3", "upload_web_data.py"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
