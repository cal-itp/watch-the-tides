# watch-the-tides

A guide to Cal-ITP's public **TIDES** bucket, `gs://calitp-tides` — what's in it, how
it's laid out, and how to pull it — plus a small worked example that pulls one day of
vehicle positions and animates it.

- **Just want to see it?** The live animation is at
  **https://docs.calitp.org/watch-the-tides/** (no setup).
- **Want to run the example?** See **[RUNNING.md](RUNNING.md)**. You can run it on the
  committed [`sample/`](sample/) with **no Google Cloud account**
  ([Path A](RUNNING.md#path-a--run-on-the-committed-sample-no-gcp)), or pull a full day
  yourself ([Path B](RUNNING.md#path-b--pull-the-full-day-from-the-bucket)).
- **Want to understand the data?** Keep reading.

## What is TIDES, and what's in this bucket?

[**TIDES**](https://tides-transit.org) (Transit Integrated Data Exchange Specification)
is an open, community-governed standard for *historical* transit operations data —
where vehicles actually went, which trips actually ran, and so on.

`gs://calitp-tides` is Cal-ITP's public, TIDES-shaped rendering of that data for
**California transit agencies**. It is produced from Cal-ITP's nightly GTFS-Realtime
archive and refreshed by two Airflow DAGs in
[`cal-itp/data-infra`](https://github.com/cal-itp/data-infra):

| DAG | cadence | writes |
|-----|---------|--------|
| [`generate_tides`](https://github.com/cal-itp/data-infra/blob/main/airflow/dags/generate_tides.py) | Mon & Thu | the **fact** tables (`vehicle_locations/`, `trips_performed/`) |
| [`publish_tides_reference`](https://github.com/cal-itp/data-infra/blob/main/airflow/dags/publish_tides_reference.py) | Mondays | the **reference** tables (`reference/`) and **machine-readable metadata** (`datapackage.json`, `metadata/data.json`) |

It is not LA Metro–only — the facts span every eligible California agency
publishing GTFS-RT (120+ organizations as of this writing). The example in this repo
just happens to pull LA Metro. Everything is published under
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

## Bucket layout

```
gs://calitp-tides/
├── vehicle_locations/        # FACT: GPS pings  (Mon & Thu DAG)
│   └── organization_source_record_id=<org>/base64_url=<feed>/dt=<date>/data_*.parquet
├── trips_performed/          # FACT: one row per trip actually operated
│   └── organization_source_record_id=<org>/base64_url=<feed>/dt=<date>/data_*.parquet
├── reference/                # crosswalk / naming tables that resolve the IDs above
│   ├── tides_<table>_latest/ #   stable path, overwritten each run (current snapshot)
│   │   ├── data_*.parquet
│   │   ├── data_*.csv
│   │   └── datapackage.json  #   Frictionless data dictionary for this table
│   └── tides_<table>/dt=<date>/   # full history, one partition per run date
├── metadata/
│   └── data.json             # DCAT-US catalog describing every dataset above
└── *_outcomes/               # per-run export logs (JSONL), partitioned by dt / ts
```

Both fact tables are **hive-partitioned** by publishing organization, feed, and
service date, so you can pull exactly one agency-feed-day (that's what
[`download.py`](download.py) does).

### The fact tables

`vehicle_locations` (GPS pings) carries `latitude`, `longitude`, `event_timestamp`,
`vehicle_id`, `trip_id_performed`, `trip_stop_sequence`, `stop_id`, `current_status`,
`speed` (m/s), `heading`, `odometer`, plus the partition/identity columns
`organization_source_record_id`, `base64_url`, `gtfs_dataset_key`, `service_date`.
`trips_performed` summarizes the same operations one row per operated trip.

Neither fact carries agency names or route info — those are **opaque IDs** you resolve
with the reference tables.

### The reference tables (resolving the IDs)

The facts only carry IDs. The `reference/` tables turn them into something readable.
Each is published both as a full history and as a `_latest` current snapshot, with a
`datapackage.json` data dictionary:

| reference table | resolves | to |
|-----------------|----------|-----|
| `tides_organizations` | `organization_source_record_id` | org name, type, NTD ID, Caltrans district, RTPA/MPO |
| `tides_provider_gtfs_data` | an org | its schedule / vehicle-positions / trip-updates / service-alerts feeds (+ `gtfs_dataset_key`) |
| `tides_gtfs_datasets` | `gtfs_dataset_key` / `base64_url` | feed name, type, decoded URL |
| `tides_services` | `service_source_record_id` | service name, mode, operating counties |
| `tides_agency` | a schedule feed's `base64_url` | GTFS `agency.txt` (agency name, URL, timezone…) |

All are small — a copy of the `_latest` set (CSV + parquet + `datapackage.json`) is
committed under [`sample/reference/`](sample/reference/) so you can browse them without
touching GCP. These columns mirror what Cal-ITP already publishes to
[data.ca.gov](https://data.ca.gov/dataset/cal-itp-gtfs-ingest-pipeline-dataset), so the
same joins work there too.

### Machine-readable metadata

`publish_tides_reference` emits standards-based metadata (per Caltrans SAM 5160.1) in
the same run:

- a **Frictionless** [`datapackage.json`](https://specs.frictionlessdata.io/data-package/)
  next to every reference table — field names, types, and descriptions, sourced from
  the dbt model docs.
- a **DCAT-US** [`metadata/data.json`](https://resources.data.gov/resources/dcat-us/)
  catalog (Project Open Data v1.1) covering the reference tables **and** the fact
  tables — the same catalog format data.ca.gov publishes.

These are standard Frictionless packages, so `datapackage.json` doubles as a field
dictionary (open it as JSON), and the data files validate with the same tooling TIDES
uses:

```bash
pip install frictionless
frictionless validate sample/reference/tides_gtfs_datasets_latest/data_000000000000.csv
```

## Reading a bucket path

A fact path looks like:

```
gs://calitp-tides/vehicle_locations/
  organization_source_record_id=recPnGkwdpnr8jmHB/      # WHO publishes the feed
  base64_url=aHR0cHM6Ly9hcGku…dmVoaWNsZS1wb3NpdGlvbnM/  # WHICH feed (its URL, base64-encoded)
  dt=2026-05-28/                                         # service date
  data_*.parquet
```

Resolve the two IDs with the reference tables above — `organization_source_record_id`
in `tides_organizations`, `base64_url` in `tides_gtfs_datasets`. (They also resolve in
the equivalent data.ca.gov tables:
[`provider_gtfs_data`](https://data.ca.gov/dataset/cal-itp-gtfs-ingest-pipeline-dataset/resource/ebe116fb-b9da-4fee-a0c5-497c9d6d61d7),
[`gtfs_datasets`](https://data.ca.gov/dataset/cal-itp-gtfs-ingest-pipeline-dataset/resource/e4ca5bd4-e9ce-40aa-a58a-3a6d78b042bd).)

`base64_url` is just the feed URL `base64`-encoded — decode it yourself:

```python
import base64
base64.urlsafe_b64decode("aHR0cHM6Ly9hcGku…dmVoaWNsZS1wb3NpdGlvbnM=" + "===").decode()
# -> https://api.goswift.ly/real-time/lametro/gtfs-rt-vehicle-positions
```

The two feeds the example pulls (same organization, two separate vehicle-position feeds):

| organization_source_record_id | organization_name | base64_url (decoded) | feed name |
|---|---|---|---|
| `recPnGkwdpnr8jmHB` | Los Angeles County Metropolitan Transportation Authority | `https://api.goswift.ly/real-time/lametro/gtfs-rt-vehicle-positions` | LA Metro Bus Vehicle Positions |
| `recPnGkwdpnr8jmHB` | Los Angeles County Metropolitan Transportation Authority | `https://api.goswift.ly/real-time/lametro-rail/gtfs-rt-vehicle-positions` | LA Metro Rail Vehicle Positions |

## Requester-pays: how to access the bucket

`gs://calitp-tides` is a **requester-pays** bucket. Every request must be billed to a
Google Cloud project **you** own — you pay the egress (pennies for a day or two of
data). There is no anonymous download, and the browser/Console download button is
unreliable for these buckets, so use the CLI or API with a billing project. See
Google's [Use Requester Pays](https://docs.cloud.google.com/storage/docs/using-requester-pays)
(requests without a billing project fail with `400 UserProjectMissing`).

```bash
# gcloud CLI (what download.py uses) — bill the request to your own project:
gcloud storage cp "gs://calitp-tides/<path>" . --billing-project=YOUR_PROJECT
```

```python
# Python client — note user_project, and that it uses ADC, not `gcloud auth login`:
#   gcloud auth application-default login
from google.cloud import storage
client = storage.Client()
bucket = client.bucket("calitp-tides", user_project="YOUR_PROJECT")
bucket.blob("metadata/data.json").download_to_filename("data.json")
```

**No GCP account?** The [`sample/`](sample/) directory has a real (small) slice of the
bucket committed to the repo — enough to run the demo and inspect the reference data
and metadata. See [RUNNING.md Path A](RUNNING.md#path-a--run-on-the-committed-sample-no-gcp).

## Running the example

See **[RUNNING.md](RUNNING.md)** for setup, the two run paths, tunables, and how the
scripts work. In short, it downloads one day of LA Metro bus + rail `vehicle_locations`
and produces an animated map, an all-routes map, and a pings-per-hour chart.

## The TIDES ecosystem

- **The spec & its tooling** — [tides-transit.org](https://tides-transit.org) and
  [`TIDES-transit/TIDES`](https://github.com/TIDES-transit/TIDES). TIDES is built on
  [Frictionless](https://frictionlessdata.io/), so the `datapackage.json` files in this
  bucket are Frictionless data packages you can read and validate with `frictionless`
  (or the scripts in the spec's `/bin`).
- **Other implementations** — [`TIDES-transit/tides-implementations`](https://github.com/TIDES-transit/tides-implementations)
  collects TIDES implementations by agencies, vendors, and researchers. This bucket is
  Cal-ITP's California implementation.
- **The upstream pipeline** — the GTFS ingest metadata that resolves these IDs is also
  published on the [California Open Data Portal](https://data.ca.gov/dataset/cal-itp-gtfs-ingest-pipeline-dataset).

Know of a tool or group consuming `gs://calitp-tides` (an R/Python package, a research
project)? Open an issue or PR and we'll list it here.
