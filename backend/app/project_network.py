"""Explicit reserve, canonical and alternate operations through Webdev's API."""
from contextlib import contextmanager, nullcontext
import hashlib
import json
import re
from typing import Literal
from urllib.parse import quote
from uuid import UUID

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.domain_classification import classify_domains
from app import models
from app.core.config import get_settings
from app.network_state import alternate_links, domain_name, observe_network, state_revision, validate_markup
from app.project_cache import ProjectCacheError, project_server_url, refresh_project_server_id
from app.webdev import webdev_origin_headers


from app.fake_main import create_fake_settings, select_fake_settings, delete_fake_settings, normalize_fake_path, fake_canonical_markup


class NetworkConflict(ValueError):
    pass


class DomainTypeUpdate(BaseModel):
    domain: str = Field(min_length=1, max_length=253)
    domain_type: Literal["drop", "newreg"]


class DomainHistoryUpdate(BaseModel):
    domain: str = Field(min_length=1, max_length=253)
    field: Literal["main", "alternate", "x_default", "ban"]
    checked: bool


class DomainCheck(BaseModel):
    domain: str = Field(min_length=1, max_length=253)
    revision: str


class NetworkChange(BaseModel):
    request_id: UUID
    action: Literal["reserve", "reglue", "alternates", "create_subdomains", "create_domains", "delete_domain", "create_fake_main", "select_fake_main", "domain_redirect", "domain_redirects_main", "page_redirect"]
    revision: str = Field(min_length=1, max_length=64)
    domain: str = Field(default="", max_length=253)
    alternate_markup: str = Field(default="", max_length=100000)
    enable_alternates: bool = True
    enable_canonical: bool | None = Field(default=None, strict=True)
    enable_dynamic_routes: bool | None = Field(default=None, strict=True)
    canonical_default_markup: str | None = Field(default=None, max_length=100000)
    canonical_fake_main_markup: str | None = Field(default=None, max_length=100000)
    fake_main_path: str = Field(default="", max_length=250)
    delete_fake_main: bool = Field(default=False, strict=True)
    activate_fake_main: bool = False
    domains: list[str] = Field(default_factory=list, max_length=100)
    redirect_source: str = Field(default="", max_length=253)
    redirect_target: str = Field(default="", max_length=4096)
    redirect_original_source: str = Field(default="", max_length=253)
    redirect_delete: bool = Field(default=False, strict=True)
    page_redirect_domain: str = Field(default="", max_length=253)
    page_redirect_source: str = Field(default="", max_length=2048)
    page_redirect_target: str = Field(default="", max_length=4096)
    page_redirect_original_domain: str = Field(default="", max_length=253)
    page_redirect_original_source: str = Field(default="", max_length=2048)
    page_redirect_delete: bool = Field(default=False, strict=True)


@contextmanager
def network_lock(db, site_id):
    if db.bind.dialect.name != "postgresql":
        yield
        return
    key = int(hashlib.sha256(f"project-network:{site_id}".encode()).hexdigest()[:16], 16) - 2**63
    # Nested run/domain/site locks share one dedicated connection. Taking a
    # pooled connection per key exhausts the deliberately small worker pool.
    slot = "project_network_lock_connection"
    connection = db.info.get(slot)
    owner = connection is None
    if owner:
        connection = db.bind.connect()
        db.info[slot] = connection
    try:
        if not connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}):
            raise NetworkConflict("С сеткой уже выполняется операция. Обновите данные через несколько секунд.")
        try:
            yield
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
    finally:
        if owner:
            db.info.pop(slot, None)
            connection.close()



class Remote:
    def __init__(self, db, site):
        self.site = site
        self.db = db

    def __enter__(self):
        refresh_project_server_id(self.db, self.site)
        settings = get_settings()
        if not settings.project_cache_username or not settings.project_cache_password:
            raise ProjectCacheError("Доступ к Webdev не настроен на сервере.")
        self.client = httpx.Client(timeout=60.0)
        try:
            response = self.client.post(settings.project_cache_url.rstrip("/") + "/auth/login", json={
                "username": settings.project_cache_username, "pass": settings.project_cache_password,
            }, headers=webdev_origin_headers(settings))
            response.raise_for_status()
            token = response.json().get("token")
            if not token:
                raise ProjectCacheError("Webdev не вернул токен авторизации.")
            self.client.headers["Authorization"] = f"Bearer {token}"
            return self
        except Exception:
            self.client.close()
            raise

    def __exit__(self, *_):
        self.client.close()

    def project(self):
        from app.webdev_read_retry import project_get
        response = project_get(self.client, project_server_url(self.site, "/projects/one/") + quote(self.site.name, safe=""))
        project = response.json()
        if not isinstance(project, dict) or not isinstance(project.get("settings"), dict):
            raise ProjectCacheError("Webdev вернул неполные настройки проекта.")
        return project

    def job_state(self, job_id):
        url = get_settings().project_cache_url.rstrip("/") + "/site-config/" + quote(str(job_id), safe="") + "/stream"
        token = self.client.headers["Authorization"].removeprefix("Bearer ")
        # Read just the current SSE snapshot; never wait for the whole task.
        with self.client.stream("GET", url, params={"token": token}, timeout=5.0) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line.startswith("data:"):
                    event = json.loads(line[5:].strip())
                    if isinstance(event, dict) and event.get("type") != "heartbeat":
                        return event
        return None

    def request(self, method, path, payload):
        # No retries for mutations: a timeout does not mean the operation failed.
        url = get_settings().project_cache_url.rstrip("/") + path if path in {"/site-config/create", "/site-config/delete"} else project_server_url(self.site, path)
        response = self.client.request(method, url, json=payload)
        response.raise_for_status()
        try:
            result = response.json() if response.content else {}
        except ValueError:
            # Native universal-admin backups return a plain-text filesystem path.
            if path != "/projects/backup":
                raise
            result = {"message": response.text}
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except ValueError:
                result = {"message": result}
        return response.status_code, result


def operation_matches(operation, state):
    payload = operation.request_payload
    if operation.action == 'structured_data':
        return (state.get('enableJsonMarkup') is payload.get('enableJsonMarkup')
                and state.get('jsonMarkup') == payload.get('jsonMarkup')
                and isinstance(payload.get('enableJsonMarkup'), bool) and isinstance(payload.get('jsonMarkup'), str))
    if operation.action == "page_redirect":
        return state.get('has_page_redirects') and state.get('page_redirects') == payload['pageRedirects']
    if operation.action == "reglue_redirects":
        return (state['canon'] == payload['expected_canon'] and state.get('redirects_verified', state.get('has_domain_redirects'))
                and state.get('domain_redirects') == payload['redirects'])
    if operation.action in {"domain_redirect", "domain_redirects_main"}:
        return (state.get("redirects_verified", state.get("has_domain_redirects")) and state.get("domain_redirects") == payload["redirects"]
                and (operation.action != "domain_redirects_main" or state["canon"] == payload["expected_canon"]))
    if operation.action in {"create_fake_main", "select_fake_main"}:
        return (all(state.get("fake_main_settings", {}).get(key) == value for key, value in payload["alternate"].items())
                and all(state.get(key) == value for key, value in payload.get('head_sync', {}).items())
                and ('redirects' not in payload or state.get('has_domain_redirects') and state.get('domain_redirects') == payload['redirects'])
                and ('pageRedirects' not in payload or state.get('has_page_redirects') and state.get('page_redirects') == payload['pageRedirects']))
    if payload.get('fake_main_parent_id'):
        return (state.get('fake_main_current') == payload['expected_fake_main']
                and all(state.get(key) == value for key, value in payload['head_sync'].items()))
    if payload.get('reglue_parent_id'):
        return (state.get('canon') == payload['expected_canon']
                and all(state.get(key) == value for key, value in payload['head_sync'].items()))
    if operation.action in {"create_subdomains", "create_domains"}:
        return all(item["domain"] in state["domains"] for item in payload["domains"])
    if operation.action == "delete_domain":
        return all(domain not in state["domains"] for domain in payload["domains"])
    if operation.action == "reserve":
        return state["reserve"] == payload["reserve"]
    if operation.action == "reglue":
        if state["canon"] != payload["reserve"] or any(state.get(k) != v for k, v in payload.get('head_sync', {}).items()):
            return False
        if payload.get("redirect_sync"):
            from app.domain_redirects import for_reglue
            try:
                return state.get("domain_redirects") == for_reglue(state, payload)
            except ValueError:
                return False
        return True
    return (state["has_head"] and state["alternateMarkup"] == payload["alternateMarkup"]
            and state["enableAlternates"] == payload["enableAlternates"]
            and all(state.get(key) == payload[key] for key in
                    ("enableCanonical", "canonicalDefaultMarkup", "canonicalFakeMainMarkup") if key in payload))


def observe(db, site, project):
    # This reader receives a complete native project; an absent optional list is empty.
    settings = project.get('settings') or {}
    if isinstance(settings, dict) and 'pageRedirects' not in settings:
        project = {**project, 'settings': {**settings, 'pageRedirects': []}}
    # Merge observations after reloading the row; never replace history with a remote list.
    db.refresh(site, with_for_update=True)
    state = observe_network(site, project, db=db)
    from app.reglue_reserves import reconcile_memberships
    reconcile_memberships(db, [(site, state)])
    from app.project_cache import _apply_fibery_name
    _apply_fibery_name(site, project.get("settings") if isinstance(project.get("settings"), dict) else {})
    site.cache_canon = state["canon"]
    if state["canon"]:
        site.base_url = "https://" + state["canon"]
    site.cache_domains = state["domains"]
    from app.branded_domains import apply_brand_domain_types
    from app.domain_classification import apply_default_domain_types
    apply_brand_domain_types(site)
    apply_default_domain_types(site)
    site.domains_count = len(state["domains"])
    # Production sessions disable autoflush. Include receipts just changed from
    # failed to unknown in this same verification pass.
    db.flush()
    for operation in db.scalars(select(models.NetworkOperation).where(
        models.NetworkOperation.site_id == site.id,
        models.NetworkOperation.status.in_(["pending", "unknown"]),
    )):
        observed = {**state, "redirects_verified": isinstance(project.get("settings", {}).get("redirects"), list)}
        if operation.action == 'structured_data':
            head = project.get('head') if isinstance(project.get('head'), dict) else {}
            observed.update(enableJsonMarkup=head.get('enableJsonMarkup'), jsonMarkup=head.get('jsonMarkup'))
        if operation_matches(operation, observed):
            operation.status = "confirmed"
            from app.reglue_history import confirm
            confirm(site, operation)
            if operation.action in {"reglue", "create_fake_main", "select_fake_main"}:
                from app.reglue_journal import snapshot
                from datetime import datetime, timezone
                operation.request_payload = {**operation.request_payload,
                    "confirmed_at": operation.request_payload.get("confirmed_at") or datetime.now(timezone.utc).isoformat(),
                    "journal_after": snapshot(state)}
            if operation.action == "reglue" and operation.request_payload.get("redirect_sync"):
                operation.request_payload = {**operation.request_payload, "redirects_after": state["domain_redirects"]}
            operation.message = ("Домены появились в сетке. Завершение настройки HTTPS проверяйте отдельно." if operation.action in {"create_subdomains", "create_domains"} else "Изменение подтверждено чтением настроек проекта.")
    from app.network_indexing import confirm_manual_indexing
    from app.domain_transfer_queue import observe as observe_transfer_queue
    observe_transfer_queue(db, site, state)
    db.flush()
    confirm_manual_indexing(db, site, {**state, "head_verified": isinstance(project.get("head"), dict) and "alternateMarkup" in project["head"]})
    db.commit()
    return state


def operation_history(db, site):
    active = ('pending', 'unknown', 'queued', 'running', 'waiting', 'index_queued', 'index_submitting', 'index_unknown')
    query = select(models.NetworkOperation).where(models.NetworkOperation.site_id == site.id)
    operations = [
        *db.scalars(query.where(models.NetworkOperation.status.in_(active)).order_by(models.NetworkOperation.created_at.desc())).all(),
        *db.scalars(query.where(models.NetworkOperation.status.not_in(active)).order_by(models.NetworkOperation.created_at.desc()).limit(20)).all(),
    ]
    return [{"id": op.id, "action": op.action, "status": op.status, "message": op.message,
                        "initiator": op.initiator, "created_at": op.created_at,
                        "source_domain": op.request_payload.get("source_domain") if op.action == "reglue" else None,
                        "alternates_before": op.request_payload.get("alternates_before") if op.action == "alternates" else None,
                        "alternates_after": {"markup": op.request_payload.get("alternateMarkup", ""), "enabled": op.request_payload.get("enableAlternates", False)} if op.action == "alternates" else None,
                        "redirects_before": op.request_payload.get("redirects_before") if op.action in {"domain_redirect", "domain_redirects_main", "reglue_redirects", "reglue"} else None,
                        "redirects_after": op.request_payload.get("redirects_after") if op.action == "reglue" else op.request_payload.get("redirects") if op.action in {"domain_redirect", "domain_redirects_main", "reglue_redirects"} else None,
                        "page_redirects_before": op.request_payload.get('page_redirects_before') if op.action == 'page_redirect' else None,
                        "page_redirects_after": op.request_payload.get('pageRedirects') if op.action == 'page_redirect' else None,
                        "domain": op.request_payload.get("reserve") or ((op.request_payload.get("domains") or [None])[0] if op.action == "delete_domain" else None), "domains": [item["domain"] if isinstance(item, dict) else item for item in op.request_payload.get("domains", [])], "response_status": op.response_status, "task_id": op.request_payload.get("task_id")}
                       for op in operations]


def result(db, site, state):
    from app.network_stock_warning import notice
    from app.domain_transfer_policy import banned_domains
    from app.reglue_journal import latest_for_site, recent_for_site
    return {
        "stock_warning": notice(db, site, state),
        "added_to_system_at": site.added_to_system_at,
        "fibery_name": site.fibery_name,
        "domain_bans": banned_domains(db, site, list(dict.fromkeys([*state["domains"], *state.get("amp_domains", []), *(site.main_domain_history or []), *(site.alternate_domain_history or []), *(site.x_default_history or []), *state.get("history_overrides", {}), *state.get("domain_added_at", {}), *state.get("domain_removed_at", {}), *(period["domain"] for period in state.get("domain_membership_history", []))]))),
        **state, "domain_classification": classify_domains(state["domains"], site.domain_types or {}, site.main_domain_history or [], state["canon"]), "domain_types": site.domain_types or {}, "revision": state_revision(state), "main_history": site.main_domain_history or [],
        "x_default_history": site.x_default_history or [],
        "alternate_history": site.alternate_domain_history or [],
        "alternates": alternate_links(state["alternateMarkup"]),
        "operations": operation_history(db, site),
        "last_reglue_at": site.last_reglue_at,
        "last_reglue": latest_for_site(db, site),
        "recent_network_changes": recent_for_site(db, site),
    }


def require_revision(state, revision):
    if state_revision(state) != revision:
        raise NetworkConflict("Настройки сетки изменились. Обновите данные и проверьте изменения перед сохранением.")


def require_domain(state, value):
    domain = domain_name(value)
    if not domain or domain not in state["domains"]:
        raise ValueError("Выберите резервный домен из текущей сетки.")
    from app.domain_transfer_policy import blocked_transfer_zone
    if blocked_transfer_zone(domain):
        raise ValueError("Доменная зона запрещена для переклея: БАН.")
    if domain in state.get("amp_domains", []):
        raise ValueError("AMP-домены не участвуют в переклеях и не могут быть резервом.")
    if domain == state["canon"]:
        raise ValueError("Текущий Main нельзя выбрать резервом.")
    return domain


def read_network(db, site):
    with network_lock(db, site.id), Remote(db, site) as remote:
        project = remote.project()
        state = observe(db, site, project)
        from app.reglue_redirects import continue_pending
        state, project = continue_pending(db, site, remote, state, project)
        from app.fake_main_head import continue_pending as continue_fake_head
        state, project = continue_fake_head(db, site, remote, state, project)
        for operation in db.scalars(select(models.NetworkOperation).where(
            models.NetworkOperation.site_id == site.id,
            models.NetworkOperation.action.in_(["delete_domain", "create_subdomains", "create_domains"]),
            models.NetworkOperation.status.in_(["pending", "unknown"]),
        )):
            job_id = operation.request_payload.get("job_id")
            if not job_id:
                continue
            try:
                job = remote.job_state(job_id)
            except (httpx.HTTPError, ValueError):
                continue
            if job and job.get("state") in {"failed", "completed"}:
                job_result = job.get('result') or {}
                failures = [item for item in (job.get("domains") or job_result.get('domains') or []) if item.get("status") == "error"]
                if job["state"] == "failed" or failures or job_result.get('errorCount'):
                    operation.status = "failed"
                    operation.message = str(job.get("error") or (failures[0].get("logs") if failures else None) or "Задача Webdev завершилась ошибкой.")[:2000]
        db.commit()
        metadata = {}
        if db.info.get('auto_pilot_preview'):
            from app.reglue_title_h1 import page_metadata
            try: metadata = {'page_metadata':page_metadata(project,site.homepage_title or '')}
            except (ValueError, KeyError): metadata = {'page_metadata':{'title':site.homepage_title or '', 'h1':''}}
        return {**result(db, site, state), **metadata, "head_verified": isinstance(project.get("head"), dict) and "alternateMarkup" in project["head"], "redirects_verified": isinstance(project.get("settings", {}).get("redirects"), list)}


def check_domain(db, site, payload):
    with network_lock(db, site.id), Remote(db, site) as remote:
        state = observe(db, site, remote.project())
        require_revision(state, payload.revision)
        domain = require_domain(state, payload.domain)
        _, response = remote.request("POST", "/projects/check-domain", {"domain": domain})
        if not isinstance(response, dict) or not isinstance(response.get("reachable"), bool):
            raise ProjectCacheError("Webdev не вернул результат проверки домена.")
        return {"domain": domain, "reachable": response["reachable"], "reason": str(response.get("reason") or "")}


def validate_subdomains(values, cached_domains, require_parent=True):
    if not values:
        raise ValueError("Укажите поддомены для создания.")
    known = {domain_name(value) for value in cached_domains}
    known.discard("")
    if require_parent and not known:
        raise ValueError("В базе нет сохранённой сетки. Сначала загрузите кэш проекта.")
    parents = {value.removeprefix("www.") for value in known}
    domains = []
    for value in values:
        raw = value.strip().lower().rstrip(".")
        try:
            domain = raw.encode("idna").decode()
        except UnicodeError:
            raise ValueError("Некорректное имя поддомена.") from None
        if "." not in domain or len(domain) > 253 or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in domain.split(".")):
            raise ValueError("Укажите имена поддоменов без протокола, пути и wildcard.")
        if domain in known:
            raise ValueError(f"Поддомен {domain} уже есть в сетке.")
        if require_parent and not any(domain.endswith("." + parent) and domain != "www." + parent for parent in parents):
            raise ValueError(f"Родительский домен для {domain} отсутствует в сохранённой сетке проекта.")
        if domain not in domains:
            domains.append(domain)
    return domains



def deletion_domains(payload):
    raw = payload.domains or [payload.domain]
    domains = list(dict.fromkeys(domain_name(value) for value in raw))
    if not domains or any(not value for value in domains) or len(domains)>100:
        raise ValueError('Укажите от 1 до 100 корректных доменов для удаления.')
    return domains

def change_network(db, site, payload, username, *, auto_run_id=None):
    # Local cache gate runs before authentication or any remote requests.
    existing_receipt = db.get(models.NetworkOperation, str(payload.request_id))
    if payload.action == "delete_domain" and not existing_receipt:
        for domain in deletion_domains(payload):
            if domain not in (site.cache_domains or []):
                raise ValueError("Домен отсутствует в сохранённой сетке проекта: " + domain)
    if payload.action in {"create_subdomains", "create_domains"} and not existing_receipt:
        validate_subdomains(payload.domains, site.cache_domains or [], require_parent=payload.action == "create_subdomains")
        from app.domain_transfer_policy import require_main_destination
        require_main_destination(db, site, payload.domains)
    from app.fake_path_allocation import group_lock, require_available
    path_lock = group_lock(db, site) if payload.action in {'reglue', 'create_fake_main', 'select_fake_main'} else nullcontext()
    with network_lock(db, site.id), path_lock, Remote(db, site) as remote:
        from app.auto_reglue import blocking_run
        active_auto = blocking_run(db, site.id, db.get(models.AutoReglueRun, auto_run_id) if auto_run_id else None)
        if active_auto is not None and active_auto.id != auto_run_id:
            raise NetworkConflict("У проекта незавершённый автопереклей. Дождитесь результата или остановите его в настройках.")
        existing = db.get(models.NetworkOperation, str(payload.request_id))
        if existing and (existing.site_id != site.id or existing.action != payload.action):
            raise NetworkConflict("Идентификатор запроса уже используется другой операцией.")
        project = remote.project()
        state = observe(db, site, project)
        if existing:
            return result(db, site, state)
        if payload.action == "delete_domain" and auto_run_id:
            from app.domain_redirects import require_transfer_free
            require_transfer_free({**state, "redirects_verified": isinstance(project.get("settings", {}).get("redirects"), list)}, deletion_domains(payload))
        require_revision(state, payload.revision)
        if auto_run_id:
            run = db.get(models.AutoReglueRun, auto_run_id)
            from app.mass_action_scope import require_run_scope
            require_run_scope(db, run)
            from app.mass_reglue_launch import require_run
            require_run(db, run)
            if run and run.plan.get('execution_mode') == 'transfer_only':
                from app.domain_redistribution import validate_write
                validate_write(db, run, site, payload)
            if run and run.plan.get('execution_mode') == 'cross_network':
                from app.cross_reglue import require_pair
                if run.plan.get('reserve_pool_id'):
                    if site.id != run.site_id or run.plan['source_site_id'] != run.site_id or payload.action not in {'create_domains', 'reserve', 'reglue', 'alternates', 'create_fake_main'}:
                        raise ValueError('Операция не соответствует плану добавления из базы резервов.')
                    from app import reglue_reserves as pool
                    from app.cross_reglue import require_import_for_plan
                    row = db.get(models.ReglueReserveDomain, run.plan['reserve_pool_id'])
                    if row is None or row.run_id != run.id or row.domain != run.plan['new_main']:
                        raise ValueError('Домен не выделен этому запуску.')
                    if payload.action == 'create_domains':
                        if payload.domains != [row.domain]:
                            raise ValueError('Домен не соответствует базе резервов.')
                        pool.validate_plan(db, site, state, run.plan, run=run)
                        require_import_for_plan(db, site, state, run.plan)
                elif run.plan.get('local_target'):
                    if site.id != run.site_id or run.plan['source_site_id'] != run.site_id or payload.action in {'delete_domain','create_domains'}:
                        raise ValueError('Локальная доля не допускает переноса доменов.')
                    if payload.action == 'create_subdomains':
                        if payload.domains != [run.plan.get('create_subdomain')]:
                            raise ValueError('Поддомен не соответствует зарезервированному плану.')
                        from app.mass_main_targets import require_target
                        require_target(db, site, state, run.plan)
                elif run.plan.get('use_selected_reserve'):
                    if site.id != run.site_id or run.plan['source_site_id'] != run.site_id or payload.action in {'delete_domain', 'create_domains', 'create_subdomains'}:
                        raise ValueError('Переклей на выбранный резерв не допускает переноса доменов.')
                else:
                    require_pair(db.get(models.Site, run.plan['source_site_id']), db.get(models.Site, run.site_id))
            if run and payload.action == 'delete_domain' and run.plan.get('execution_mode') in {'cross_network', 'transfer_only'}:
                from app.network_reserve import require_import_target
                if run.plan.get('requires_newreg') and any((site.domain_types or {}).get(d) != 'newreg' for d in deletion_domains(payload)):
                    raise ValueError('Для переклея без резерва требуется новорег.')
                target_ids = {run.site_id}
                if run.plan.get('extraction_batch'):
                    from app.move_batch import extraction
                    peers, _ = extraction(db, run)
                    target_ids.update(peer.site_id for peer in peers)
                for target_id in target_ids:
                    receiving = db.get(models.Site, target_id)
                    receiving_state = read_network(db, receiving)
                    if run.plan.get('execution_mode') == 'cross_network':
                        from app.cross_reglue import require_import_for_plan
                        require_import_for_plan(db, receiving, receiving_state, run.plan)
                    else:
                        require_import_target(receiving_state)
            if run and run.plan.get('execution_mode') == 'cross_network' and payload.action == 'create_domains' and not run.plan.get('reserve_pool_id'):
                from app.cross_reglue import receipt_id, completed_job
                deletion = db.get(models.NetworkOperation, receipt_id(run, 'delete_domain'))
                source = db.get(models.Site, run.plan['source_site_id'])
                if payload.domains != [run.plan['new_main']] or site.id != run.site_id or not deletion or deletion.site_id != source.id or not completed_job(db, source, deletion):
                    raise ValueError('Добавление при переносе разрешено только после подтверждённого извлечения домена.')

        if not auto_run_id and db.scalar(select(models.NetworkOperation.id).where(
            models.NetworkOperation.site_id == site.id,
            models.NetworkOperation.status.in_(["pending", "unknown"]),
        ).limit(1)):
            raise NetworkConflict("Предыдущая операция ещё не подтверждена. Обновите данные сетки; повторная отправка заблокирована.")
        request = {"folder": site.name.encode("idna").decode()}
        method = "POST"
        if payload.action in {"create_subdomains", "create_domains"}:
            domains = validate_subdomains(payload.domains, state["domains"], require_parent=payload.action == "create_subdomains")
            port = str(project["settings"].get("port") or "")
            if not port.isdigit() or not 0 < int(port) <= 65535:
                raise ValueError("В настройках проекта отсутствует корректный port.")
            path = "/site-config/create"
            request = {
                "server": project_server_url(site, "/").split("://", 1)[1].rstrip("/"),
                "project": site.name.encode("idna").decode(),
                "username": get_settings().project_cache_username,
                "port": port,
                "domains": [{"id": f"{payload.request_id}-{i}", "domain": domain, "wwwPrimary": False} for i, domain in enumerate(domains)],
            }
        elif payload.action == "delete_domain":
            domains = deletion_domains(payload)
            from app.network_reserve import reserved_domains
            protected = {domain_name(value).removeprefix("www.") for value in
                [site.name, state["canon"], *reserved_domains(state), *state.get("amp_domains", []), state.get("amp", "")]}
            markup = state["alternateMarkup"].replace("{{settings.canon}}", state["canon"])
            used = {link['domain'].removeprefix('www.') for link in alternate_links(markup)}
            for domain in domains:
                if domain not in state['domains']:
                    raise ValueError('Домен отсутствует в актуальной сетке проекта: ' + domain)
                bare=domain.removeprefix('www.')
                if bare in protected:
                    raise ValueError('Нельзя удалить домен проекта, текущий Main, AMP или резерв. Сначала измените назначение домена. ' + domain)
                if bare in used:
                    raise ValueError('Домен используется в альтернейтах. Сначала измените разметку. ' + domain)
            path = "/site-config/delete"
            request = {"server": project_server_url(site, "/").split("://", 1)[1].rstrip("/"),
                "project": site.name.encode("idna").decode(), "username": get_settings().project_cache_username,
                "domains": [domain.encode('idna').decode() for domain in domains]}
        elif payload.action == "domain_redirects_main":
            from app.domain_redirects import all_to_main
            path = "/projects/update-value"
            request["redirects"] = all_to_main(state)
        elif payload.action == "domain_redirect":
            from app.domain_redirects import update_redirects
            path = "/projects/update-value"
            request["redirects"] = update_redirects(project, payload.redirect_source, payload.redirect_target, payload.redirect_original_source, delete=payload.redirect_delete)
        elif payload.action == 'page_redirect':
            from app.page_redirects import update
            from app.domain_redirects import redirect_domain
            if not payload.page_redirect_delete and redirect_domain(payload.page_redirect_domain) not in state['domains']:
                raise ValueError('Выберите домен из текущей сетки проекта.')
            path = '/projects/update-value'
            request['pageRedirects'] = update(project, payload.page_redirect_domain, payload.page_redirect_source,
                payload.page_redirect_target, payload.page_redirect_original_domain,
                payload.page_redirect_original_source, payload.page_redirect_delete)
        elif payload.action in {"create_fake_main", "select_fake_main"}:
            path = "/projects/update-value"
            if not payload.delete_fake_main and payload.fake_main_path and (payload.activate_fake_main or payload.action == 'select_fake_main'):
                require_available(db, site, payload.fake_main_path)
            if payload.action == 'create_fake_main' and payload.activate_fake_main:
                if normalize_fake_path(payload.fake_main_path) in state.get('fake_main_history', []):
                    raise ValueError('Путь новой фейковой страницы уже использован. Подготовьте новый план.')
            if payload.delete_fake_main:
                if payload.action != "select_fake_main" or payload.enable_dynamic_routes is not None:
                    raise ValueError("Удаление страницы нельзя совмещать с созданием или переключением динамических страниц.")
                request["alternate"] = delete_fake_settings(project, payload.fake_main_path)
            elif payload.action == "select_fake_main" and payload.enable_dynamic_routes is not None:
                alternate = (project.get("settings") or {}).get("alternate") or {}
                if not isinstance(alternate, dict):
                    raise ValueError("Не удалось прочитать настройки динамических страниц. Обновите данные проекта.")
                request["alternate"] = {**alternate, "enableDynamicRoutes": payload.enable_dynamic_routes}
            else:
                request["alternate"] = (create_fake_settings(project, payload.fake_main_path, activate=payload.activate_fake_main)
                                        if payload.action == "create_fake_main" else select_fake_settings(project, payload.fake_main_path))
        elif payload.action in {"reserve", "reglue"}:
            domain = require_domain(state, payload.domain)
            request["reserve"] = domain
            if payload.action == "reserve":
                path = "/projects/update-value"
                request["reserveOption"] = domain
            else:
                if state["reserve"] != domain:
                    raise NetworkConflict("Сначала сохраните выбранный резервный домен.")
                if state.get('fake_main_enabled'):
                    require_available(db, site, state.get('fake_main_current'))
                if auto_run_id is not None:
                    from app.reglue_dns import allowed
                    if not allowed(db.get(models.AutoReglueRun, auto_run_id)):
                        _, check = remote.request("POST", "/projects/check-domain", {"domain": domain})
                        if not isinstance(check, dict) or check.get("reachable") is not True:
                            raise ValueError("Резервный домен не подтвердил доступность. Проверьте домен перед переклеем.")
                from app.domain_redirects import retarget_redirects
                # Full redirect settings must be known before changing Main.
                retarget_redirects({**state, "redirects_verified": isinstance(project["settings"].get("redirects"), list)}, state["canon"], domain)
                path = "/projects/update-reglue"
                request.update(trigger="webdev:settings", initiator=get_settings().project_cache_username)
        else:
            if not state["has_head"]:
                raise ValueError("У проекта отсутствует head; сохранение альтернейтов недоступно.")
            validate_markup(payload.alternate_markup)
            method, path = "PATCH", "/projects/update-head"
            request.update(alternateMarkup=payload.alternate_markup, enableAlternates=payload.enable_alternates)
            if payload.enable_canonical is not None:
                request["enableCanonical"] = payload.enable_canonical
            for source, target in ((payload.canonical_default_markup, "canonicalDefaultMarkup"), (payload.canonical_fake_main_markup, "canonicalFakeMainMarkup")):
                if source is not None:
                    if source.strip() and not re.fullmatch(r"<link\s+rel=[\"']canonical[\"']\s+href=[\"']https?://[^\"'<>\s]+[\"']\s*/?>", source.strip(), re.IGNORECASE):
                        raise ValueError('Каноникл должен содержать одну ссылку <link rel="canonical" href="https://…" />.')
                    request[target] = source
            if payload.fake_main_path:
                fake_path = normalize_fake_path(payload.fake_main_path)
                from app.canonical_allocation import mode as canonical_mode
                if ((not payload.enable_alternates and canonical_mode(payload.canonical_fake_main_markup) != 'self') or not state['fake_main_enabled']
                        or state['fake_main_current'] != fake_path or fake_path not in state['fake_main_paths']):
                    raise ValueError('Для canonical выберите действующий включённый фейковый внутряк и включите альтернейты.')
                request.update(enableCanonical=True, canonicalFakeMainMarkup=payload.canonical_fake_main_markup if payload.canonical_fake_main_markup is not None else fake_canonical_markup(fake_path))
                if not state['canonicalDefaultMarkup']:
                    request['canonicalDefaultMarkup'] = '<link rel="canonical" href="https://{{settings.canon}}{{reqPath}}" />'
        if payload.action in {"create_fake_main", "select_fake_main"} and not payload.delete_fake_main:
            from app.fake_main_redirects import retarget
            request.update(retarget(project, state.get('fake_main_current'),
                                    request['alternate'].get('currentFakeMain'), state['canon']))
        stored_request = dict(request)
        if payload.action in {"reglue", "create_fake_main", "select_fake_main"}:
            from app.reglue_journal import snapshot
            stored_request["journal_before"] = snapshot(state)
        if payload.action in {'create_fake_main', 'select_fake_main'}:
            from app.fake_main import retarget_fake_head
            changes = retarget_fake_head(state, state.get('fake_main_current'), request['alternate'].get('currentFakeMain'))
            if changes:
                stored_request.update(head_sync=changes, head_before={key: state[key] for key in changes})
        if payload.action in {"domain_redirect", "domain_redirects_main"}:
            stored_request["redirects_before"] = state["domain_redirects"]
            if payload.action == "domain_redirects_main":
                stored_request["expected_canon"] = state["canon"]
        if payload.action == 'page_redirect':
            stored_request['page_redirects_before'] = state['page_redirects']
        if auto_run_id:
            run = db.get(models.AutoReglueRun, auto_run_id)
            if run and run.plan.get('execution_mode') == 'cross_network':
                stored_request['cross_network_transfer'] = {
                    'run_id': run.id, 'source_site_id': run.plan['source_site_id'],
                    'source_project': run.plan['source_project'], 'target_site_id': run.site_id,
                    'target_project': run.plan['project'], 'domain': run.plan['new_main'],
                }

        if auto_run_id:
            stored_request["auto_run_id"] = auto_run_id
        if payload.action == "reglue":
            stored_request["source_domain"] = state["canon"]
            stored_request["redirect_sync"] = True
            stored_request["redirects_before"] = state["domain_redirects"]
            if auto_run_id:
                run = db.get(models.AutoReglueRun, auto_run_id)
                if run:
                    from app.canonical_allocation import mode
                    plan = run.plan
                    redirect_fake_path = plan.get('fake_main_path') or ''
                    internal = mode(plan.get('canonicalFakeMainMarkup'), redirect_fake_path) == 'internal'
                    stored_request['redirect_target'] = domain + (redirect_fake_path if internal else '')
                    stored_request['redirect_old_main'] = bool(plan.get('redirect_old_main'))
            if auto_run_id is None:
                from app.reglue_head import retarget_main_alternates
                changes = retarget_main_alternates(state, domain)
                if changes:
                    stored_request.update(head_sync=changes, head_before={key: state[key] for key in changes})
                stored_request.update(indexing_pending=True, _indexing={
                    "canon": domain, "alternateMarkup": changes.get('alternateMarkup', state["alternateMarkup"]),
                    "enableAlternates": state["enableAlternates"],
                })
        elif payload.action == "alternates":
            stored_request["alternates_before"] = {
                "markup": state["alternateMarkup"], "enabled": state["enableAlternates"],
            }
            if payload.fake_main_path or payload.enable_canonical is not None or payload.canonical_default_markup is not None or payload.canonical_fake_main_markup is not None:
                stored_request['canonical_before'] = {key: state[key] for key in
                    ('enableCanonical', 'canonicalDefaultMarkup', 'canonicalFakeMainMarkup')}
        if auto_run_id:
            run = db.get(models.AutoReglueRun, auto_run_id)
            if run and run.plan.get('execution_mode') in {'transfer_only', 'cross_network'}:
                from app import domain_transfer_queue as transfer_queue
                if payload.action == 'delete_domain':
                    if run.plan.get('extraction_batch'):
                        from app.move_batch import extraction
                        peers,_=extraction(db,run)
                        transfer_queue.reserve_extraction(db,peers,str(payload.request_id))
                    else:transfer_queue.reserve(db, run, deletion_domains(payload), str(payload.request_id))
                elif payload.action == 'create_domains':
                    transfer_queue.adding(db, run, payload.domains, str(payload.request_id))
        operation = models.NetworkOperation(id=str(payload.request_id), site_id=site.id, action=payload.action,
                                            initiator=username, request_payload=stored_request, status="pending")
        db.add(operation)
        db.commit()  # Receipt exists even if the connection or process stops after sending.
        try:
            code, response = remote.request(method, path, request)
            operation.response_status = code
            if isinstance(response, dict) and (response.get("errors") or response.get("success") is False or response.get("error")):
                operation.status = "failed"
                operation.message = str(response.get("message") or response.get("errors") or response.get("error"))[:2000]
            elif payload.action in {"create_subdomains", "create_domains", "delete_domain"}:
                if not isinstance(response, dict) or not response.get("jobId"):
                    operation.status = "unknown"
                    operation.message = "Webdev не вернул номер задачи. Повторная отправка заблокирована; обновите сетку."
                else:
                    operation.request_payload = {**operation.request_payload, "job_id": str(response["jobId"])}
                    operation.message = (f"Задача удаления {response['jobId']} запущена. Ожидаем удаления домена из сетки."
                        if payload.action == "delete_domain" else f"Задача создания {response['jobId']} запущена. Ожидаем появления доменов в сетке.")
                    if response.get("skipped"):
                        operation.message += " Webdev пропустил часть доменов: " + str(response["skipped"])[:1000]
            else:
                operation.message = "Запрос отправлен. Ожидается подтверждение настроек проекта."
        except httpx.HTTPStatusError as exc:
            operation.response_status = exc.response.status_code
            operation.status = "failed" if 400 <= exc.response.status_code < 500 else "unknown"
            operation.message = f"Webdev вернул HTTP {exc.response.status_code}. Обновите сетку для проверки результата."
            try:
                body = exc.response.json()
                detail = {key: body[key] for key in ('message', 'error', 'errors', 'statusCode') if key in body} if isinstance(body, dict) else {}
            except ValueError:
                detail = {}
            operation.request_payload = {**operation.request_payload, 'http_error': {'status': exc.response.status_code, 'detail': str(detail)[:2000]}}
        except (httpx.HTTPError, ValueError):
            operation.status = "unknown"
            operation.message = "Ответ не получен или не распознан. Запрос мог выполниться; обновите сетку для проверки результата."
        db.commit()
        try:
            if auto_run_id and operation.status == 'failed' and payload.action in {'create_fake_main', 'select_fake_main', 'reglue', 'alternates'}:
                from app.reglue_dns import allowed, is_dns_error
                if allowed(db.get(models.AutoReglueRun, auto_run_id)) and is_dns_error(operation.message):
                    # The write may have succeeded before Webdev's DNS health-check.
                    # Only a fresh read and exact setting comparison may confirm it.
                    operation.status = 'unknown'
                    operation.request_payload = {**operation.request_payload, 'dns_health_warning': operation.message}
                    db.commit()
            project = remote.project()
            state = observe(db, site, project)
            if auto_run_id and operation.status == 'failed' and payload.action in {'create_fake_main', 'select_fake_main', 'reglue', 'alternates'}:
                from app.reglue_dns import allowed, note
                run = db.get(models.AutoReglueRun, auto_run_id)
                actual = {**state, 'redirects_verified': isinstance(project.get('settings', {}).get('redirects'), list)}
                if allowed(run) and operation_matches(operation, actual):
                    message = operation.message
                    operation.status = 'unknown'
                    state = observe(db, site, project)
                    note(db, run, run.plan['new_main'], f'Настройки подтверждены чтением Webdev. Ответ при сохранении: HTTP {operation.response_status}. {message}')
            if payload.action == "reglue":
                from app.reglue_redirects import continue_pending
                state, project = continue_pending(db, site, remote, state, project)
            if payload.action in {'create_fake_main', 'select_fake_main', 'reglue'}:
                from app.fake_main_head import continue_pending
                state, project = continue_pending(db, site, remote, state, project)
        except (httpx.HTTPError, ValueError, ProjectCacheError):
            # Keep the durable receipt visible; do not re-send the write.
            if operation.status == "pending":
                operation.status = "unknown"
                operation.message = "Не удалось перечитать настройки. Обновите сетку для проверки результата."
                db.commit()
        return result(db, site, state)


def update_domain_type(db, site, payload):
    # Separate local metadata: cache refreshes never overwrite these values.
    db.refresh(site, with_for_update=True)
    domain = domain_name(payload.domain)
    known = set(site.cache_domains or []) | set(site.main_domain_history or []) | set(site.alternate_domain_history or [])
    known.update((site.network_state or {}).get("domain_added_at", {}))
    known.update((site.network_state or {}).get("domain_removed_at", {}))
    known.update(period["domain"] for period in (site.network_state or {}).get("domain_membership_history", []))
    if site.cache_canon:
        known.add(domain_name(site.cache_canon))
    if domain not in known:
        raise ValueError("Домен отсутствует в сохранённой сетке и истории проекта.")
    if domain in (site.network_state or {}).get("amp_domains", []) or (site.domain_types or {}).get(domain) == "amp":
        raise ValueError("Тип AMP определяется настройками проекта и не меняется вручную.")
    site.domain_types = {**(site.domain_types or {}), domain: payload.domain_type}
    db.commit()
    return {"domain_types": site.domain_types, "domain_classification": classify_domains(site.cache_domains or [], site.domain_types, site.main_domain_history or [], site.cache_canon or "")}


def update_domain_history(db, site, payload, initiator):
    from datetime import datetime, timezone
    from app.network_state import HISTORY_FIELDS, apply_history_overrides, is_project_identity
    db.refresh(site, with_for_update=True)
    domain = domain_name(payload.domain)
    state = dict(site.network_state or {})
    known = set(site.cache_domains or []) | set(state.get("domains", [])) | set(state.get("amp_domains", []))
    for attribute in HISTORY_FIELDS.values():
        known.update(getattr(site, attribute) or [])
    if site.cache_canon:
        known.add(domain_name(site.cache_canon))
    known.update(state.get("history_overrides", {}))
    known.update(state.get("domain_added_at", {}))
    known.update(state.get("domain_removed_at", {}))
    known.update(period["domain"] for period in state.get("domain_membership_history", []))
    if not domain or domain not in known:
        raise ValueError("Домен отсутствует в сетке и истории проекта.")
    if not payload.checked and is_project_identity(site, domain):
        raise ValueError("Домен является именем проекта Webdev. Защитные отметки снимать нельзя.")
    if payload.field == "ban":
        from app.domain_transfer_policy import set_ban
        set_ban(db, site, domain, payload.checked, initiator)
        return result(db, site, state)
    overrides = dict(state.get("history_overrides", {}))
    flags = dict(overrides.get(domain, {}))
    before = domain in (getattr(site, HISTORY_FIELDS[payload.field]) or [])
    flags[payload.field] = payload.checked
    overrides[domain] = flags
    state["history_overrides"] = overrides
    state["history_edits"] = [*state.get("history_edits", []), {
        "domain": domain, "field": payload.field, "before": before,
        "checked": payload.checked, "initiator": initiator,
        "at": datetime.now(timezone.utc).isoformat(),
    }]
    apply_history_overrides(site, overrides)
    site.network_state = state
    db.commit()
    return result(db, site, state)
