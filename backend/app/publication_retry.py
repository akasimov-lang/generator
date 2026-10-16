"""Bounded retries for publication requests, retaining payload and idempotency key."""
import asyncio
import logging

import httpx

PUBLICATION_MAX_ATTEMPTS = 6
PUBLICATION_RETRY_DELAY_SECONDS = 10
logger = logging.getLogger(__name__)


async def post_publication(client, endpoint, *, json, headers, on_retry=None, on_attempt=None, before_retry=None, verify_first=False):
    for attempt in range(1, PUBLICATION_MAX_ATTEMPTS + 1):
        if (attempt > 1 or verify_first) and before_retry:
            confirmed = await before_retry()
            if confirmed is not None:
                return confirmed
        if on_attempt:
            on_attempt(attempt)
        response, error = None, None
        try:
            response = await client.post(endpoint, json=json, headers=headers)
        except httpx.TransportError as exc:
            if attempt == PUBLICATION_MAX_ATTEMPTS:
                raise
            error = exc
        else:
            retryable = response.status_code in (408, 429) or 500 <= response.status_code < 600
            if not retryable or attempt == PUBLICATION_MAX_ATTEMPTS:
                return response
        if on_retry:
            on_retry(attempt, response, error)
        logger.warning("Publication attempt %s/%s failed (%s); retrying in %ss", attempt,
                       PUBLICATION_MAX_ATTEMPTS, response.status_code if response is not None else type(error).__name__,
                       PUBLICATION_RETRY_DELAY_SECONDS)
        await asyncio.sleep(PUBLICATION_RETRY_DELAY_SECONDS)


def set_publication_attempt(item, attempt, *, waiting=False, error=None):
    context = dict(item.generation_context or {})
    context["publication_retry"] = {
        "attempt": attempt, "attempts_sent": attempt - 1 if waiting else attempt, "max_attempts": PUBLICATION_MAX_ATTEMPTS,
        "waiting": waiting, "delay_seconds": PUBLICATION_RETRY_DELAY_SECONDS,
        "error": error,
    }
    item.generation_context = context
