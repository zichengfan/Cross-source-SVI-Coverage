"""Polite-scraper utilities — shared by every provider fetch path.

Codifies the project's "polite default" posture once: a descriptive User-Agent,
a per-host request throttle, retry with exponential backoff on transient
failures, and a robots.txt check. New providers and the extent-discovery runner
should fetch through `polite_fetch` rather than calling urllib directly.
"""

from __future__ import annotations

import time
import urllib.robotparser
from dataclasses import dataclass
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DEFAULT_USER_AGENT = (
    "global-svi-coverage-observatory/0.3 "
    "(+https://github.com/zichengfan/Cross-source-SVI-Coverage)"
)

# HTTP statuses worth retrying — transient server/throttle errors.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class PolitePolicy:
    """Tunable scrape posture. Providers may pass a stricter policy."""

    min_interval_seconds: float = 0.25
    max_retries: int = 3
    backoff_base_seconds: float = 1.0
    timeout_seconds: int = 60
    respect_robots: bool = True
    user_agent: str = DEFAULT_USER_AGENT


class _HostThrottle:
    """Enforces a minimum gap between requests to the same host."""

    def __init__(self) -> None:
        self._last_request: dict[str, float] = {}
        self._lock = Lock()

    def wait(self, host: str, min_interval_seconds: float) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request.get(host, 0.0)
            if elapsed < min_interval_seconds:
                time.sleep(min_interval_seconds - elapsed)
            self._last_request[host] = time.monotonic()


_THROTTLE = _HostThrottle()
_ROBOTS_CACHE: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def robots_allows(url: str, user_agent: str = DEFAULT_USER_AGENT) -> bool:
    """Whether robots.txt permits fetching `url`. Unreachable robots.txt → allowed."""
    parts = urlsplit(url)
    root = f"{parts.scheme}://{parts.netloc}"
    if root not in _ROBOTS_CACHE:
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(f"{root}/robots.txt")
        try:
            parser.read()
        except Exception:
            parser = None
        _ROBOTS_CACHE[root] = parser
    parser = _ROBOTS_CACHE[root]
    if parser is None:
        return True
    return parser.can_fetch(user_agent, url)


def polite_fetch(
    url: str,
    headers: dict[str, str] | None = None,
    policy: PolitePolicy | None = None,
) -> tuple[bytes, str, int]:
    """Fetch `url` politely: throttle per host, retry transient failures.

    Returns (payload, content_type, http_status). Raises HTTPError/URLError when
    a non-retryable error occurs or retries are exhausted — callers keep their
    existing 404 / error handling.
    """
    policy = policy or PolitePolicy()
    request_headers = dict(headers or {})
    request_headers.setdefault("User-Agent", policy.user_agent)
    host = urlsplit(url).netloc

    last_error: Exception | None = None
    for attempt in range(policy.max_retries + 1):
        _THROTTLE.wait(host, policy.min_interval_seconds)
        try:
            request = Request(url, headers=request_headers)
            with urlopen(request, timeout=policy.timeout_seconds) as response:
                return (
                    response.read(),
                    response.headers.get("Content-Type", ""),
                    response.status,
                )
        except HTTPError as exc:
            if exc.code in RETRYABLE_STATUS and attempt < policy.max_retries:
                last_error = exc
                time.sleep(policy.backoff_base_seconds * (2**attempt))
                continue
            raise
        except URLError as exc:
            if attempt < policy.max_retries:
                last_error = exc
                time.sleep(policy.backoff_base_seconds * (2**attempt))
                continue
            raise

    # Loop only exits via return/raise; this guards an impossible fallthrough.
    raise last_error if last_error is not None else RuntimeError(f"polite_fetch failed: {url}")
