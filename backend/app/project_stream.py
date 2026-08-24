import json
import logging
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings
from app.db import SessionLocal
from app.project_cache import ProjectCacheError, sync_project_data_update


logger = logging.getLogger("project-stream")


@dataclass(frozen=True)
class ServerSentEvent:
    event_id: str
    event: str
    data: str


@dataclass
class StreamCursor:
    last_event_id: str = ""


def iter_sse_events(lines: Iterable[str]) -> Iterator[ServerSentEvent]:
    event_id = ""
    event_name = "message"
    data_lines: list[str] = []

    def build_event() -> ServerSentEvent | None:
        if not data_lines:
            return None
        return ServerSentEvent(event_id=event_id, event=event_name, data="\n".join(data_lines))

    for raw_line in lines:
        line = raw_line.rstrip("\r")
        if not line:
            event = build_event()
            if event:
                yield event
            event_name = "message"
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if field == "id" and "\x00" not in value:
            event_id = value
        elif field == "event":
            event_name = value or "message"
        elif field == "data":
            data_lines.append(value)

    event = build_event()
    if event:
        yield event


def _login(client: httpx.Client) -> str:
    settings = get_settings()
    if not settings.project_cache_username or not settings.project_cache_password:
        raise ProjectCacheError("Project cache credentials are not configured")
    response = client.post(
        f"{settings.project_cache_url.rstrip('/')}/auth/login",
        json={"username": settings.project_cache_username, "pass": settings.project_cache_password},
    )
    response.raise_for_status()
    token = str(response.json().get("token") or "").strip()
    if not token:
        raise ProjectCacheError("Project stream login did not return a token")
    return token


def _fetch_project_data(client: httpx.Client, token: str, project_name: str) -> dict[str, Any]:
    settings = get_settings()
    response = client.post(
        f"{settings.project_cache_url.rstrip('/')}/projects/cache",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "fields": {"settings": False, "head": False, "data": True},
            "names": [project_name],
        },
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ProjectCacheError("Project stream cache refresh returned an unexpected response")
    project = next(
        (
            item
            for item in payload
            if isinstance(item, dict) and str(item.get("name") or "").strip() == project_name
        ),
        None,
    )
    if not project:
        raise ProjectCacheError(f"Stream project '{project_name}' was not found in cache")
    return project


def _handle_event(client: httpx.Client, token: str, event: ServerSentEvent) -> None:
    try:
        payload = json.loads(event.data)
    except (TypeError, json.JSONDecodeError):
        logger.warning("Ignoring malformed SSE event id=%s", event.event_id or "-")
        return
    if not isinstance(payload, dict):
        return
    project_name = str(payload.get("projectName") or payload.get("project_name") or "").strip()
    if not project_name:
        logger.warning("Ignoring SSE event without projectName id=%s", event.event_id or "-")
        return
    project = _fetch_project_data(client, token, project_name)
    with SessionLocal() as db:
        updated_count = sync_project_data_update(
            db,
            project_name,
            project,
            server_host=str(payload.get("server") or "").strip() or None,
        )
    logger.info(
        "Applied project event id=%s project=%s modified_at=%s sites=%d",
        event.event_id or "-",
        project_name,
        payload.get("modifiedAt") or payload.get("modified_at") or "-",
        updated_count,
    )


def consume_stream(cursor: StreamCursor) -> None:
    settings = get_settings()
    with httpx.Client(timeout=httpx.Timeout(30.0, read=None), follow_redirects=True) as client:
        token = _login(client)
        headers = {"Accept": "text/event-stream", "Cache-Control": "no-cache"}
        if cursor.last_event_id:
            headers["Last-Event-ID"] = cursor.last_event_id
        with client.stream(
            "GET",
            f"{settings.project_cache_url.rstrip('/')}/projects/stream",
            params={"token": token},
            headers=headers,
        ) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "text/event-stream" not in content_type:
                raise ProjectCacheError(f"Project stream returned unexpected content type: {content_type or 'missing'}")
            logger.info("Connected to project stream")
            for event in iter_sse_events(response.iter_lines()):
                _handle_event(client, token, event)
                if event.event_id:
                    cursor.last_event_id = event.event_id


def run_forever() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    cursor = StreamCursor()
    retry_delay = 1
    while True:
        try:
            consume_stream(cursor)
            retry_delay = 1
        except KeyboardInterrupt:
            raise
        except Exception:
            logger.exception("Project stream disconnected; reconnecting in %ss", retry_delay)
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)


if __name__ == "__main__":
    run_forever()
