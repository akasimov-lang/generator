"""Domain roles derived from the cached network and persisted root types."""
from app.network_state import domain_name
import tldextract

# Use the packaged snapshot only: no DNS/HTTP requests or writable cache.
_extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, extra_suffixes=("test", "in.com", "it.com", "co.com"))

def registrable_root(domain):
    parsed = _extract(domain)
    return f"{parsed.domain}.{parsed.suffix}" if parsed.domain and parsed.suffix else None


def classify_domains(domains, domain_types, main_history=(), canon=""):
    names = list(dict.fromkeys(domain_name(d) for d in domains if domain_name(d)))
    bare = {d: d.removeprefix("www.") for d in names}
    used = {domain_name(d).removeprefix("www.") for d in [*main_history, canon] if d}
    result = {}
    for domain in names:
        parents = [p for p in names if bare[domain] != bare[p] and bare[domain].endswith("." + bare[p])]
        # Use the network root, not an intermediate nested subdomain.
        parent = min(parents, key=lambda p: (bare[p].count("."), p.startswith("www."))) if parents else None
        root = registrable_root(bare[domain])
        if not parent and root and root != bare[domain]:
            parent = root
        kind = (domain_types.get(parent) or domain_types.get(parent.removeprefix("www."))) if parent else None
        result[domain] = {
            "is_subdomain": parent is not None,
            "parent_domain": parent,
            "parent_type": kind if kind in {"drop", "newreg"} else None,
            "unused_as_main": bare[domain] not in used,
        }
    return result


NEWREG_ZONES = ("site", "fm", "top", "fun", "app", "ink", "in.com", "it.com", "co.uk", "co.com", "xyz")


def default_domain_type(domain):
    name = domain_name(domain).removeprefix("www.")
    return "newreg" if any(name.endswith("." + zone) for zone in NEWREG_ZONES) else "drop"


def apply_default_domain_types(site):
    """Persist defaults for untyped roots, including parents absent from the network."""
    types = dict(site.domain_types or {})
    roles = classify_domains(site.cache_domains or [], types)
    changes = []
    for domain, role in roles.items():
        target = role["parent_domain"] if role["is_subdomain"] else domain
        bare = target.removeprefix("www.")
        aliases = (target, bare, "www." + bare)
        existing = next((types[key] for key in aliases if types.get(key) in {"drop", "newreg"}), None)
        if types.get(target) in {"drop", "newreg"}:
            continue
        kind = existing or default_domain_type(target)
        types[target] = kind
        changes.append({"domain": target, "type": kind})
    if changes:
        site.domain_types = types
    return changes


def backfill_default_domain_types(db):
    from sqlalchemy import select
    from app.models import Site
    counts = {"projects": 0, "drop": 0, "newreg": 0}
    for site in db.scalars(select(Site).order_by(Site.id).with_for_update()):
        changes = apply_default_domain_types(site)
        counts["projects"] += bool(changes)
        for change in changes:
            counts[change["type"]] += 1
    db.commit()
    return counts
