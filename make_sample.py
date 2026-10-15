"""Thin a full day of downloaded vehicle_locations into the committed sample.

The real feeds are big (LA Metro bus is ~2.2M pings / ~100 MB a day), too big to
check into git. This produces a small, representative slice that still drives the
default AM-peak animation, so the demo runs with **no GCP account** -- see
`sample/README.md`.

What it keeps (a thinned slice, not the whole day):
  * the AM-peak WINDOW only (06:00-10:00 local, around animate.py's 07:00-09:00)
  * all rail vehicles; the busiest BUS_VEHICLES bus vehicles (what the animation
    surfaces anyway)
  * one ping per INTERVAL_SEC per vehicle

Regenerate (needs the full files in data/ from download.py):
    uv run python download.py
    uv run python make_sample.py        # -> sample/la_metro_{bus,rail}_<date>.parquet
"""

import os

import pandas as pd

import config

SAMPLE_DIR = "sample"
WINDOW = ("06:00", "10:00")  # local; brackets animate.py's default 07:00-09:00
INTERVAL_SEC = 20            # one ping per vehicle per 20s
BUS_VEHICLES = 60            # busiest bus vehicles to keep (rail keeps all)


def thin(df: pd.DataFrame, max_vehicles: int | None) -> pd.DataFrame:
    df = df.copy()
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"])
    day = df["event_timestamp"].dt.normalize().iloc[0]
    lo = day + pd.Timedelta(WINDOW[0] + ":00")
    hi = day + pd.Timedelta(WINDOW[1] + ":00")
    win = df[(df["event_timestamp"] >= lo) & (df["event_timestamp"] <= hi)]

    if max_vehicles:
        keep = win["vehicle_id"].value_counts().head(max_vehicles).index
        win = win[win["vehicle_id"].isin(keep)]

    out = [
        g.set_index("event_timestamp").sort_index()
        .resample(f"{INTERVAL_SEC}s").first().dropna(subset=["latitude", "longitude"])
        .reset_index()
        for _, g in win.groupby("vehicle_id")
    ]
    return pd.concat(out, ignore_index=True) if out else win.iloc[:0]


def main() -> None:
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    dt = config.SERVICE_DATE
    for label, max_vehicles in [("la_metro_rail", None), ("la_metro_bus", BUS_VEHICLES)]:
        src = os.path.join("data", f"{label}_{dt}.parquet")
        if not os.path.exists(src):
            raise SystemExit(f"missing {src} -- run `uv run python download.py` first")
        thinned = thin(pd.read_parquet(src), max_vehicles)
        out = os.path.join(SAMPLE_DIR, f"{label}_{dt}.parquet")
        thinned.to_parquet(out, index=False)
        print(
            f"  [{label}] {len(thinned):,} rows, "
            f"{thinned['vehicle_id'].nunique()} vehicles, "
            f"{os.path.getsize(out) / 1e6:.1f} MB -> {out}"
        )


if __name__ == "__main__":
    main()
