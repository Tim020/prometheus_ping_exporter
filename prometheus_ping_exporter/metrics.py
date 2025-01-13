from prometheus_client import Counter, Gauge, Histogram
from prometheus_client.utils import INF

SCRAPE_DURATION_SECONDS = Histogram(
    "scrape_duration_seconds",
    "Scrape Duration (seconds) for a particular host",
    ["process", "host"],
    buckets=(0.5, 1, 2.5, 5, 7.5, 10, 12, 14, 16, 18, 20, INF),
)
SCRAPE_COUNT = Counter(
    "scrape_count", "Number of Scrapes", ["process", "host", "is_error"]
)
HOST_AVAILABILITY = Gauge("host_availability", "Host availability", ["host"])
TRANSMITTED_PACKETS = Counter(
    "transmitted_packets", "Number of transmitted packets", ["host"]
)
RECEIVED_PACKETS = Counter("received_packets", "Number of received packets", ["host"])
PROCESS_DURATION_SECONDS = Histogram(
    "process_duration_seconds",
    "Overall duration of the scraper process across all hosts",
    ["process"],
    buckets=(0.5, 1, 2.5, 5, 7.5, 10, 12, 14, 16, 18, 20, INF),
)
