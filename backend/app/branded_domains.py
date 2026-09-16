"""Classify branded roots using cached data only. Never relabel a branded child."""
import re
from app.domain_classification import registrable_root
from app.network_state import domain_name
from app.site_brands import BRANDS, GENERAL, normalized


def brand_key(value):
    return re.sub(r"[^\w]", "", normalized(value))


def brand_aliases(extra_brands=()):
    result = {}
    for brand, aliases in BRANDS.items():
        for alias in [brand, *aliases]:
            key = brand_key(alias)
            if key:
                result[key] = brand
    for brand in extra_brands:
        if brand and brand != GENERAL:
            result.setdefault(brand_key(brand), brand)
    return result


def apply_brand_domain_types(site, *, aliases=None, overwrite_drops=False):
    aliases = aliases or brand_aliases([site.brand])
    types = dict(site.domain_types or {})
    changes = []
    for value in site.cache_domains or []:
        domain = domain_name(value)
        bare = domain.removeprefix("www.")
        root = registrable_root(bare)
        if not root or root != bare:
            continue
        # Never match text in a public suffix, or text in a branded subdomain.
        label = bare.split(".")[0]
        try:
            label = label.encode("ascii").decode("idna")
        except (UnicodeError, ValueError):
            pass
        key = brand_key(label)
        matches = [(len(alias), brand) for alias, brand in aliases.items() if alias and alias in key]
        if not matches:
            continue
        brand = max(matches)[1]
        old = types.get(domain)
        if old in {"newreg", "amp"} or old == "drop" and not overwrite_drops:
            continue
        types[domain] = "newreg"
        changes.append({"project": site.name, "domain": domain, "brand": brand, "before": old, "after": "newreg"})
    if changes:
        site.domain_types = types
    return changes


def backfill_branded_domains(db):
    from sqlalchemy import select
    from app.models import Site
    sites = db.scalars(select(Site).order_by(Site.id).with_for_update()).all()
    aliases = brand_aliases(site.brand for site in sites)
    changes = []
    scanned = 0
    for site in sites:
        scanned += len(site.cache_domains or [])
        changes.extend(apply_brand_domain_types(site, aliases=aliases, overwrite_drops=True))
    db.commit()
    replacements = [change for change in changes if change["before"] == "drop"]
    return {"projects": len(sites), "domains_scanned": scanned, "updated": len(changes),
            "newly_classified": len(changes) - len(replacements),
            "drops_replaced": len(replacements), "replacements": replacements}
