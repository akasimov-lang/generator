"""Bounded retries for network reads; mutations must never use this helper."""
import logging
import time

import httpx

ATTEMPTS = 5
TIMEOUT = 10.0
INTERVAL = 10.0
logger = logging.getLogger(__name__)


def retryable(error):
    request = getattr(error, 'request', None)
    if request is None or request.method != 'GET':
        return False
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in (408, 429) or error.response.status_code >= 500
    return isinstance(error, httpx.RequestError)


def project_get(client, url):
    for attempt in range(1, ATTEMPTS + 1):
        try:
            response = client.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if status not in (408, 429) and status < 500:
                raise
            if attempt == ATTEMPTS:
                raise
        except httpx.RequestError:
            if attempt == ATTEMPTS:
                raise
        logger.warning("Webdev network read unavailable; attempt %s/%s, retry in %ss", attempt, ATTEMPTS, INTERVAL)
        time.sleep(INTERVAL)
