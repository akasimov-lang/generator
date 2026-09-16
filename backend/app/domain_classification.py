"""Domain roles derived from the cached network and persisted root types."""
from app.network_state import domain_name
import tldextract

# Use the packaged snapshot only: no DNS/HTTP requests or writable cache.
_extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, extra_suffixes=("test",))

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
