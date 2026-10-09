"""Upload web/data/decisions.parquet to the Cloudflare R2 bucket the site reads from.

Run after build_web_data.py whenever the corpus changes. The site's PARQUET_URL
in web/app.js points at this bucket's public r2.dev URL, which stays fixed --
re-running this just replaces the object at the same key.

Requires CF_R2_ACCOUNT_ID, CF_R2_ACCESS_KEY_ID, CF_R2_SECRET_ACCESS_KEY in the
environment (same account used by this user's other projects' R2 buckets).

    python upload_web_data.py
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config

BUCKET = "hhs-dab-data"
KEY = "decisions.parquet"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, default=Path("web/data/decisions.parquet"))
    args = ap.parse_args()

    if not args.file.exists():
        raise SystemExit(f"{args.file} not found -- run build_web_data.py first")

    client = boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['CF_R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["CF_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["CF_R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    tc = TransferConfig(multipart_chunksize=64 * 1024 * 1024,
                        multipart_threshold=64 * 1024 * 1024)
    client.upload_file(str(args.file), BUCKET, KEY, Config=tc,
                       ExtraArgs={"ContentType": "application/octet-stream"})
    size_mb = args.file.stat().st_size / 1e6
    print(f"uploaded {args.file} ({size_mb:.1f} MB) -> r2://{BUCKET}/{KEY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
