# Running watch-the-tides

How to run this demo and reproduce its outputs. For what the data *is* and how
the `gs://calitp-tides` bucket is laid out, see the [README](README.md).

The demo pulls one service day of `vehicle_locations` for **LA Metro Bus** and
**LA Metro Rail** and produces:

- `outputs/vehicle_animation.html` — vehicles moving along their routes over time,
  colored to match GTFS (rail by line, bus by service type).
- `outputs/all_bus_routes_map.html` — a static map of **every** bus route that ran
  that day, one representative track each (see [Why the animation shows only some
  routes](#why-the-animation-shows-only-some-routes)).
- `outputs/pings_per_hour.png` — a service-profile chart of pings per hour.

There are two ways to run it:

- **[Path A — no GCP account](#path-a--run-on-the-committed-sample-no-gcp)** uses the
  small data slice committed under `sample/`. Best for a first look.
- **[Path B — your own GCP project](#path-b--pull-the-full-day-from-the-bucket)**
  pulls a full service day from the requester-pays bucket. Needed for the full
  network, the all-routes map, and any other date.

Both need [`uv`](https://docs.astral.sh/uv/). Both fetch LA Metro's GTFS over plain
HTTPS from GitLab to color vehicles (no account needed). Only Path B needs `gcloud`
and a billing-enabled Google Cloud project.

```bash
uv sync
```

## Path A — run on the committed sample (no GCP)

`sample/` holds a thinned slice of the 2026-05-28 service day (all rail + the busiest
bus vehicles over the 06:00–10:00 AM peak — see [`sample/README.md`](sample/README.md)).
Point the scripts at it with `TIDES_DATA_DIR`:

```bash
TIDES_DATA_DIR=sample uv run python animate.py   # -> outputs/vehicle_animation.html
TIDES_DATA_DIR=sample uv run python charts.py    # -> outputs/pings_per_hour.png
```

Then open `outputs/vehicle_animation.html` and hit play.

The sample reproduces the default AM-peak animation (25 busiest vehicles per mode).
It does **not** cover the whole day or every route, so `all_routes_map.py` and the
full pings-per-hour profile need Path B.

## Path B — pull the full day from the bucket

`gs://calitp-tides` is **requester-pays**: every request is billed to a Google Cloud
project *you* own (you pay egress — pennies for this sample). See
[the README](README.md#requester-pays-how-to-access-the-bucket) for the why and the
raw access commands.

```bash
gcloud auth login                         # a Google account with a billing-enabled GCP project
export TIDES_BILLING_PROJECT=your-project-id

uv run python download.py        # -> data/la_metro_{bus,rail}_<date>.parquet
uv run python animate.py         # -> outputs/vehicle_animation.html
uv run python all_routes_map.py  # -> outputs/all_bus_routes_map.html  (all bus routes that ran)
uv run python charts.py          # -> outputs/pings_per_hour.png
```

## Tuning (env vars)

| var | default | what |
|-----|---------|------|
| `TIDES_BILLING_PROJECT` | — | GCP project billed for requester-pays downloads (Path B) |
| `TIDES_DATA_DIR` | `data` | where parquet is read/written; set to `sample` for Path A |
| `TIDES_DT` | `2026-05-28` | service date to pull / read |
| `ANIM_START` / `ANIM_END` | `07:00` / `09:00` | animation window (local HH:MM) |
| `ANIM_INTERVAL_SEC` | `30` | resample interval per vehicle |
| `ANIM_MAX_VEHICLES` | `25` | busiest N vehicles per mode to animate |

## How it works

| file | what |
|------|------|
| `config.py` | billing project, data dir, service date, the two LA Metro feeds, colors |
| `download.py` | pulls one day of each feed from the requester-pays bucket via `gcloud storage` |
| `make_sample.py` | thins a downloaded day into the committed `sample/` slice |
| `gtfs_colors.py` | maps vehicles to GTFS colors by joining `trip_id` to LA Metro GTFS |
| `animate.py` | time-animated folium map of moving vehicles |
| `all_routes_map.py` | static map of every bus route that operated, one representative track each |
| `charts.py` | pings-per-hour chart |

### A note on GTFS colors

TIDES `vehicle_locations` carries `trip_id_performed` but no route, so to color
vehicles we join to LA Metro's GTFS (`trip_id → route_id → route_color`). LA Metro
regenerates its GTFS frequently and **reassigns trip IDs**, so `gtfs_colors.py`
fetches the GTFS commit **effective on the service date** from GitLab — otherwise the
IDs don't line up. Rail uses the GTFS line color; buses are colored by service type
(Local / Rapid / Express / Limited / BRT).

## Why the animation shows only some routes

The animation isn't the whole picture. `animate.py` deliberately limits how much it
renders (so the file stays light and playable), so it surfaces only a fraction of the
bus network. That's a *rendering* cap, not a data gap — a full `download.py` pull
already contains every shard, covering nearly all routes that operated.

To see the full network, run `all_routes_map.py` (Path B), which draws one
representative track per route.

### A note on the parquet shards

Each `dt=<date>/` partition holds several `data_*.parquet` shards. Their sizes vary,
but **not** by route — BigQuery's export splits a partition into roughly
**equal-sized** files (e.g. eight ~13 MB shards for one bus day), and each shard is an
arbitrary slice of rows that already contains *all* routes. So bigger feeds/busier
days just get *more* equal-sized shards: **LA Metro bus** (~1,680 vehicles, 2.2M
pings/day) lands ~8 shards ≈ 100 MB, while **LA Metro rail** (small fleet) is a single
~8 MB shard. Size tracks data volume (fleet size × how busy the day was), never which
routes ran.
