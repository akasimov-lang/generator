"""Explicit reserve, canonical and alternate operations through Webdev's API."""
from contextlib import contextmanager
import hashlib
import json
from typing import Literal
from urllib.parse import quote
from uuid import UUID

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app import models
from app.core.config import get_settings
from app.network_state import alternate_links, domain_name, observe_network, state_revision, validate_markup
from app.project_cache import ProjectCacheError, project_server_url, refresh_project_server_id


class NetworkConflict(ValueError):
    pass


class DomainCheck(BaseModel):
    domain: str = Field(min_length=1, max_length=253)
    revision: str


class NetworkChange(BaseModel):
    request_id: UUID
    action: Literal["reserve", "reglue", "alternates"]
    revision: str = Field(min_length=1, max_length=64)
    domain: str = Field(default="", max_length=253)
    alternate_markup: str = Field(default="", max_length=100000)
    enable_alternates: bool = True


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

    def request(self, method, path, payload):
        # No retries for mutations: a timeout does not mean the operation failed.
        response = self.client.request(method, project_server_url(self.site, path), json=payload)
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
    site.domains_count = len(state["domains"])
    for operation in db.scalars(select(models.NetworkOperation).where(
        models.NetworkOperation.site_id == site.id,
        models.NetworkOperation.status.in_(["pending", "unknown"]),
    )):
        if operation_matches(operation, state):
            operation.status = "confirmed"
            operation.message = "Изменение подтверждено чтением настроек проекта."
    db.commit()
    return state


def result(db, site, state):
    operations = db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.site_id == site.id)
                           .order_by(models.NetworkOperation.created_at.desc()).limit(20)).all()
    return {
        **state, "revision": state_revision(state), "main_history": site.main_domain_history or [],
        "x_default_history": site.x_default_history or [],
        "alternate_history": site.alternate_domain_history or [],
        "alternates": alternate_links(state["alternateMarkup"]),
        "operations": [{"id": op.id, "action": op.action, "status": op.status, "message": op.message,
                        "initiator": op.initiator, "created_at": op.created_at,
                        "domain": op.request_payload.get("reserve"), "response_status": op.response_status}
                       for op in operations],
    }


def require_revision(state, revision):
    if state_revision(state) != revision:
        raise NetworkConflict("Настройки сетки изменились. Обновите данные и проверьте изменения перед сохранением.")


def require_domain(state, value):
    domain = domain_name(value)
    if not domain or domain not in state["domains"]:
        raise ValueError("Выберите резервный домен из текущей сетки.")
    if domain == state["canon"]:
        raise ValueError("Текущий Main нельзя выбрать резервом.")
    return domain


def read_network(db, site):
    with network_lock(db, site.id), Remote(db, site) as remote:
        state = observe(db, site, remote.project())
        return result(db, site, state)


def check_domain(db, site, payload):
    with network_lock(db, site.id), Remote(db, site) as remote:
        state = observe(db, site, remote.project())
        require_revision(state, payload.revision)
        domain = require_domain(state, payload.domain)
        _, response = remote.request("POST", "/projects/check-domain", {"domain": domain})
        if not isinstance(response, dict) or not isinstance(response.get("reachable"), bool):
            raise ProjectCacheError("Webdev не вернул результат проверки домена.")
        return {"domain": domain, "reachable": response["reachable"], "reason": str(response.get("reason") or "")}


def change_network(db, site, payload, username):
    with network_lock(db, site.id), Remote(db, site) as remote:
        existing = db.get(models.NetworkOperation, str(payload.request_id))
        if existing and (existing.site_id != site.id or existing.action != payload.action):
            raise NetworkConflict("Идентификатор запроса уже используется другой операцией.")
        state = observe(db, site, remote.project())
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
        if payload.action in {"reserve", "reglue"}:
            domain = require_domain(state, payload.domain)
            request["reserve"] = domain
            if payload.action == "reserve":
                path = "/projects/update-value"
                request["reserveOption"] = domain
            else:
                if state["reserve"] != domain:
                    raise NetworkConflict("Сначала сохраните выбранный резервный домен.")
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
                                            initiator=username, request_payload=request, status="pending")
        db.add(operation)
        db.commit()  # Receipt exists even if the connection or process stops after sending.
        try:
            code, response = remote.request(method, path, request)
            operation.response_status = code
            if isinstance(response, dict) and (response.get("errors") or response.get("success") is False or response.get("error")):
                operation.status = "failed"
                operation.message = str(response.get("message") or response.get("errors") or response.get("error"))[:2000]
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
