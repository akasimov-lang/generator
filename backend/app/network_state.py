"""Observe domain history without modifying the remote project."""
import hashlib
import json
import re
from datetime import datetime, timezone
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
    data = project.get("data") if isinstance(project.get("data"), dict) else {}
    content_pages = data.get("pages") if isinstance(data.get("pages"), list) else []
    alternate = settings.get("alternate") if isinstance(settings.get("alternate"), dict) else {}
    return {
        "content_page_paths": ["/" + str(page.get("slug") or "").strip("/") + "/" for page in content_pages if isinstance(page, dict)],
        "fake_main_settings": alternate,
        "fake_main_paths": fake_paths(alternate),
        "fake_main_current": alternate.get("currentFakeMain") or "",
        "fake_main_enabled": bool(alternate.get("enableDynamicRoutes")),
        "amp": amp, "prev_amp": prev_amp,
        "amp_domains": list(dict.fromkeys([*amp_domains, *filter(None, [amp, prev_amp])])),
        "canon": domain_name(settings.get("canon")),
        "prev": domain_name(settings.get("prev")),
        "reserve": domain_name(settings.get("reserveOption") or settings.get("reserve")),
        "reserved_domains": list(dict.fromkeys(filter(None, [domain_name(settings.get("reserveOption")), domain_name(settings.get("reserve"))]))),
        "domains": list(dict.fromkeys(domains)),
        "domain_redirects": settings.get("redirects") if isinstance(settings.get("redirects"), list) else [],
        "has_domain_redirects": isinstance(settings.get("redirects"), list),
        "page_redirects": settings.get("pageRedirects") if isinstance(settings.get("pageRedirects"), list) else [],
        "has_page_redirects": isinstance(settings.get("pageRedirects"), list),
        "alternateMarkup": head.get("alternateMarkup") if isinstance(head.get("alternateMarkup"), str) else "",
        "enableAlternates": bool(head.get("enableAlternates")),
        "enableCanonical": bool(head.get("enableCanonical")),
        "canonicalDefaultMarkup": head.get("canonicalDefaultMarkup") or "",
        "canonicalFakeMainMarkup": head.get("canonicalFakeMainMarkup") or "",
        "has_head": isinstance(project.get("head"), dict),
    }


def observe_network(site, project: dict, *, db=None) -> dict:
    state = project_network_state(project)
    from app.reglue_history import observe_main
    observe_main(site, site.cache_canon, state['canon'])
    settings = project.get("settings") if isinstance(project.get("settings"), dict) else {}
    if not any(key in settings for key in ("reserveOption", "reserve")):
        for key in ("reserve", "reserved_domains"):
            state[key] = (site.network_state or {}).get(key, state[key])
    if not isinstance(settings.get("domains"), list):
        state["domains"] = (site.network_state or {}).get("domains", [])
    if "redirects" not in settings:
        for key in ("domain_redirects", "has_domain_redirects"):
            state[key] = (site.network_state or {}).get(key, state[key])
    if "pageRedirects" not in settings:
        for key in ("page_redirects", "has_page_redirects"):
            state[key] = (site.network_state or {}).get(key, state[key])
    if not any(key in settings for key in ("amp", "prevAmp", "ampDomains", "ampList")):
        for key in ("amp", "prev_amp", "amp_domains"):
            state[key] = (site.network_state or {}).get(key, state[key])
    if "data" not in project:
        state["content_page_paths"] = (site.network_state or {}).get("content_page_paths", [])
    previous_alternate = (site.network_state or {}).get("fake_main_settings", {})
    alternate = settings.get("alternate")
    if not isinstance(alternate, dict): alternate = {}
    for remote_key, state_key in (("currentFakeMain", "fake_main_current"), ("enableDynamicRoutes", "fake_main_enabled"), ("fakeMain", "fake_main_paths")):
        if remote_key not in alternate:
            state[state_key] = (site.network_state or {}).get(state_key, state[state_key])
    state["fake_main_settings"] = {**previous_alternate, **alternate}
    if "canon" not in settings:
        state["canon"] = (site.network_state or {}).get("canon", state["canon"])
    site.main_domain_history = list(dict.fromkeys(filter(None, [
        *(site.main_domain_history or []), domain_name(site.cache_canon), state["prev"], state["canon"],
    ])))
    # Partial cache events must not clear head observations.
    if not state["has_head"]:
        for key in ("alternateMarkup", "enableAlternates", "has_head", "enableCanonical", "canonicalDefaultMarkup", "canonicalFakeMainMarkup"):
            state[key] = (site.network_state or {}).get(key, state[key])
    state['fake_main_history'] = list(dict.fromkeys([
        *(site.network_state or {}).get('fake_main_history', []),
        *state['fake_main_paths'], *filter(None, [state['fake_main_current']]),
    ]))
    links = alternate_links(state["alternateMarkup"].replace("{{settings.canon}}", state["canon"]).replace("{{reqPath}}", "/"))
    site.alternate_domain_history = list(dict.fromkeys([
        *(site.alternate_domain_history or []), *(link["domain"] for link in links if link["domain"]),
    ]))
    site.x_default_history = list(dict.fromkeys([
        *(site.x_default_history or []),
        *(link["domain"] for link in links if link["hreflang"].lower() == "x-default" and link["domain"]),
    ]))
    site.domain_types = {**(site.domain_types or {}), **{domain: "amp" for domain in state["amp_domains"]}}
    previous = site.network_state or {}
    state["protected_main_domains"] = list(dict.fromkeys([
        *previous.get("protected_main_domains", []),
        *([state["canon"]] if getattr(site, "project_status", None) == "mass_actions" and state["canon"] else []),
    ]))
    track_domain_membership(previous, state, settings)
    state["history_overrides"] = previous.get("history_overrides", {})
    state["history_edits"] = previous.get("history_edits", [])
    apply_history_overrides(site, state["history_overrides"])
    mark_project_identity(site, state["domains"])
    from app.network_cache_history import track
    track(site, previous, state, settings, db)
    site.network_state = state
    return state


def track_domain_membership(previous, state, settings):
    """Keep observed membership periods; unknown historical dates remain unknown."""
    added_at = dict(previous.get("domain_added_at") or {})
    removed_at = dict(previous.get("domain_removed_at") or {})
    addition_history = list(previous.get("domain_addition_history") or [])
    periods = [dict(period) for period in previous.get("domain_membership_history") or []]
    known = set(previous.get("domains") or []) | set(previous.get("amp_domains") or [])
    current = set(state["domains"]) | set(state["amp_domains"])
    # Existing members establish a baseline, without assigning today's date to old domains.
    for domain in sorted(known if "domains" in previous else current):
        if not any(period.get("domain") == domain and period.get("removed_at") is None for period in periods):
            periods.append({"domain": domain, "added_at": added_at.get(domain), "removed_at": None})
    authoritative = isinstance(settings.get("domains"), list) or any(
        key in settings for key in ("amp", "prevAmp", "ampDomains", "ampList"))
    if "domains" in previous and authoritative:
        observed_at = datetime.now(timezone.utc).isoformat()
        for domain in sorted(known - current):
            removed_at[domain] = observed_at
            for period in reversed(periods):
                if period.get("domain") == domain and period.get("removed_at") is None:
                    period["removed_at"] = observed_at
                    break
        for domain in sorted(current - known):
            if added_at.get(domain) and not any(event.get("domain") == domain and event.get("added_at") == added_at[domain] for event in addition_history):
                addition_history.append({"domain": domain, "added_at": added_at[domain]})
            added_at[domain] = observed_at
            addition_history.append({"domain": domain, "added_at": observed_at})
            periods.append({"domain": domain, "added_at": observed_at, "removed_at": None})
    state["domain_added_at"] = added_at
    state["domain_removed_at"] = removed_at
    state["domain_addition_history"] = addition_history
    state["domain_membership_history"] = periods


def state_revision(state: dict) -> str:
    return hashlib.sha256(json.dumps({k:v for k,v in state.items() if k not in {"cache_change_history", "cache_change_baseline"}}, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


HISTORY_FIELDS = {
    "main": "main_domain_history",
    "alternate": "alternate_domain_history",
    "x_default": "x_default_history",
}


def is_project_identity(site, domain):
    """Webdev's immutable project name, allowing the equivalent www spelling."""
    name = domain_name(site.name).removeprefix("www.")
    return bool(name) and domain_name(domain).removeprefix("www.") == name


def mark_project_identity(site, domains=None):
    """Local protection flags; never change the remote Main or head markup."""
    members = domains if domains is not None else [
        *(site.network_state or {}).get("domains", []), *(site.cache_domains or []),
    ]
    identity = [domain_name(domain) for domain in members if is_project_identity(site, domain)]
    for attribute in HISTORY_FIELDS.values():
        setattr(site, attribute, list(dict.fromkeys([*(getattr(site, attribute) or []), *identity])))


def apply_history_overrides(site, overrides):
    """Explicit corrections, including false, survive remote observations."""
    for field, attribute in HISTORY_FIELDS.items():
        values = list(getattr(site, attribute) or [])
        for domain, flags in overrides.items():
            if field not in flags:
                continue
            values = [value for value in values if value != domain]
            if flags[field]:
                values.append(domain)
        setattr(site, attribute, values)
