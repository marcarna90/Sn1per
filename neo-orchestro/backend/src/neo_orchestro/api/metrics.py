"""Prometheus metrics with bounded label cardinality (route templates, never raw paths)."""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

UNMATCHED = "unmatched"


class Metrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()  # per app: no duplicate registration across tests
        self._requests = Counter(
            "neo_http_requests_total",
            "HTTP requests handled",
            ["method", "route", "status"],
            registry=self.registry,
        )
        self._latency = Histogram(
            "neo_http_request_duration_seconds",
            "HTTP request latency",
            ["method", "route"],
            registry=self.registry,
        )

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        self._requests.labels(method=method, route=route, status=str(status)).inc()
        self._latency.labels(method=method, route=route).observe(seconds)

    def render(self) -> tuple[bytes, str]:
        return generate_latest(self.registry), CONTENT_TYPE_LATEST
