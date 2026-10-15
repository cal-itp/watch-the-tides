# sample/ — a small, committed slice of the TIDES bucket

So you can try watch-the-tides (and see what the published TIDES data looks like)
**without a Google Cloud account**. Everything here is real data pulled from
`gs://calitp-tides`, just small enough to check into git.

```
sample/
  la_metro_bus_2026-05-28.parquet    # thinned vehicle_locations (demo input, Path A)
  la_metro_rail_2026-05-28.parquet   # thinned vehicle_locations (demo input, Path A)
  reference/                         # the published TIDES reference tables (*_latest)
    tides_organizations_latest/      #   each: data_*.csv + data_*.parquet + datapackage.json
    tides_gtfs_datasets_latest/
    tides_provider_gtfs_data_latest/
    tides_services_latest/
    tides_agency_latest/
  metadata/
    data.json                        # the bucket's DCAT-US catalog
```

## The vehicle_locations parquet (demo input)

`make_sample.py` thins a full downloaded service day (2026-05-28) down to a slice that
still drives the default animation:

- the **06:00–10:00** AM-peak window only (around `animate.py`'s 07:00–09:00 default),
- **all** rail vehicles; the **60 busiest** bus vehicles (what the animation surfaces
  anyway),
- one ping per vehicle per **20 s**.

That turns ~2.4M pings / ~110 MB into ~75k rows / ~4 MB. It reproduces the headline
animation but is **not** the whole day or every route — the all-routes map and the
full pings-per-hour profile need a real download (RUNNING.md, Path B).

Run the demo against it:

```bash
TIDES_DATA_DIR=sample uv run python animate.py
```

Regenerate (needs the full files in `data/` from `download.py`):

```bash
uv run python download.py
uv run python make_sample.py
```

## The reference tables + metadata (copied verbatim from the bucket)

`reference/` and `metadata/data.json` are copied straight from `gs://calitp-tides`,
unmodified, so you can inspect the real published reference data and its
machine-readable metadata offline. These resolve the opaque IDs on the fact tables
(`organization_source_record_id`, `base64_url`, `gtfs_dataset_key`) — see the
[README](../README.md#the-reference-tables-resolving-the-ids) for how they fit
together.

They were pulled with:

```bash
gcloud storage cp -r "gs://calitp-tides/reference/*_latest"  sample/reference/ \
  --billing-project=YOUR_PROJECT
gcloud storage cp    "gs://calitp-tides/metadata/data.json"  sample/metadata/ \
  --billing-project=YOUR_PROJECT
```

Each reference table ships with a Frictionless `datapackage.json` (a field dictionary),
and the data files validate with the standard TIDES tooling:

```bash
pip install frictionless
frictionless validate sample/reference/tides_gtfs_datasets_latest/data_000000000000.csv
```
