"""DNS reachability is advisory for mass runs verified against fresh Webdev data."""
from datetime import datetime, timezone
from urllib.parse import urlsplit
import httpx


def is_dns_error(error):
    text = str(error).lower()
    return any(marker in text for marker in ('enotfound', 'eai_again', 'name or service not known', 'temporary failure in name resolution', 'nodename nor servname', 'getaddrinfo failed', 'dns failed', 'ошибка dns'))


def allowed(run):
    return bool(run and run.plan.get('list_launch_id') and run.plan.get('execution_mode') == 'cross_network')


def note(db, run, domain, message, *, kind=None):
    if not allowed(run) and kind != 'availability':
        return
    warnings = list(run.plan.get('dns_warnings') or [])
    entry = {'domain': domain, 'message': str(message)[:1000], 'checked_at': datetime.now(timezone.utc).isoformat(), **({'kind':kind} if kind else {})}
    warnings = [w for w in warnings if (w.get('domain'), w.get('kind')) != (domain, kind)]
    run.plan = {**run.plan, 'dns_warnings': [*warnings, entry]}
    db.commit()


def verify_pages(db, site, run, state):
    from app.auto_reglue import verify_pages as verify
    if allowed(run):
        # Network settings are verified by the final reconciliation. Public DNS,
        # TLS and HTTP are checked separately after all writes have finished.
        return
    verify(run.plan['required_page_urls'])


def audit_pages(db, run):
    if not run.plan.get('new_main'): return []
    from app.auto_reglue import verify_pages as verify
    results = []
    urls = list(dict.fromkeys(['https://' + run.plan['new_main'] + '/', *run.plan.get('required_page_urls', [])]))
    for url in urls:
        try:
            verify([url])
            results.append({'url': url, 'ok': True})
            archive_notes(db, run, lambda item: item.get('domain') == url and (
                item.get('kind') == 'availability' or 'Доступность сайта:' in item.get('message', '')))
        except (httpx.HTTPError, ValueError) as error:
            results.append({'url': url, 'ok': False, 'message': str(error)[:1000]})
            note(db, run, url, 'Доступность сайта: ' + str(error), kind='availability')
    run.plan = {**run.plan, 'availability_checked_at': datetime.now(timezone.utc).isoformat()}
    db.commit()
    return results


def archive_notes(db, run, predicate):
    notes = run.plan.get('dns_warnings') or []
    resolved = [item for item in notes if predicate(item)]
    if not resolved: return
    at = datetime.now(timezone.utc).isoformat()
    run.plan = {**run.plan, 'dns_warnings': [item for item in notes if item not in resolved],
        'archived_notes': [*run.plan.get('archived_notes', []), *[
            {**item, 'archived_at': at, 'archived_by': 'Автопроверка', 'resolution': 'Подтверждено свежей проверкой'} for item in resolved]]}
    db.commit()


def archive_confirmed_notes(db, run):
    # A warning about an ambiguous write is resolved by fresh matching settings.
    # DNS/HTTP warnings require their own successful public check; backups are unrelated.
    archive_notes(db, run, lambda item: item.get('kind') != 'availability' and any(
        text in item.get('message', '') for text in ('Настройки подтверждены Webdev.', 'Настройки Webdev подтверждены', 'Настройки подтверждены чтением Webdev.')))
