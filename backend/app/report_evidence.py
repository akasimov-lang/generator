"""Keep dated current observations separate from immutable operation evidence."""
from copy import deepcopy
from datetime import datetime, timezone
from sqlalchemy import select
from app import models

PREFIX = 'report-observation:'


def capture(db, site, project, *, source='cache', at=None):
    from app.network_state import project_network_state
    from app.maintenance_reports import page_values
    from app.homepage_headings import extract
    state = project_network_state(project)
    data = project.get('data') if isinstance(project.get('data'), dict) else {}
    pages = data.get('pages') if isinstance(data.get('pages'), list) else []
    home = next((p for p in pages if isinstance(p, dict) and str(p.get('slug') or '').strip('/') == ''), None)
    values = page_values(home) if home else {}
    if home:
        headings = extract(project)
        if headings.get('h1_status') == 'found':
            values['h1'] = '\n'.join(h['text'] for h in headings['headings'])
    settings = project.get('settings') if isinstance(project.get('settings'), dict) else {}
    if 'canon' in settings:
        values['main'] = state['canon']
    if isinstance(project.get('head'), dict):
        values.update(alternates=state['alternateMarkup'], canonical=state['canonicalFakeMainMarkup'] or state['canonicalDefaultMarkup'])
    if isinstance(settings.get('alternate'), dict):
        values['fake_path'] = state['fake_main_current']
    if site.id is None:
        db.flush()
    key = PREFIX + site.id
    record = db.get(models.AutoReglueConfig, key)
    if record is None:
        record = models.AutoReglueConfig(key=key, value={}); db.add(record)
    record.value = {'values':{**(record.value or {}).get('values', {}), **values}, 'source':source, 'observed_at':(at or datetime.now(timezone.utc)).isoformat()}
    return record.value


def observations(db, ids):
    return {r.key[len(PREFIX):]:deepcopy(r.value) for r in db.scalars(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key.in_([PREFIX + sid for sid in ids])))}


def enrich(db, entries):
    current = observations(db, [r['site_id'] for r in entries])
    ids = [r['run_id'] for r in entries if r.get('run_id')]
    runs = {r.id:r for r in db.scalars(select(models.AutoReglueRun).where(models.AutoReglueRun.id.in_(ids)))} if ids else {}
    for row in entries:
        row['current_observation'] = current.get(row['site_id'])
        state = row.get('source_state') or {}
        saved = {key:state[src] for key,src in [('main','canon'),('alternates','alternateMarkup'),('fake_path','fake_main_current')] if src in state}
        canonical = state.get('canonicalFakeMainMarkup') or state.get('canonicalDefaultMarkup')
        if canonical is not None:
            saved['canonical'] = canonical
        row['before'] = {**saved, **row.get('before', {})}
        run = runs.get(row.get('run_id'))
        if not run or run.site_id != row['site_id']:
            continue
        plan = run.plan
        before = {k:v for k,v in {'main':plan.get('old_main'), 'alternates':(plan.get('alternates_before') or {}).get('markup')}.items() if v is not None}
        row['before'] = {**before, **row.get('before', {})}
        applied = plan.get('applied_result') or {}
        if applied.get('confirmed_at'):
            after = {k:applied[src] for k,src in [('main','new_main'),('alternates','alternateMarkup'),('canonical','canonicalFakeMainResolved'),('fake_path','fake_main_path')] if applied.get(src) is not None}
            row['after'] = {**row.get('after', {}), **after}
            row['network_confirmed_at'] = applied['confirmed_at']
    return entries
