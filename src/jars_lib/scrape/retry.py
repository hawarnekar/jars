"""A small retry helper with exponential backoff for transient network failures.

The scrapers make many sequential requests; a single dropped connection, timeout, or 5xx
shouldn't abort a long crawl. ``with_retry`` re-invokes a callable a few times with growing
delays, but only for *transient* errors — a 404 or a parse error fails fast, unchanged.

Hand-rolled (no ``tenacity`` dependency) to keep the install footprint small.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

import httpx

log = logging.getLogger("jars_lib.scrape.retry")

T = TypeVar("T")

# Server-side / transient HTTP status codes worth retrying.
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


def is_transient_http(exc: BaseException) -> bool:
    """Whether an exception is a retryable transient network failure."""
    if isinstance(exc, httpx.TransportError):  # connect/read/write timeouts, conn resets
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRY_STATUS
    return False


def with_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    backoff: float = 2.0,
    is_transient: Callable[[BaseException], bool] = is_transient_http,
    description: str = "request",
) -> T:
    """Call ``fn`` with exponential backoff, retrying only on transient failures.

    Parameters
    ----------
    attempts:
        Total number of tries (so ``3`` means the initial call plus 2 retries).
    base_delay, backoff:
        The nth retry sleeps ``base_delay * backoff ** (n - 1)`` seconds.
    is_transient:
        Predicate deciding whether a raised exception is worth retrying. Non-transient
        errors propagate immediately. Defaults to :func:`is_transient_http`.
    description:
        Human label used in the retry log line.

    The last attempt's exception is re-raised unchanged, so callers can translate it.
    """
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except BaseException as exc:
            if attempt >= attempts or not is_transient(exc):
                raise
            delay = base_delay * (backoff ** (attempt - 1))
            log.warning(
                "%s failed (%s); retrying in %.1fs (attempt %d/%d)",
                description, exc, delay, attempt + 1, attempts,
            )
            time.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
