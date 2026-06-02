"""Pings-per-hour chart from the downloaded TIDES vehicle_locations.

A simple service profile: how many vehicle-location pings each feed reports per hour
of the day. Run `download.py` first.

    uv run python charts.py   ->  outputs/pings_per_hour.png
"""

import os

import pandas as pd
import matplotlib.pyplot as plt

import config

MODE_COLORS = {"Bus": "#E47200", "Rail": "#0072BC"}  # Metro orange / A-Line blue


def load(label, mode):
    df = pd.read_parquet(os.path.join(config.DATA_DIR, f"{label}_{config.SERVICE_DATE}.parquet"))
    df["mode"] = mode
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"])
    return df


def main():
    df = pd.concat(
        [load("la_metro_bus", "Bus"), load("la_metro_rail", "Rail")],
        ignore_index=True,
    )
    by_hour = (
        df.assign(hour=df["event_timestamp"].dt.hour)
        .groupby(["hour", "mode"]).size().unstack("mode").fillna(0)
    )

    ax = by_hour.plot(kind="bar", figsize=(10, 4), color=[MODE_COLORS[c] for c in by_hour.columns])
    ax.set_xlabel("hour of day (local)")
    ax.set_ylabel("pings")
    ax.set_title(f"LA Metro vehicle pings per hour — {config.SERVICE_DATE}")
    ax.figure.tight_layout()

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    out = os.path.join(config.OUTPUT_DIR, "pings_per_hour.png")
    ax.figure.savefig(out, dpi=120)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
