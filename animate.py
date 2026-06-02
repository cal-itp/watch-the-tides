"""Animated map: watch LA Metro vehicles move over a time window.

Uses folium's TimestampedGeoJson to play back each vehicle's GPS pings, so you get
a time slider + play button and markers that travel along their routes.

2.2M bus pings can't all be animated, so we (1) restrict to a time WINDOW, (2) keep
only the busiest vehicles per mode, and (3) resample each vehicle to a fixed interval.

    uv run python animate.py
    open outputs/vehicle_animation.html

Tunables via env:
    TIDES_DT                 service date (default from config)
    ANIM_START / ANIM_END    window, local HH:MM (default 07:00–09:00, the AM peak)
    ANIM_INTERVAL_SEC        resample interval per vehicle (default 30)
    ANIM_MAX_VEHICLES        busiest N vehicles per mode (default 25)
"""

import os

import pandas as pd
import folium
from folium.plugins import TimestampedGeoJson

import config
import gtfs_colors

START = os.environ.get("ANIM_START", "07:00")
END = os.environ.get("ANIM_END", "09:00")
INTERVAL_SEC = int(os.environ.get("ANIM_INTERVAL_SEC", "30"))
MAX_VEHICLES = int(os.environ.get("ANIM_MAX_VEHICLES", "25"))


def load(label, mode):
    df = pd.read_parquet(os.path.join(config.DATA_DIR, f"{label}_{config.SERVICE_DATE}.parquet"))
    df["mode"] = mode
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"])
    return df.dropna(subset=["latitude", "longitude"])


def vehicle_tracks(df, mode):
    """Yield (vehicle_id, resampled track) for the busiest vehicles in the window."""
    day = df["event_timestamp"].dt.normalize().iloc[0]
    lo = day + pd.Timedelta(START + ":00")
    hi = day + pd.Timedelta(END + ":00")
    win = df[(df["event_timestamp"] >= lo) & (df["event_timestamp"] <= hi)]

    busiest = win["vehicle_id"].value_counts().head(MAX_VEHICLES).index
    for vid in busiest:
        track = (
            win[win["vehicle_id"] == vid]
            .set_index("event_timestamp")
            .sort_index()
            .resample(f"{INTERVAL_SEC}s")
            .first()
            .dropna(subset=["latitude", "longitude"])
        )
        if len(track) >= 2:  # need movement to animate
            yield vid, track


def feature(vid, track, mode, color):
    coords = track[["longitude", "latitude"]].values.tolist()  # GeoJSON = [lon, lat]
    times = [t.isoformat() for t in track.index]
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {
            "times": times,
            "style": {"color": color, "weight": 3, "opacity": 0.7},
            "icon": "circle",
            "iconstyle": {"fillColor": color, "fillOpacity": 0.9, "stroke": False, "radius": 5},
            "popup": f"{mode} vehicle {vid}",
        },
    }


def main():
    bus = load("la_metro_bus", "Bus")
    rail = load("la_metro_rail", "Rail")
    df = pd.concat([bus, rail], ignore_index=True)

    features = []
    used_modes = []
    for mode, g in df.groupby("mode"):
        colors = gtfs_colors.vehicle_colors(g, mode)  # {vehicle_id: hex}
        n = 0
        for vid, track in vehicle_tracks(g, mode):
            features.append(feature(vid, track, mode, colors.get(vid, config.FALLBACK_COLOR)))
            n += 1
        used_modes.append(mode)
        print(f"  {mode}: {n} animated vehicles ({START}–{END}, every {INTERVAL_SEC}s)")

    center = [df["latitude"].median(), df["longitude"].median()]
    m = folium.Map(location=center, zoom_start=11, tiles="cartodbpositron")
    gtfs_colors.add_legend(m, used_modes)
    TimestampedGeoJson(
        {"type": "FeatureCollection", "features": features},
        period=f"PT{INTERVAL_SEC}S",
        add_last_point=True,
        transition_time=150,
        loop=True,
        auto_play=False,
        max_speed=10,
        date_options="HH:mm:ss",
    ).add_to(m)

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    out = os.path.join(config.OUTPUT_DIR, "vehicle_animation.html")
    m.save(out)
    print(f"saved {out}  ({os.path.getsize(out)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
