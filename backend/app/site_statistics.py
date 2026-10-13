"""Read-only statistics of saved mass-action networks."""
import re
from app.domain_classification import classify_domains
from app.network_state import domain_name


def network_domain_counts(site):
    domains = sorted({domain_name(d) for d in (site.cache_domains or [])} - {''})
    types = {domain_name(k): v for k, v in (site.domain_types or {}).items()}
    roles = classify_domains(domains, types)
    counts = dict(drop=0, newreg=0, subdomains=0, amp=0, unknown=0)
    for domain in domains:
        root = domain.removeprefix('www.')
        value = types.get(domain) or types.get(root) or types.get('www.' + root)
        if value == 'amp':
            counts['amp'] += 1
        elif roles[domain]['is_subdomain']:
            counts['subdomains'] += 1
        elif value in ('drop', 'newreg'):
            counts[value] += 1
        else:
            counts['unknown'] += 1
    return dict(domains=len(domains), **counts)


def mass_action_statistics(sites, scope="mass_actions"):
    statuses = {scope} if scope in {"geo_ru", "geo_kz", "hands_only"} else {"mass_actions"}
    rows = []
    seen = set()
    for site in sites:
        if site.hidden_from_projects or site.project_status not in statuses or site.id in seen:
            continue
        seen.add(site.id)
        geo = (site.cache_geo or '').strip().upper()
        parts = re.split('[-_]', geo)
        geo = next((p for p in reversed(parts) if re.fullmatch('[A-Z]{2}', p)), geo) or 'UNKNOWN'
        kind = site.site_type or ('monobrand' if (site.brand or '').strip() and site.brand.strip().casefold() != 'общие ключи' else 'general')
        counts = network_domain_counts(site)
        rows.append(dict(id=site.id, name=site.name, project_name=site.fibery_name or site.name,
                         geo=geo, site_type=kind, brand=(site.brand or "").strip() if kind == "monobrand" else "Общие ключи", **counts,
                         cache_synced_at=site.cache_synced_at.isoformat() if site.cache_synced_at else None))
    return {'projects': rows}
