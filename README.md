# watch-the-tides

A small, self-contained example of pulling [TIDES](https://tides-transit.org) transit data from
Cal-ITP's public `gs://calitp-tides` bucket and visualizing it. It downloads one service day of
`vehicle_locations` for **LA Metro Bus** and **LA Metro Rail**, then produces:

- `outputs/vehicle_animation.html` — an interactive map where vehicles move along their routes over
  time, colored to match GTFS (rail by line, bus by service type).
- `outputs/all_bus_routes_map.html` — a static map of **every** bus route that ran that day, one
  representative track each, in its own color (see [Why the animation shows only some routes](#why-the-animation-shows-only-some-routes)).
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
uv run python all_routes_map.py  # -> outputs/all_bus_routes_map.html  (all bus routes that ran)
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
| `all_routes_map.py` | static map of every bus route that operated, one representative track each |
| `charts.py` | pings-per-hour chart |

### A note on GTFS colors

TIDES `vehicle_locations` carries `trip_id_performed` but no route, so to color vehicles we join to
LA Metro's GTFS (`trip_id → route_id → route_color`). LA Metro regenerates its GTFS frequently and
**reassigns trip IDs**, so `gtfs_colors.py` fetches the GTFS commit **effective on the service date**
from GitLab — otherwise the IDs don't line up. Rail uses the GTFS line color; buses are colored by
service type (Local / Rapid / Express / Limited / BRT).

## Why the animation shows only some routes

The animation isn't the whole picture. `animate.py` deliberately limits how much it renders (so the
file stays light and playable), so it surfaces only a fraction of the bus network. That's a
*rendering* cap, not a data gap — `download.py` already pulls every shard, and the downloaded data
covers nearly all routes that operated.

To see the full network, run `all_routes_map.py`, which draws one representative track per route.

### A note on the parquet shards

Each `dt=<date>/` partition holds several `data_*.parquet` shards. Their sizes vary, but **not** by
route — BigQuery's export splits a partition into roughly **equal-sized** files (e.g. eight ~13 MB
shards for one bus day), and each shard is an arbitrary slice of rows that already contains *all*
routes. So bigger feeds/busier days just get *more* equal-sized shards: **LA Metro bus** (~1,680
vehicles, 2.2M pings/day) lands ~8 shards ≈ 100 MB, while **LA Metro rail** (small fleet) is a single
~8 MB shard. Size tracks data volume (fleet size × how busy the day was), never which routes ran.

## Reading the bucket path (organization & feed IDs)

A bucket path looks like:

```
gs://calitp-tides/vehicle_locations/
  organization_source_record_id=recPnGkwdpnr8jmHB/      # WHO publishes the feed
  base64_url=aHR0cHM6Ly9hcGku…dmVoaWNsZS1wb3NpdGlvbnM/  # WHICH feed (its URL, base64-encoded)
  dt=2026-05-28/                                         # service date
  data_*.parquet
```

Both IDs come from Cal-ITP's nightly GTFS-ingest metadata, published on the California Open Data
Portal — you can look them up there:

- **`organization_source_record_id`** → the publishing agency. Resolve it in
  [`provider_gtfs_data`](https://data.ca.gov/dataset/cal-itp-gtfs-ingest-pipeline-dataset/resource/ebe116fb-b9da-4fee-a0c5-497c9d6d61d7)
  via its `organization_source_record_id` / `organization_name` columns (that table also lists each
  org's schedule / vehicle-positions / trip-updates / alerts feeds).
- **`base64_url`** → the specific feed. It's just the feed URL `base64`-encoded
  (`base64.urlsafe_b64decode`), and you can also resolve it in
  [`gtfs_datasets`](https://data.ca.gov/dataset/cal-itp-gtfs-ingest-pipeline-dataset/resource/e4ca5bd4-e9ce-40aa-a58a-3a6d78b042bd)
  via its `base64_url` → `name` / `type` / `url` columns.

The two feeds this example uses (same organization, two separate vehicle-position feeds):

| organization_source_record_id | organization_name | base64_url (decoded) | feed name | type |
|---|---|---|---|---|
| `recPnGkwdpnr8jmHB` | Los Angeles County Metropolitan Transportation Authority | `https://api.goswift.ly/real-time/lametro/gtfs-rt-vehicle-positions` | LA Metro Bus Vehicle Positions | vehicle_positions |
| `recPnGkwdpnr8jmHB` | Los Angeles County Metropolitan Transportation Authority | `https://api.goswift.ly/real-time/lametro-rail/gtfs-rt-vehicle-positions` | LA Metro Rail Vehicle Positions | vehicle_positions |

Decode any `base64_url` yourself:

```python
import base64
base64.urlsafe_b64decode("aHR0cHM6Ly9hcGku…dmVoaWNsZS1wb3NpdGlvbnM=" + "===").decode()
# -> https://api.goswift.ly/real-time/lametro/gtfs-rt-vehicle-positions
```

## The data

TIDES `vehicle_locations` (GPS pings): `latitude`, `longitude`, `event_timestamp`, `vehicle_id`,
`trip_id_performed`, `speed` (m/s), `heading`, `stop_id`, `current_status`, and more. Browse the
bucket layout at `gs://calitp-tides/vehicle_locations/.../dt=YYYY-MM-DD/`.
