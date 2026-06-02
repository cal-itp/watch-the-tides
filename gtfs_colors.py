"""Map TIDES vehicles to GTFS colors.

TIDES vehicle_locations has `trip_id_performed` but no route, so we join to LA Metro
GTFS: trip_id -> route_id -> (route_color, route_long_name).

LA Metro's GTFS is regenerated periodically and reassigns trip_ids (rail: daily;
bus: each June/Dec), so we fetch the commit *effective on the service date* from
GitLab instead of today's feed — otherwise the trip_ids don't line up.

  rail -> the line's GTFS route_color (A blue, B red, C green, D purple, E gold, K pink)
  bus  -> service type from route_long_name (config.BUS_TYPE_COLORS), since bus
          route_color is uninformative (almost all black)

Coloring is per *vehicle* (majority matched route), so a train/bus is one color even
when only some of its trips matched. Unmatched vehicles fall back to gray.
"""

import io
import os
import urllib.parse
import urllib.request
import zipfile

import pandas as pd

import config


def _gitlab_commit_zip(repo: str, until_date: str) -> bytes:
    """Download the repo's gtfs zip as it was on/before until_date (YYYY-MM-DD)."""
    proj = urllib.parse.quote(repo, safe="")
    name = repo.split("/")[-1] + ".zip"  # e.g. gtfs_rail.zip

    sha = "master"
    try:
        api = (
            f"https://gitlab.com/api/v4/projects/{proj}/repository/commits"
            f"?until={until_date}T23:59:59Z&per_page=1"
        )
        import json

        with urllib.request.urlopen(api, timeout=30) as r:
            commits = json.load(r)
        if commits:
            sha = commits[0]["id"]
    except Exception as e:  # fall back to current master
        print(f"  [{repo}] commit lookup failed ({e}); using master")

    raw = f"https://gitlab.com/{repo}/-/raw/{sha}/{name}"
    with urllib.request.urlopen(raw, timeout=120) as r:
        return r.read()


def _load_zip(mode: str) -> bytes:
    """Return the date-effective GTFS zip bytes, cached under gtfs/."""
    os.makedirs(config.GTFS_DIR, exist_ok=True)
    repo = config.GTFS_REPOS[mode]
    cache = os.path.join(config.GTFS_DIR, f"{repo.split('/')[-1]}_{config.SERVICE_DATE}.zip")
    if not os.path.exists(cache):
        print(f"  [{mode}] fetching GTFS effective {config.SERVICE_DATE} from {repo}")
        with open(cache, "wb") as f:
            f.write(_gitlab_commit_zip(repo, config.SERVICE_DATE))
    with open(cache, "rb") as f:
        return f.read()


def _read_tables(mode: str):
    z = zipfile.ZipFile(io.BytesIO(_load_zip(mode)))
    trips = pd.read_csv(z.open("trips.txt"), dtype=str)[["trip_id", "route_id"]]
    routes = pd.read_csv(z.open("routes.txt"), dtype=str)
    return trips, routes


def _bus_color(route_long_name: str) -> str:
    name = route_long_name or ""
    for needle, color in config.BUS_TYPE_COLORS:
        if needle.lower() in name.lower():
            return color
    return config.FALLBACK_COLOR


def vehicle_colors(df: pd.DataFrame, mode: str) -> dict:
    """Return {vehicle_id: hex} for one feed's pings, using date-effective GTFS."""
    trips, routes = _read_tables(mode)
    routes = routes.set_index("route_id")

    joined = df.merge(trips, left_on="trip_id_performed", right_on="trip_id", how="left")
    # majority matched route per vehicle
    matched = joined.dropna(subset=["route_id"])
    maj = matched.groupby("vehicle_id")["route_id"].agg(lambda s: s.value_counts().idxmax())

    if mode == "Bus":
        long_names = routes["route_long_name"].to_dict()
        route_to_color = {rid: _bus_color(long_names.get(rid, "")) for rid in maj.unique()}
    else:  # Rail: use the GTFS route_color
        colors = routes["route_color"].to_dict()
        route_to_color = {rid: "#" + str(colors.get(rid, "")).lstrip("#") for rid in maj.unique()}

    colors_by_vehicle = {
        vid: route_to_color.get(maj.get(vid), config.FALLBACK_COLOR)
        for vid in df["vehicle_id"].unique()
    }

    n_assigned = sum(1 for c in colors_by_vehicle.values() if c != config.FALLBACK_COLOR)
    pct_rows = 100 * joined["route_id"].notna().mean()
    print(
        f"  [{mode}] colored {n_assigned}/{len(colors_by_vehicle)} vehicles "
        f"({pct_rows:.0f}% of pings matched a GTFS trip)"
    )
    return colors_by_vehicle


def legend_entries(mode: str) -> list:
    """[(label, hex)] for building a map legend."""
    if mode == "Rail":
        _, routes = _read_tables("Rail")
        out = []
        for _, r in routes.iterrows():
            short = (r.get("route_long_name") or r["route_id"]).replace("Metro ", "")
            out.append((short, "#" + str(r["route_color"]).lstrip("#")))
        return out
    # Bus: the service-type table
    labels = {
        "Rapid": "Rapid bus", "Express": "Express bus", "Limited": "Limited bus",
        "G Line": "G Line (BRT)", "J Line": "J Line (BRT)", "Local": "Local bus",
    }
    return [(labels[n], c) for n, c in config.BUS_TYPE_COLORS]


def add_legend(folium_map, modes):
    """Add a floating legend (lines + bus types present) to a folium map."""
    rows = []
    for mode in modes:
        rows.append(f'<div style="margin-top:4px;font-weight:600">{mode}</div>')
        for label, color in legend_entries(mode):
            rows.append(
                f'<div><span style="display:inline-block;width:11px;height:11px;'
                f'background:{color};margin-right:6px;border:1px solid #888"></span>{label}</div>'
            )
    html = (
        '<div style="position:fixed;bottom:24px;left:12px;z-index:9999;background:white;'
        'padding:8px 10px;border:1px solid #aaa;border-radius:4px;font:12px sans-serif;'
        'max-height:60vh;overflow:auto;box-shadow:0 1px 4px rgba(0,0,0,.3)">'
        + "".join(rows)
        + "</div>"
    )
    import folium

    folium_map.get_root().html.add_child(folium.Element(html))


if __name__ == "__main__":
    for label, mode in [("la_metro_bus", "Bus"), ("la_metro_rail", "Rail")]:
        path = os.path.join(config.DATA_DIR, f"{label}_{config.SERVICE_DATE}.parquet")
        df = pd.read_parquet(path)
        vehicle_colors(df, mode)
