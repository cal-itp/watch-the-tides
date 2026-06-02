"""Static map of *every* LA Metro bus route present in one day of TIDES data.

animate.py shows only the busiest ~25 vehicles (~10 routes); this draws one
representative track per route so you see the whole network at once, each route
in its own color.

    uv run python download.py        # need data/la_metro_bus_<date>.parquet
    uv run python all_routes_map.py  # -> outputs/all_bus_routes_map.html
"""

import colorsys
import os

import folium
import pandas as pd

import config
import gtfs_colors


def colors_for(routes: list[str]) -> dict:
    """A distinct hex color per route_id, spread around the HSV wheel."""
    out = {}
    for i, rid in enumerate(routes):
        r, g, b = colorsys.hsv_to_rgb((i * 0.61803398875) % 1.0, 0.65, 0.90)
        out[rid] = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
    return out


def main() -> None:
    df = pd.read_parquet(os.path.join(config.DATA_DIR, f"la_metro_bus_{config.SERVICE_DATE}.parquet"))
    df = df.dropna(subset=["latitude", "longitude"])

    trips, routes = gtfs_colors._read_tables("Bus")  # date-effective GTFS
    names = routes.set_index("route_id")
    j = df.merge(trips, left_on="trip_id_performed", right_on="trip_id", how="left").dropna(subset=["route_id"])

    color = colors_for(sorted(j["route_id"].unique()))

    m = folium.Map(location=[df["latitude"].median(), df["longitude"].median()],
                   zoom_start=10, tiles="cartodbpositron")
    legend = []
    for rid, g in j.groupby("route_id"):
        trip = g["trip_id_performed"].value_counts().idxmax()  # busiest trip on this route
        track = g[g["trip_id_performed"] == trip].sort_values("event_timestamp")[["latitude", "longitude"]]
        if len(track) < 2:
            continue
        short, long = names["route_short_name"].get(rid, rid), names["route_long_name"].get(rid, "")
        folium.PolyLine(track.values.tolist(), color=color[rid], weight=3, opacity=0.75,
                        tooltip=f"{short}: {long}").add_to(m)
        legend.append((str(short), color[rid]))

    legend.sort(key=lambda e: (0, int(e[0])) if e[0].isdigit() else (1, e[0]))  # 2, 4, ... 720
    rows = "".join(
        f'<div><span style="display:inline-block;width:11px;height:11px;background:{c};'
        f'margin-right:6px;border:1px solid #888"></span>{label}</div>'
        for label, c in legend
    )
    m.get_root().html.add_child(folium.Element(
        '<div style="position:fixed;top:12px;right:12px;z-index:9999;background:white;'
        'padding:8px 10px;border:1px solid #aaa;border-radius:4px;font:12px sans-serif;'
        'max-height:80vh;overflow:auto;box-shadow:0 1px 4px rgba(0,0,0,.3)">'
        f'<div style="margin-bottom:4px;font-weight:600">Bus routes ({len(legend)})</div>{rows}</div>'
    ))

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    out = os.path.join(config.OUTPUT_DIR, "all_bus_routes_map.html")
    m.save(out)
    print(f"Drew {len(legend)} of {names.index.nunique()} routes -> {out}")


if __name__ == "__main__":
    main()
