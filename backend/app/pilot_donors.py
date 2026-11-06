"""Explicit donor-only grants scoped to one saved plan; never enable Main moves."""
from app import models


def key(job_id):
    return 'pilot-donors:' + str(job_id)


def grants(db, job_id):
    job = db.get(models.BackgroundJob, job_id) if job_id else None
    if not job or job.kind not in {'auto_pilot_preview', 'mass_reglue_list'}:
        return {}
    row = db.get(models.AutoReglueConfig, key(job.id))
    allowed = job.payload.get('allowed')
    excluded = job.payload.get('excluded_site_ids', [])
    return {sid: grant for sid, grant in (row.value.get('sites', {}) if row else {}).items()
            if grant.get('approved') and sid not in excluded and (allowed is None or sid in allowed)}


def authorized(db, plan, site_id):
    approval = plan.get('donor_authorization') or {}
    return bool(site_id != plan.get('site_id') and site_id == plan.get('source_site_id')
                and approval.get('source_site_id') == site_id
                and site_id in grants(db, approval.get('plan_id')))


def stamp(db, plan):
    job_id = db.info.get('pilot_job_id')
    source = plan.get('source_site_id')
    grant = grants(db, job_id).get(source)
    if grant and source != plan['site_id']:
        plan['donor_authorization'] = {'plan_id': job_id, 'source_site_id': source,
                                       'approved_by': grant.get('actor'), 'approved_at': grant.get('at')}
    return plan
