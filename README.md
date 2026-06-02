# watch-the-tides

A small, self-contained example of pulling [TIDES](https://tides-transit.org) transit data from
Cal-ITP's public `gs://calitp-tides` bucket and visualizing it. It downloads one service day of
`vehicle_locations` for **LA Metro Bus** and **LA Metro Rail**, then produces:

- `outputs/vehicle_animation.html` — an interactive map where vehicles move along their routes over
  time, colored to match GTFS (rail by line, bus by service type).
- `outputs/pings_per_hour.png` — a service-profile chart of pings per hour.

It's meant as a starting point if you want to work with Cal-ITP's TIDES data yourself.

**▶ See it live:** https://docs.calitp.org/watch-the-tides/ — interactive animation + chart, no setup needed.

## The one thing to know: requester-pays

`gs://calitp-tides` is a **requester-pays** bucket. Every request must be billed to a Google Cloud
project **you** own — you pay the egress (pennies for this sample). There is no anonymous download,
and the browser/Console download button is unreliable for these buckets. Use the CLI/API with a
billing project. See Google's docs:

- [Use Requester Pays](https://docs.cloud.google.com/storage/docs/using-requester-pays)
- [Requester Pays overview](https://docs.cloud.google.com/storage/docs/requester-pays) — requests without a billing project fail with `400 UserProjectMissing`.

```bash
# the core idea — bill the request to your own project:
gcloud storage cp "gs://calitp-tides/<path>" . --billing-project=YOUR_PROJECT
```

## Setup

Requires [`uv`](https://docs.astral.sh/uv/) and the `gcloud` CLI.

```bash
uv sync
gcloud auth login                         # a Google account with a billing-enabled GCP project
export TIDES_BILLING_PROJECT=your-project-id
```

## Run

```bash
uv run python download.py     # -> data/la_metro_{bus,rail}_<date>.parquet  (requester-pays download)
uv run python animate.py      # -> outputs/vehicle_animation.html
uv run python charts.py       # -> outputs/pings_per_hour.png
```

Then open `outputs/vehicle_animation.html` and hit play.

Optional tuning (env vars): `TIDES_DT` (service date), and for the animation `ANIM_START`/`ANIM_END`
(window), `ANIM_INTERVAL_SEC`, `ANIM_MAX_VEHICLES`.

## How it works

| file | what |
|------|------|
| `config.py` | billing project (from `TIDES_BILLING_PROJECT`), service date, the two LA Metro feeds, colors |
| `download.py` | pulls one day of each feed from the requester-pays bucket via `gcloud storage` |
| `gtfs_colors.py` | maps vehicles to GTFS colors by joining `trip_id` to LA Metro GTFS |
| `animate.py` | time-animated folium map of moving vehicles |
| `charts.py` | pings-per-hour chart |

### A note on GTFS colors

TIDES `vehicle_locations` carries `trip_id_performed` but no route, so to color vehicles we join to
LA Metro's GTFS (`trip_id → route_id → route_color`). LA Metro regenerates its GTFS frequently and
**reassigns trip IDs**, so `gtfs_colors.py` fetches the GTFS commit **effective on the service date**
from GitLab — otherwise the IDs don't line up. Rail uses the GTFS line color; buses are colored by
service type (Local / Rapid / Express / Limited / BRT), since LA Metro bus GTFS has no useful colors.

## The data

TIDES `vehicle_locations` (GPS pings): `latitude`, `longitude`, `event_timestamp`, `vehicle_id`,
`trip_id_performed`, `speed` (m/s), `heading`, `stop_id`, `current_status`, and more. Browse the
bucket layout at `gs://calitp-tides/vehicle_locations/.../dt=YYYY-MM-DD/`.
