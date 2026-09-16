"""Explicit reserve, canonical and alternate operations through Webdev's API."""
from contextlib import contextmanager
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


from app.fake_main import create_fake_settings, select_fake_settings


class NetworkConflict(ValueError):
    pass


class DomainTypeUpdate(BaseModel):
    domain: str = Field(min_length=1, max_length=253)
    domain_type: Literal["drop", "newreg"]


class DomainCheck(BaseModel):
    domain: str = Field(min_length=1, max_length=253)
    revision: str


class NetworkChange(BaseModel):
    request_id: UUID
    action: Literal["reserve", "reglue", "alternates", "create_subdomains", "delete_domain", "create_fake_main", "select_fake_main"]
    revision: str = Field(min_length=1, max_length=64)
    domain: str = Field(default="", max_length=253)
    alternate_markup: str = Field(default="", max_length=100000)
    enable_alternates: bool = True
    fake_main_path: str = Field(default="", max_length=250)
    domains: list[str] = Field(default_factory=list, max_length=100)


@contextmanager
def network_lock(db, site_id):
    if db.bind.dialect.name != "postgresql":
        yield
        return
    key = int(hashlib.sha256(f"project-network:{site_id}".encode()).hexdigest()[:16], 16) - 2**63
    with db.bind.connect() as connection:
        if not connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}):
            raise NetworkConflict("С сеткой уже выполняется операция. Обновите данные через несколько секунд.")
        try:
            yield
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})


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
            })
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
        response = self.client.get(project_server_url(self.site, "/projects/one/") + quote(self.site.name, safe=""))
        response.raise_for_status()
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
        result = response.json() if response.content else {}
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except ValueError:
                result = {"message": result}
        return response.status_code, result


def operation_matches(operation, state):
    payload = operation.request_payload
    if operation.action in {"create_fake_main", "select_fake_main"}:
        return all(state.get("fake_main_settings", {}).get(key) == value for key, value in payload["alternate"].items())
    if operation.action == "create_subdomains":
        return all(item["domain"] in state["domains"] for item in payload["domains"])
    if operation.action == "delete_domain":
        return all(domain not in state["domains"] for domain in payload["domains"])
    if operation.action == "reserve":
        return state["reserve"] == payload["reserve"]
    if operation.action == "reglue":
        return state["canon"] == payload["reserve"]
    return state["has_head"] and state["alternateMarkup"] == payload["alternateMarkup"] and state["enableAlternates"] == payload["enableAlternates"]


def observe(db, site, project):
    # Merge observations after reloading the row; never replace history with a remote list.
    db.refresh(site, with_for_update=True)
    state = observe_network(site, project)
    site.cache_canon = state["canon"]
    if state["canon"]:
        site.base_url = "https://" + state["canon"]
    site.cache_domains = state["domains"]
    from app.branded_domains import apply_brand_domain_types
    from app.domain_classification import apply_default_domain_types
    apply_brand_domain_types(site)
    apply_default_domain_types(site)
    site.domains_count = len(state["domains"])
    for operation in db.scalars(select(models.NetworkOperation).where(
        models.NetworkOperation.site_id == site.id,
        models.NetworkOperation.status.in_(["pending", "unknown"]),
    )):
        if operation_matches(operation, state):
            operation.status = "confirmed"
            operation.message = ("Поддомены появились в сетке. Завершение настройки HTTPS проверяйте отдельно." if operation.action == "create_subdomains" else "Изменение подтверждено чтением настроек проекта.")
    from app.network_indexing import confirm_manual_indexing
    db.flush()
    confirm_manual_indexing(db, site, {**state, "head_verified": isinstance(project.get("head"), dict) and "alternateMarkup" in project["head"]})
    db.commit()
    return state


def operation_history(db, site):
    operations = db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.site_id == site.id)
                           .order_by(models.NetworkOperation.created_at.desc()).limit(20)).all()
    return [{"id": op.id, "action": op.action, "status": op.status, "message": op.message,
                        "initiator": op.initiator, "created_at": op.created_at,
                        "domain": op.request_payload.get("reserve") or ((op.request_payload.get("domains") or [None])[0] if op.action == "delete_domain" else None), "domains": [item["domain"] if isinstance(item, dict) else item for item in op.request_payload.get("domains", [])], "response_status": op.response_status, "task_id": op.request_payload.get("task_id")}
                       for op in operations]


def result(db, site, state):
    return {
        **state, "domain_classification": classify_domains(state["domains"], site.domain_types or {}, site.main_domain_history or [], state["canon"]), "domain_types": site.domain_types or {}, "revision": state_revision(state), "main_history": site.main_domain_history or [],
        "x_default_history": site.x_default_history or [],
        "alternate_history": site.alternate_domain_history or [],
        "alternates": alternate_links(state["alternateMarkup"]),
        "operations": operation_history(db, site),
    }


def require_revision(state, revision):
    if state_revision(state) != revision:
        raise NetworkConflict("Настройки сетки изменились. Обновите данные и проверьте изменения перед сохранением.")


def require_domain(state, value):
    domain = domain_name(value)
    if not domain or domain not in state["domains"]:
        raise ValueError("Выберите резервный домен из текущей сетки.")
    if domain in state.get("amp_domains", []):
        raise ValueError("AMP-домены не участвуют в переклеях и не могут быть резервом.")
    if domain == state["canon"]:
        raise ValueError("Текущий Main нельзя выбрать резервом.")
    return domain


def read_network(db, site):
    with network_lock(db, site.id), Remote(db, site) as remote:
        project = remote.project()
        state = observe(db, site, project)
        for operation in db.scalars(select(models.NetworkOperation).where(
            models.NetworkOperation.site_id == site.id,
            models.NetworkOperation.action.in_(["delete_domain", "create_subdomains"]),
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
                failures = [item for item in job.get("domains", []) if item.get("status") == "error"]
                if job["state"] == "failed" or failures:
                    operation.status = "failed"
                    operation.message = str(job.get("error") or (failures[0].get("logs") if failures else None) or "Задача Webdev завершилась ошибкой.")[:2000]
        db.commit()
        return {**result(db, site, state), "head_verified": isinstance(project.get("head"), dict) and "alternateMarkup" in project["head"]}


def check_domain(db, site, payload):
    with network_lock(db, site.id), Remote(db, site) as remote:
        state = observe(db, site, remote.project())
        require_revision(state, payload.revision)
        domain = require_domain(state, payload.domain)
        _, response = remote.request("POST", "/projects/check-domain", {"domain": domain})
        if not isinstance(response, dict) or not isinstance(response.get("reachable"), bool):
            raise ProjectCacheError("Webdev не вернул результат проверки домена.")
        return {"domain": domain, "reachable": response["reachable"], "reason": str(response.get("reason") or "")}


def validate_subdomains(values, cached_domains):
    if not values:
        raise ValueError("Укажите поддомены для создания.")
    known = {domain_name(value) for value in cached_domains}
    known.discard("")
    if not known:
        raise ValueError("В базе нет сохранённой сетки. Сначала загрузите кэш проекта.")
    parents = {value.removeprefix("www.") for value in known}
    domains = []
    for value in values:
        raw = value.strip().lower().rstrip(".")
        try:
            domain = raw.encode("idna").decode()
        except UnicodeError:
            raise ValueError("Некорректное имя поддомена.") from None
        if len(domain) > 253 or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in domain.split(".")):
            raise ValueError("Укажите имена поддоменов без протокола, пути и wildcard.")
        if domain in known:
            raise ValueError(f"Поддомен {domain} уже есть в сетке.")
        if not any(domain.endswith("." + parent) and domain != "www." + parent for parent in parents):
            raise ValueError(f"Родительский домен для {domain} отсутствует в сохранённой сетке проекта.")
        if domain not in domains:
            domains.append(domain)
    return domains


def change_network(db, site, payload, username, *, auto_run_id=None):
    # Local cache gate runs before authentication or any remote requests.
    existing_receipt = db.get(models.NetworkOperation, str(payload.request_id))
    if payload.action == "delete_domain" and not existing_receipt:
        if domain_name(payload.domain) not in (site.cache_domains or []):
            raise ValueError("Домен отсутствует в сохранённой сетке проекта.")
    if payload.action == "create_subdomains" and not existing_receipt:
        validate_subdomains(payload.domains, site.cache_domains or [])
    with network_lock(db, site.id), Remote(db, site) as remote:
        active_auto = db.scalar(select(models.AutoReglueRun).where(
            models.AutoReglueRun.site_id == site.id,
            models.AutoReglueRun.status.in_(["queued", "running", "waiting", "partial"]),
        ))
        if active_auto is not None and active_auto.id != auto_run_id:
            raise NetworkConflict("У проекта незавершённый автопереклей. Дождитесь результата или остановите его в настройках.")
        existing = db.get(models.NetworkOperation, str(payload.request_id))
        if existing and (existing.site_id != site.id or existing.action != payload.action):
            raise NetworkConflict("Идентификатор запроса уже используется другой операцией.")
        project = remote.project()
        state = observe(db, site, project)
        if existing:
            return result(db, site, state)
        require_revision(state, payload.revision)
        if db.scalar(select(models.NetworkOperation.id).where(
            models.NetworkOperation.site_id == site.id,
            models.NetworkOperation.status.in_(["pending", "unknown"]),
        ).limit(1)):
            raise NetworkConflict("Предыдущая операция ещё не подтверждена. Обновите данные сетки; повторная отправка заблокирована.")
        request = {"folder": site.name.encode("idna").decode()}
        method = "POST"
        if payload.action == "create_subdomains":
            domains = validate_subdomains(payload.domains, state["domains"])
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
            domain = domain_name(payload.domain)
            if domain not in state["domains"]:
                raise ValueError("Домен отсутствует в актуальной сетке проекта.")
            bare = domain.removeprefix("www.")
            protected = {domain_name(value).removeprefix("www.") for value in [site.name, state["canon"], state["reserve"], state.get("amp", "")]}
            if bare in protected:
                raise ValueError("Нельзя удалить домен проекта, текущий Main, AMP или резерв. Сначала измените назначение домена.")
            markup = state["alternateMarkup"].replace("{{settings.canon}}", state["canon"])
            if any(link["domain"].removeprefix("www.") == bare for link in alternate_links(markup)):
                raise ValueError("Домен используется в альтернейтах. Сначала измените разметку.")
            path = "/site-config/delete"
            request = {
                "server": project_server_url(site, "/").split("://", 1)[1].rstrip("/"),
                "project": site.name.encode("idna").decode(),
                "username": get_settings().project_cache_username,
                "domains": [domain.encode("idna").decode()],
            }
        elif payload.action in {"create_fake_main", "select_fake_main"}:
            path = "/projects/update-value"
            prepare = create_fake_settings if payload.action == "create_fake_main" else select_fake_settings
            request["alternate"] = prepare(project, payload.fake_main_path)
        elif payload.action in {"reserve", "reglue"}:
            domain = require_domain(state, payload.domain)
            request["reserve"] = domain
            if payload.action == "reserve":
                path = "/projects/update-value"
                request["reserveOption"] = domain
            else:
                if state["reserve"] != domain:
                    raise NetworkConflict("Сначала сохраните выбранный резервный домен.")
                if auto_run_id is not None:
                    _, check = remote.request("POST", "/projects/check-domain", {"domain": domain})
                    if not isinstance(check, dict) or check.get("reachable") is not True:
                        raise ValueError("Резервный домен не подтвердил доступность. Проверьте домен перед переклеем.")
                path = "/projects/update-reglue"
                request.update(trigger="webdev:settings", initiator=username)
        else:
            if not state["has_head"]:
                raise ValueError("У проекта отсутствует head; сохранение альтернейтов недоступно.")
            validate_markup(payload.alternate_markup)
            method, path = "PATCH", "/projects/update-head"
            request.update(alternateMarkup=payload.alternate_markup, enableAlternates=payload.enable_alternates)
        operation = models.NetworkOperation(id=str(payload.request_id), site_id=site.id, action=payload.action,
                                            initiator=username, request_payload={**request, **({"indexing_pending": True, "_indexing": {"canon": domain, "alternateMarkup": state["alternateMarkup"], "enableAlternates": state["enableAlternates"]}} if payload.action == "reglue" and auto_run_id is None else {})}, status="pending")
        db.add(operation)
        db.commit()  # Receipt exists even if the connection or process stops after sending.
        try:
            code, response = remote.request(method, path, request)
            operation.response_status = code
            if isinstance(response, dict) and (response.get("errors") or response.get("success") is False or response.get("error")):
                operation.status = "failed"
                operation.message = str(response.get("message") or response.get("errors") or response.get("error"))[:2000]
            elif payload.action in {"create_subdomains", "delete_domain"}:
                if not isinstance(response, dict) or not response.get("jobId"):
                    operation.status = "unknown"
                    operation.message = "Webdev не вернул номер задачи. Повторная отправка заблокирована; обновите сетку."
                else:
                    operation.request_payload = {**operation.request_payload, "job_id": str(response["jobId"])}
                    operation.message = (f"Задача удаления {response['jobId']} запущена. Ожидаем удаления домена из сетки."
                        if payload.action == "delete_domain" else f"Задача создания {response['jobId']} запущена. Ожидаем появления поддоменов в сетке.")
                    if response.get("skipped"):
                        operation.message += " Webdev пропустил часть доменов: " + str(response["skipped"])[:1000]
            else:
                operation.message = "Запрос отправлен. Ожидается подтверждение настроек проекта."
        except httpx.HTTPStatusError as exc:
            operation.response_status = exc.response.status_code
            operation.status = "failed" if 400 <= exc.response.status_code < 500 else "unknown"
            operation.message = f"Webdev вернул HTTP {exc.response.status_code}. Обновите сетку для проверки результата."
        except (httpx.HTTPError, ValueError):
            operation.status = "unknown"
            operation.message = "Ответ не получен или не распознан. Запрос мог выполниться; обновите сетку для проверки результата."
        db.commit()
        try:
            state = observe(db, site, remote.project())
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
    if site.cache_canon:
        known.add(domain_name(site.cache_canon))
    if domain not in known:
        raise ValueError("Домен отсутствует в сохранённой сетке и истории проекта.")
    if domain in (site.network_state or {}).get("amp_domains", []) or (site.domain_types or {}).get(domain) == "amp":
        raise ValueError("Тип AMP определяется настройками проекта и не меняется вручную.")
    site.domain_types = {**(site.domain_types or {}), domain: payload.domain_type}
    db.commit()
    return {"domain_types": site.domain_types, "domain_classification": classify_domains(site.cache_domains or [], site.domain_types, site.main_domain_history or [], site.cache_canon or "")}
