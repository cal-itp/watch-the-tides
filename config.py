"""Configuration for the watch-the-tides example.

The TIDES data lives in the *requester-pays* bucket gs://calitp-tides, so every
request must name a billing project you own (you pay egress -- pennies for this
sample). See README.md for the why.
"""

import os

# gs://calitp-tides is requester-pays, so every download must be billed to a Google
# Cloud project YOU own (you pay egress -- pennies for this sample). Set your own:
#   export TIDES_BILLING_PROJECT=your-gcp-project-id
BILLING_PROJECT = os.environ.get("TIDES_BILLING_PROJECT")

BUCKET = "calitp-tides"
DATASET = "vehicle_locations"

# Single service date to pull (override with TIDES_DT).
SERVICE_DATE = os.environ.get("TIDES_DT", "2026-05-28")

# LA Metro feeds (same organization, two separate GTFS-RT vehicle-position feeds).
# org + base64_url identify a feed's path prefix in the bucket.
LA_METRO_ORG = "recPnGkwdpnr8jmHB"

FEEDS = {
    # label: (organization_source_record_id, base64_url)
    "la_metro_bus": (
        LA_METRO_ORG,
        # https://api.goswift.ly/real-time/lametro/gtfs-rt-vehicle-positions
        "aHR0cHM6Ly9hcGkuZ29zd2lmdC5seS9yZWFsLXRpbWUvbGFtZXRyby9ndGZzLXJ0LXZlaGljbGUtcG9zaXRpb25z",
    ),
    "la_metro_rail": (
        LA_METRO_ORG,
        # https://api.goswift.ly/real-time/lametro-rail/gtfs-rt-vehicle-positions
        "aHR0cHM6Ly9hcGkuZ29zd2lmdC5seS9yZWFsLXRpbWUvbGFtZXRyby1yYWlsL2d0ZnMtcnQtdmVoaWNsZS1wb3NpdGlvbnM=",
    ),
}

DATA_DIR = "data"
OUTPUT_DIR = "outputs"
GTFS_DIR = "gtfs"

# LA Metro GTFS lives on GitLab; we pull the commit effective on SERVICE_DATE so
# trip_ids line up (rail is regenerated daily, bus changes each June/Dec).
GTFS_REPOS = {"Rail": "LACMTA/gtfs_rail", "Bus": "LACMTA/gtfs_bus"}

# Bus has no useful GTFS route_color (almost all black), so buses are colored by
# service type, classified from route_long_name. Order matters (first match wins).
BUS_TYPE_COLORS = [
    ("Rapid", "#C8102E"),    # Metro Rapid (7xx) — red
    ("Express", "#0061A0"),  # Metro Express — blue
    ("Limited", "#F5A623"),  # Metro Limited — amber
    ("G Line", "#5A7D7C"),   # G Line BRT — silver-green
    ("J Line", "#919D9D"),   # J Line BRT — silver
    ("Local", "#E47200"),    # Metro Local — orange (catch-all for the rest)
]
FALLBACK_COLOR = "#9E9E9E"  # vehicle with no matched GTFS route
