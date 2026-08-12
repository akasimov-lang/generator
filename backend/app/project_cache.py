from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings


class ProjectCacheError(RuntimeError):
    pass


def _normalize_domain(value: str | None) -> str:
    domain = (value or "").strip().lower()
    for prefix in ("https://", "http://"):
        if domain.startswith(prefix):
            domain = domain[len(prefix) :]
    return domain.rstrip("/")


def _working_project_canons() -> set[str]:
    path = Path(__file__).with_name("working_project_canons.txt")
    return {_normalize_domain(line) for line in path.read_text().splitlines() if line.strip()}


def fetch_project_cache(names: list[str] | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.project_cache_username or not settings.project_cache_password:
        raise ProjectCacheError("Project cache credentials are not configured")

    try:
        with httpx.Client(base_url=settings.project_cache_url.rstrip("/"), timeout=45.0) as client:
            login_response = client.post(
                "/auth/login",
                json={"username": settings.project_cache_username, "pass": settings.project_cache_password},
            )
            login_response.raise_for_status()
            token = login_response.json().get("token")
            if not token:
                raise ProjectCacheError("Project cache login did not return a token")
            request_payload: dict[str, Any] = {"fields": {"settings": True, "head": True, "data": True}}
            if names:
                request_payload["names"] = names
            cache_response = client.post(
                "/projects/cache",
                headers={"Authorization": f"Bearer {token}"},
                json=request_payload,
            )
            cache_response.raise_for_status()
            payload = cache_response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise ProjectCacheError(f"Project cache request failed: {error}") from error

    if not isinstance(payload, list):
        raise ProjectCacheError("Project cache returned an unexpected response")
    return [project for project in payload if isinstance(project, dict)]


def _project_menu(project: dict[str, Any]) -> dict[str, list[Any]]:
    data = project.get("data") if isinstance(project.get("data"), dict) else {}
    menu = data.get("menu") if isinstance(data.get("menu"), dict) else {}
    header = menu.get("header") if isinstance(menu.get("header"), list) else []
    footer = menu.get("footer") if isinstance(menu.get("footer"), list) else []
    return {"header": header, "footer": footer}


def _homepage_title(project: dict[str, Any]) -> str | None:
    data = project.get("data") if isinstance(project.get("data"), dict) else {}
    pages = data.get("pages") if isinstance(data.get("pages"), list) else []
    homepage = next(
        (
            page
            for page in pages
            if isinstance(page, dict) and str(page.get("slug") or "").strip() in {"", "/"}
        ),
        None,
    )
    title = str(homepage.get("title") or "").strip() if homepage else ""
    return title or None


def _internal_pages_count(project: dict[str, Any]) -> int:
    data = project.get("data") if isinstance(project.get("data"), dict) else {}
    pages = data.get("pages") if isinstance(data.get("pages"), list) else []
    return sum(
        1
        for page in pages
        if isinstance(page, dict) and str(page.get("slug") or "").strip() not in {"", "/"}
    )


def _domains_count(project: dict[str, Any]) -> int:
    settings = project.get("settings") if isinstance(project.get("settings"), dict) else {}
    domains = settings.get("domains") if isinstance(settings.get("domains"), list) else []
    return len(domains)


def sync_project_cache(db: Session, projects: list[dict[str, Any]]) -> dict[str, Any]:
    working_canons = _working_project_canons()
    existing_sites = db.scalars(select(models.Site).where(models.Site.external_project_id.is_not(None))).all()
    sites_by_external_id = {site.external_project_id: site for site in existing_sites if site.external_project_id}
    now = datetime.now(timezone.utc)
    created_count = 0
    updated_count = 0
    matched_external_ids: set[str] = set()
    processed_external_ids: set[str] = set()
    name_occurrences: dict[str, int] = {}
    name_counts = Counter(str(project.get("name") or "").strip() for project in projects)
    cache_projects: list[dict[str, Any]] = []

    for project in projects:
        name = str(project.get("name") or "").strip()
        settings = project.get("settings") if isinstance(project.get("settings"), dict) else {}
        canon = _normalize_domain(settings.get("canon"))
        if not name:
            continue
        raw_external_id = project.get("id") or project.get("_id")
        if raw_external_id:
            external_project_id = str(raw_external_id)
        else:
            name_occurrences[name] = name_occurrences.get(name, 0) + 1
            occurrence = name_occurrences[name]
            external_project_id = name if occurrence == 1 else f"{name}#{occurrence}"
        menu = _project_menu(project)
        homepage_title = _homepage_title(project)
        internal_pages_count = _internal_pages_count(project)
        domains_count = _domains_count(project)
        is_duplicate = name_counts[name] > 1
        has_menu = bool(menu["header"] or menu["footer"])
        is_working_project = canon in working_canons
        cache_projects.append(
            {
                "external_project_id": external_project_id,
                "name": name,
                "canon": canon or None,
                "homepage_title": homepage_title,
                "internal_pages_count": internal_pages_count,
                "domains_count": domains_count,
                "has_menu": has_menu,
                "is_working_project": is_working_project,
            }
        )
        if external_project_id in processed_external_ids:
            continue

        processed_external_ids.add(external_project_id)
        if is_working_project:
            matched_external_ids.add(external_project_id)
        site = sites_by_external_id.get(external_project_id)
        if site is None:
            site = models.Site(
                name=name,
                base_url=f"https://{canon}",
                publication_endpoint=f"https://{canon}/api/content",
                payload_mode="full_site",
                external_project_id=external_project_id,
                is_test_project=False,
                project_status="duplicate" if is_duplicate else "working" if is_working_project else "not_in_focus",
            )
            db.add(site)
            sites_by_external_id[external_project_id] = site
            created_count += 1
        else:
            updated_count += 1

        site.name = name
        site.base_url = f"https://{canon}"
        site.cache_canon = canon
        site.homepage_title = homepage_title
        site.internal_pages_count = internal_pages_count
        site.domains_count = domains_count
        if is_duplicate:
            site.project_status = "duplicate"
        site.default_menu = menu
        site.has_menu = has_menu
        site.cache_synced_at = now
        site.is_active = True

    db.commit()
    cache_projects.sort(key=lambda project: (not project["is_working_project"], not project["has_menu"], project["name"].lower()))
    return {
        "cache_count": len(projects),
        "matched_count": len(matched_external_ids),
        "created_count": created_count,
        "updated_count": updated_count,
        "projects": cache_projects,
    }
