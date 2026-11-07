"""Hide a report from the list while preserving work and evidence behind its URL."""
from datetime import datetime, timezone
from sqlalchemy import select
from app import models
from app.project_network import network_lock

PREFIX = 'pilot-report-hidden:'


def hidden_ids(db, username):
    return {row.key[len(PREFIX):] for row in db.scalars(select(models.AutoReglueConfig)
            .where(models.AutoReglueConfig.key.startswith(PREFIX)))
            if row.value.get('actor') == username}


def hide(db, report_id, user):
    from app import auto_pilot, maintenance_reports, mass_reglue_launch
    report_id = str(report_id)
    with network_lock(db, PREFIX + report_id):
        job = db.get(models.BackgroundJob, report_id)
        if job and job.kind == maintenance_reports.KIND:
            job = maintenance_reports.get(db, report_id, user)
        else:
            job = auto_pilot.get(db, report_id, user)
        if job.kind == mass_reglue_launch.PREVIEW_KIND:
            raise ValueError('Для черновика используйте удаление плана.')
        key = PREFIX + report_id
        if not db.get(models.AutoReglueConfig, key):
            db.add(models.AutoReglueConfig(key=key, value={
                'actor': user['username'], 'hidden_at': datetime.now(timezone.utc).isoformat()}))
            db.commit()
        return {'id': report_id, 'deleted': True}
