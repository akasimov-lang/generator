"""Observe domain history without modifying the remote project."""
import hashlib
import json
import re
from html.parser import HTMLParser
from app.fake_main import fake_paths
from urllib.parse import urlsplit


def domain_name(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    value = (value or "").strip()
    if not value or value == "none" or "{{" in value:
        return ""
    try:
        parsed = urlsplit(value if "://" in value else "//" + value)
        return (parsed.hostname or "").rstrip(".").encode("idna").decode().lower()
    except (ValueError, UnicodeError):
        return ""


class AlternateParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.invalid = False

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag != "link" or "alternate" not in (data.get("rel") or "").lower().split():
            self.invalid = True
            return
        lang = (data.get("hreflang") or "").strip()
        href = (data.get("href") or "").strip()
        if not lang or not re.fullmatch(r"[A-Za-z0-9-]+", lang) or not href.startswith(("https://", "http://")):
            self.invalid = True
        if any(key.lower().startswith("on") for key in data):
            self.invalid = True
        self.links.append({"hreflang": lang, "href": href, "domain": domain_name(href)})

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        if data.strip():
            self.invalid = True

    def handle_endtag(self, tag):
        self.invalid = True


def alternate_links(markup: str) -> list[dict]:
    parser = AlternateParser()
    parser.feed(markup)
    return parser.links


def validate_markup(markup: str) -> None:
    parser = AlternateParser()
    parser.feed(markup)
    parser.close()
    if parser.invalid:
        raise ValueError('Разметка должна содержать ссылки <link rel="alternate" hreflang="…" href="https://…" />.')
    langs = [link["hreflang"].lower() for link in parser.links]
    if len(langs) != len(set(langs)):
        raise ValueError("Для каждого hreflang, включая x-default, укажите одну ссылку.")
    for link in parser.links:
        # Preserve the known Webdev placeholders without treating them as domain history.
        href = link["href"].replace("{{settings.canon}}", "example.com").replace("{{reqPath}}", "/")
        try:
            url = urlsplit(href)
            if not url.hostname or url.username or url.password or any(char.isspace() for char in href) or "{{" in href:
                raise ValueError
            url.port
        except ValueError:
            raise ValueError("Укажите корректный полный адрес в каждой ссылке альтернейтов.") from None


def project_network_state(project: dict) -> dict:
    settings = project.get("settings") if isinstance(project.get("settings"), dict) else {}
    head = project.get("head") if isinstance(project.get("head"), dict) else {}
    domains = []
    for item in settings.get("domains") if isinstance(settings.get("domains"), list) else []:
        if isinstance(item, dict):
            item = item.get("domain") or item.get("url") or item.get("name")
        if domain := domain_name(item):
            domains.append(domain)
    amp_values = settings.get("ampDomains", settings.get("ampList", []))
    amp_domains = []
    for item in amp_values if isinstance(amp_values, list) else []:
        if isinstance(item, dict):
            item = item.get("domain") or item.get("name") or item.get("url")
        if domain := domain_name(item):
            amp_domains.append(domain)
    amp = domain_name(settings.get("amp"))
    prev_amp = domain_name(settings.get("prevAmp"))
    alternate = settings.get("alternate") if isinstance(settings.get("alternate"), dict) else {}
    return {
        "fake_main_settings": alternate,
        "fake_main_paths": fake_paths(alternate),
        "fake_main_current": alternate.get("currentFakeMain") or "",
        "fake_main_enabled": bool(alternate.get("enableDynamicRoutes")),
        "amp": amp, "prev_amp": prev_amp,
        "amp_domains": list(dict.fromkeys([*amp_domains, *filter(None, [amp, prev_amp])])),
        "canon": domain_name(settings.get("canon")),
        "prev": domain_name(settings.get("prev")),
        "reserve": domain_name(settings.get("reserveOption", settings.get("reserve"))),
        "domains": list(dict.fromkeys(domains)),
        "alternateMarkup": head.get("alternateMarkup") if isinstance(head.get("alternateMarkup"), str) else "",
        "enableAlternates": bool(head.get("enableAlternates")),
        "has_head": isinstance(project.get("head"), dict),
    }


def observe_network(site, project: dict) -> dict:
    state = project_network_state(project)
    settings = project.get("settings") if isinstance(project.get("settings"), dict) else {}
    if not any(key in settings for key in ("amp", "prevAmp", "ampDomains", "ampList")):
        for key in ("amp", "prev_amp", "amp_domains"):
            state[key] = (site.network_state or {}).get(key, state[key])
    if "alternate" not in settings:
        for key in ("fake_main_settings", "fake_main_paths", "fake_main_current", "fake_main_enabled"):
            state[key] = (site.network_state or {}).get(key, state[key])
    site.main_domain_history = list(dict.fromkeys(filter(None, [
        *(site.main_domain_history or []), domain_name(site.cache_canon), state["prev"], state["canon"],
    ])))
    # Partial cache events must not clear head observations.
    if not state["has_head"]:
        for key in ("alternateMarkup", "enableAlternates", "has_head"):
            state[key] = (site.network_state or {}).get(key, state[key])
    links = alternate_links(state["alternateMarkup"].replace("{{settings.canon}}", state["canon"]).replace("{{reqPath}}", "/"))
    site.alternate_domain_history = list(dict.fromkeys([
        *(site.alternate_domain_history or []), *(link["domain"] for link in links if link["domain"]),
    ]))
    site.x_default_history = list(dict.fromkeys([
        *(site.x_default_history or []),
        *(link["domain"] for link in links if link["hreflang"].lower() == "x-default" and link["domain"]),
    ]))
    site.domain_types = {**(site.domain_types or {}), **{domain: "amp" for domain in state["amp_domains"]}}
    site.network_state = state
    return state


def state_revision(state: dict) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
