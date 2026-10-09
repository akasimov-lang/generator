from typing import Any


def webdev_origin_headers(settings: Any) -> dict[str, str]:
    """Headers required by Webdev when issuing a new authentication token."""
    origin = str(getattr(settings, "app_public_url", "") or "").strip().rstrip("/")
    return {"Origin": origin} if origin else {}
