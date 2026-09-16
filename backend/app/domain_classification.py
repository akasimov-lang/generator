"""Domain roles derived from the cached network and persisted root types."""
from app.network_state import domain_name


def classify_domains(domains, domain_types, main_history=(), canon=""):
    names = list(dict.fromkeys(domain_name(d) for d in domains if domain_name(d)))
    bare = {d: d.removeprefix("www.") for d in names}
    used = {domain_name(d).removeprefix("www.") for d in [*main_history, canon] if d}
    result = {}
    for domain in names:
        parents = [p for p in names if bare[domain] != bare[p] and bare[domain].endswith("." + bare[p])]
        # Use the network root, not an intermediate nested subdomain.
        parent = min(parents, key=lambda p: (bare[p].count("."), p.startswith("www."))) if parents else None
        kind = (domain_types.get(parent) or domain_types.get(bare[parent])) if parent else None
        result[domain] = {
            "is_subdomain": parent is not None,
            "parent_domain": parent,
            "parent_type": kind if kind in {"drop", "newreg"} else None,
            "unused_as_main": bare[domain] not in used,
        }
    return result
