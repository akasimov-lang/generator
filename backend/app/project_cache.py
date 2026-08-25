from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings


class ProjectCacheError(RuntimeError):
    pass


def project_server_url(site: models.Site, path: str) -> str:
    server_id = (site.cache_server_ip or "").strip()
    if not server_id or not re.fullmatch(r"[A-Za-z0-9-]+", server_id):
        raise ProjectCacheError("Project serverId is missing or invalid")
    domain = get_settings().alfan_url.strip().strip("/")
    if not domain or not re.fullmatch(r"[A-Za-z0-9.-]+", domain):
        raise ProjectCacheError("Project server domain is invalid")
    return f"https://{server_id}.{domain}/{path.lstrip('/')}"


async def refresh_project_server_token(client: httpx.AsyncClient) -> str:
    settings = get_settings()
    if not settings.project_cache_username or not settings.project_cache_password:
        raise ProjectCacheError("Project cache credentials are not configured")
    response = await client.post(
        f"{settings.project_cache_url.rstrip('/')}/auth/login",
        json={"username": settings.project_cache_username, "pass": settings.project_cache_password},
    )
    response.raise_for_status()
    token = str(response.json().get("token") or "").strip()
    if not token:
        raise ProjectCacheError("Project cache login did not return a token")
    return token


def fetch_project_menu_capabilities(site: models.Site, force: bool = False) -> dict[str, Any]:
    if site.menu_capabilities_checked_at is not None and not force:
        return _site_menu_capabilities(site)
    if not site.cache_server_ip or not site.name:
        raise ProjectCacheError("Project server is not available in cache")
    if not re.fullmatch(r"[A-Za-z0-9-]+", site.cache_server_ip):
        raise ProjectCacheError("Project server name is invalid")

    settings = get_settings()
    try:
        with httpx.Client(timeout=30.0) as client:
            def get_token() -> str:
                login_response = client.post(
                    f"{settings.project_cache_url.rstrip('/')}/auth/login",
                    json={"username": settings.project_cache_username, "pass": settings.project_cache_password},
                )
                login_response.raise_for_status()
                token = str(login_response.json().get("token") or "").strip()
                if not token:
                    raise ProjectCacheError("Project cache login did not return a token")
                return token

            project_url = f"{project_server_url(site, '/projects/one')}/{quote(site.name, safe='')}"
            token = get_token()
            response = client.get(project_url, headers={"Authorization": f"Bearer {token}"})
            if response.status_code in {401, 403}:
                token = get_token()
                response = client.get(project_url, headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
            project = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise ProjectCacheError(f"Project menu capability request failed: {error}") from error

    shortcodes = project.get("shortcodes") if isinstance(project, dict) else []
    return analyze_menu_templates(shortcodes)


def analyze_menu_templates(shortcodes: Any) -> dict[str, bool]:
    templates = {
        str(item.get("name") or "").strip(): str(item.get("data") or "")
        for item in shortcodes if isinstance(item, dict)
    } if isinstance(shortcodes, list) else {}
    header_template = templates.get("header.hbs", "")
    footer_template = templates.get("footer.hbs", "")
    def renders_menu(template: str, menu_name: str) -> bool:
        escaped_name = re.escape(menu_name)
        handlebars_loop = bool(
            re.search(rf"{{{{#each\s+(?:this\.)?{escaped_name}\b[^}}]*}}}}", template, re.IGNORECASE)
        )
        scripted_menu = bool(
            re.search(
                rf"(?:\b{escaped_name}\s*(?:\.|\?\.)\s*(?:forEach|map)\s*\(|"
                rf"\bfor\s*\([^)]*\b(?:of|in)\s+{escaped_name}\b|"
                rf"\bArray\.from\s*\(\s*{escaped_name}\s*\)\s*\.\s*(?:forEach|map)\s*\()",
                template,
                re.IGNORECASE,
            )
        )
        anchor_count = len(re.findall(r"<a\b[^>]*\bhref\s*=", template, re.IGNORECASE))
        navigation_container = bool(
            re.search(r"<nav\b", template, re.IGNORECASE)
            or re.search(
                r"<(?:div|ul|ol)\b[^>]*\b(?:class|id)\s*=\s*['\"][^'\"]*"
                r"(?:menu|nav|navigation)[^'\"]*['\"]",
                template,
                re.IGNORECASE,
            )
        )
        static_menu = navigation_container and anchor_count >= 2
        return handlebars_loop or scripted_menu or static_menu

    def renders_nested_menu(template: str) -> bool:
        return bool(
            re.search(r"{{#if\s+this\.children\b", template, re.IGNORECASE)
            or re.search(r"children|sub[-_ ]?menu|dropdown|recursive|nested", template, re.IGNORECASE)
        )

    header_rendered = renders_menu(header_template, "headerMenu")
    footer_rendered = renders_menu(footer_template, "footerMenu")
    return {
        "header_menu_rendered": header_rendered,
        "header_menu_nested": header_rendered and renders_nested_menu(header_template),
        "footer_menu_rendered": footer_rendered,
        "footer_menu_nested": footer_rendered and renders_nested_menu(footer_template),
    }


def _site_menu_capabilities(site: models.Site) -> dict[str, Any]:
    return {
        "checked_at": site.menu_capabilities_checked_at,
        "header_menu_rendered": site.header_menu_rendered,
        "header_menu_nested": site.header_menu_nested,
        "footer_menu_rendered": site.footer_menu_rendered,
        "footer_menu_nested": site.footer_menu_nested,
    }


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
            request_payload: dict[str, Any] = {
                "fields": {"settings": True, "head": True, "data": True, "serverId": True}
            }
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


def refresh_project_server_id(db: Session, site: models.Site) -> str:
    """Resolve and persist the project's current server before a direct request."""
    if not site.name:
        raise ProjectCacheError("Project name is not configured")
    projects = fetch_project_cache([site.name])
    project = next((item for item in projects if str(item.get("name") or "").strip() == site.name), None)
    if not project:
        raise ProjectCacheError(f"Project '{site.name}' was not found in cache")
    server_id = str(
        project.get("serverId")
        or project.get("server_id")
        or project.get("serverIp")
        or project.get("server_ip")
        or ""
    ).strip()
    if not server_id:
        raise ProjectCacheError(f"Project '{site.name}' does not have a serverId in cache")
    if server_id != site.cache_server_ip:
        site.cache_server_ip = server_id
        db.commit()
    return server_id


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


def _project_domains(project: dict[str, Any]) -> list[str]:
    settings = project.get("settings") if isinstance(project.get("settings"), dict) else {}
    domains = settings.get("domains") if isinstance(settings.get("domains"), list) else []
    normalized_domains: list[str] = []
    for item in domains:
        value = item
        if isinstance(item, dict):
            value = item.get("domain") or item.get("url") or item.get("name")
        domain = _normalize_domain(str(value or ""))
        if domain and domain not in normalized_domains:
            normalized_domains.append(domain)
    return normalized_domains


def _deduplicate_cache_projects(projects: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    unique_projects: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for project in projects:
        name = str(project.get("name") or "").strip().casefold()
        if name and name in seen_names:
            continue
        if name:
            seen_names.add(name)
        unique_projects.append(project)
    return unique_projects, len(projects) - len(unique_projects)


def _site_has_related_data(db: Session, site: models.Site) -> bool:
    return any(
        db.scalar(select(func.count()).select_from(model).where(model.site_id == site.id))
        for model in (
            models.Section,
            models.PromptTemplate,
            models.GenerationTask,
            models.ContentItem,
            models.PublicationCampaign,
        )
    )


def _remove_safe_site_duplicates(db: Session) -> int:
    sites = db.scalars(select(models.Site)).all()
    groups: dict[str, list[models.Site]] = {}
    for site in sites:
        key = site.name.strip().casefold()
        groups.setdefault(key, []).append(site)

    deleted_ids: set[str] = set()
    for group in groups.values():
        if len(group) < 2:
            continue
        ordered = sorted(
            group,
            key=lambda site: (
                bool(re.search(r"#\d+$", site.external_project_id or "")),
                not _site_has_related_data(db, site),
                site.created_at,
            ),
        )
        for duplicate in ordered[1:]:
            if _site_has_related_data(db, duplicate):
                continue
            deleted_ids.add(duplicate.id)
            db.delete(duplicate)

    if deleted_ids:
        for user in db.scalars(select(models.User)).all():
            favorite_ids = list(user.favorite_site_ids or [])
            cleaned_ids = [site_id for site_id in favorite_ids if site_id not in deleted_ids]
            if cleaned_ids != favorite_ids:
                user.favorite_site_ids = cleaned_ids
    return len(deleted_ids)


def _normalize_menu_path(value: Any) -> str:
    path = str(value or "").strip().lower()
    if not path:
        return ""
    path = "/" + path.strip("/")
    return path if path == "/" else f"{path}/"


def _menu_item_matches_section(item: Any, section: models.Section) -> bool:
    if isinstance(item, str):
        return item.strip().casefold() == section.name.strip().casefold()
    if not isinstance(item, dict):
        return False

    item_path = _normalize_menu_path(item.get("path") or item.get("url") or item.get("href") or item.get("slug"))
    if item_path:
        return item_path == _normalize_menu_path(section.path)

    item_external_id = str(item.get("external_id") or item.get("externalId") or item.get("id") or "").strip().casefold()
    if item_external_id:
        return item_external_id == section.external_id.strip().casefold()

    item_name = str(item.get("title") or item.get("name") or item.get("label") or item.get("text") or "").strip().casefold()
    return bool(item_name and item_name == section.name.strip().casefold())


def _flatten_menu_items(items: list[Any]) -> list[Any]:
    flattened: list[Any] = []
    for item in items:
        flattened.append(item)
        if not isinstance(item, dict):
            continue
        children = item.get("children") or item.get("items")
        if isinstance(children, list):
            flattened.extend(_flatten_menu_items(children))
    return flattened


def _confirm_synchronized_sections(db: Session, site: models.Site, menu: dict[str, list[Any]]) -> int:
    sections = db.scalars(
        select(models.Section).where(models.Section.site_id == site.id)
    ).all()
    confirmed_count = 0
    for section in sections:
        menu_items = _flatten_menu_items(menu.get(section.menu_type, []))
        exists_in_project = any(_menu_item_matches_section(item, section) for item in menu_items)
        if not exists_in_project:
            if section.sync_status == "synced":
                section.sync_status = "external_deleted"
                section.synced_at = datetime.now(timezone.utc)
            continue
        if section.sync_status not in {"pending", "external_deleted"}:
            continue
        db.add(
            models.PublicationLog(
                endpoint_url=site.base_url,
                request_payload={
                    "action": "menu_item_sync_confirmed",
                    "project_name": site.name,
                    "name": section.name,
                    "path": section.path,
                    "menu_type": section.menu_type,
                },
                response_status=200,
                response_body={"synchronized": True},
            )
        )
        section.sync_status = "synced"
        section.synced_at = datetime.now(timezone.utc)
        confirmed_count += 1
    return confirmed_count


def sync_project_data_update(
    db: Session,
    project_name: str,
    project: dict[str, Any],
    *,
    server_host: str | None = None,
) -> int:
    """Apply a stream-triggered project data refresh without overwriting settings/head fields."""
    sites = db.scalars(select(models.Site).where(models.Site.name == project_name)).all()
    if not sites:
        return 0
    menu = _project_menu(project)
    server_value = (
        server_host
        or project.get("serverId")
        or project.get("server_id")
        or project.get("serverIp")
        or project.get("server_ip")
    )
    server_id = str(server_value or "").strip().split(".", 1)[0] or None
    synced_at = datetime.now(timezone.utc)
    for site in sites:
        site.default_menu = menu
        site.has_menu = bool(menu["header"] or menu["footer"])
        site.cache_synced_at = synced_at
        if server_id:
            site.cache_server_ip = server_id
        _confirm_synchronized_sections(db, site, menu)
    db.commit()
    return len(sites)


def sync_project_cache(db: Session, projects: list[dict[str, Any]]) -> dict[str, Any]:
    projects, skipped_duplicate_count = _deduplicate_cache_projects(projects)
    default_prompt = db.scalar(
        select(models.PromptTemplate)
        .where(models.PromptTemplate.name.in_(("Промпт рабочий", "Промт рабочий", "Промпт тест 1 v6")))
        .order_by(models.PromptTemplate.created_at.desc(), models.PromptTemplate.updated_at.desc())
        .limit(1)
    )
    working_canons = _working_project_canons()
    existing_sites = db.scalars(select(models.Site).where(models.Site.external_project_id.is_not(None))).all()
    sites_by_external_id = {site.external_project_id: site for site in existing_sites if site.external_project_id}
    now = datetime.now(timezone.utc)
    created_count = 0
    updated_count = 0
    confirmed_sections_count = 0
    matched_external_ids: set[str] = set()
    processed_external_ids: set[str] = set()
    name_occurrences: dict[str, int] = {}
    name_counts = Counter(str(project.get("name") or "").strip() for project in projects)
    cache_projects: list[dict[str, Any]] = []

    for project in projects:
        name = str(project.get("name") or "").strip()
        settings = project.get("settings") if isinstance(project.get("settings"), dict) else {}
        canon = _normalize_domain(settings.get("canon"))
        language = str(settings.get("lang") or "").strip() or None
        geo = str(settings.get("geo") or "").strip() or None
        server_ip = str(
            project.get("serverId")
            or project.get("server_id")
            or project.get("serverIp")
            or project.get("server_ip")
            or ""
        ).strip() or None
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
        domains = _project_domains(project)
        domains_count = len(domains)
        is_duplicate = name_counts[name] > 1
        has_menu = bool(menu["header"] or menu["footer"])
        is_working_project = canon in working_canons
        cache_projects.append(
            {
                "external_project_id": external_project_id,
                "name": name,
                "canon": canon or None,
                "language": language,
                "geo": geo,
                "homepage_title": homepage_title,
                "internal_pages_count": internal_pages_count,
                "domains_count": domains_count,
                "domains": domains,
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
        site.cache_language = language
        site.cache_geo = geo
        site.cache_server_ip = server_ip
        site.homepage_title = homepage_title
        site.internal_pages_count = internal_pages_count
        site.domains_count = domains_count
        site.cache_domains = domains
        if default_prompt and not site.default_prompt_template_id:
            site.default_prompt_template_id = default_prompt.id
        if is_duplicate:
            site.project_status = "duplicate"
        elif site.project_status == "duplicate":
            site.project_status = "working" if is_working_project else "not_in_focus"
        site.default_menu = menu
        confirmed_sections_count += _confirm_synchronized_sections(db, site, menu)
        site.has_menu = has_menu
        site.cache_synced_at = now
        site.is_active = True

    db.flush()
    deleted_duplicate_count = _remove_safe_site_duplicates(db)
    db.commit()
    cache_projects.sort(key=lambda project: (not project["is_working_project"], not project["has_menu"], project["name"].lower()))
    return {
        "cache_count": len(projects),
        "matched_count": len(matched_external_ids),
        "created_count": created_count,
        "updated_count": updated_count,
        "confirmed_sections_count": confirmed_sections_count,
        "skipped_duplicate_count": skipped_duplicate_count,
        "deleted_duplicate_count": deleted_duplicate_count,
        "projects": cache_projects,
    }
