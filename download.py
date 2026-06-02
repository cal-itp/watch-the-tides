"""Download one service day of LA Metro Bus + Rail vehicle_locations from TIDES.

gs://calitp-tides is a *requester-pays* bucket: every request must be billed to a
project you own. This script uses the `gcloud storage` CLI with --billing-project,
which is the most reliable path (it uses your active gcloud account):

    gcloud storage cp "gs://calitp-tides/<path>" . --billing-project=<project>

The pure-Python equivalent (see README) passes ``user_project`` on the bucket:

    bucket = client.bucket("calitp-tides", user_project="<project>")

...but the Python client uses Application Default Credentials (ADC), which are
separate from `gcloud auth login`. If you prefer the client, first run:
    gcloud auth application-default login

Each feed is written to its own parquet file so bus and rail stay separated:
    data/la_metro_bus_<date>.parquet
    data/la_metro_rail_<date>.parquet
"""

import os
import subprocess
import tempfile

import pandas as pd
import pyarrow.parquet as pq

import config


def feed_prefix(org: str, base64_url: str, dt: str) -> str:
    return (
        f"gs://{config.BUCKET}/{config.DATASET}/"
        f"organization_source_record_id={org}/"
        f"base64_url={base64_url}/"
        f"dt={dt}/"
    )


def download_feed(label: str, org: str, base64_url: str, dt: str) -> str | None:
    prefix = feed_prefix(org, base64_url, dt)
    os.makedirs(config.DATA_DIR, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        # Pull every data_*.parquet for this feed/day, billed to our project.
        result = subprocess.run(
            [
                "gcloud", "storage", "cp",
                f"{prefix}*.parquet", tmp,
                "--billing-project", config.BILLING_PROJECT,
            ],
            capture_output=True, text=True,
        )
        files = sorted(f for f in os.listdir(tmp) if f.endswith(".parquet"))
        if not files:
            print(f"  [{label}] no parquet under {prefix}\n    {result.stderr.strip()[:200]}")
            return None

        frames = [pq.read_table(os.path.join(tmp, f)).to_pandas() for f in files]
        total_bytes = sum(os.path.getsize(os.path.join(tmp, f)) for f in files)

    df = pd.concat(frames, ignore_index=True)
    out = os.path.join(config.DATA_DIR, f"{label}_{dt}.parquet")
    df.to_parquet(out, index=False)
    print(f"  [{label}] {len(files)} file(s), {total_bytes/1e6:.1f} MB, {len(df):,} rows -> {out}")
    return out


def main() -> None:
    if not config.BILLING_PROJECT:
        raise SystemExit(
            "Set a billing project first (the bucket is requester-pays):\n"
            "  export TIDES_BILLING_PROJECT=your-gcp-project-id"
        )
    dt = config.SERVICE_DATE
    print(f"Billing project: {config.BILLING_PROJECT}")
    print(f"Bucket: gs://{config.BUCKET} (requester-pays)")
    print(f"Service date: {dt}\n")

    for label, (org, base64_url) in config.FEEDS.items():
        download_feed(label, org, base64_url, dt)


if __name__ == "__main__":
    main()
