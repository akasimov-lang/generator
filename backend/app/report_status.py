"""User-visible planning and execution states; planning never supplies an end-of-work date."""

def metadata(job, *, status=None, finished_at=None):
    planning = job.kind == 'auto_pilot_preview' or job.kind == 'maintenance_report' and bool(job.payload.get('planning_only'))
    status = status or job.status
    if planning:
        prepared = job.status == 'completed' if job.kind == 'auto_pilot_preview' else bool(job.payload.get('planning_finished_at') or job.payload.get('planning_updated_at'))
        blocked = any(r.get('planning_status') == 'blocked' for r in (getattr(job, 'result', None) or {}).get('entries', []))
        label = 'План требует обновления' if blocked else 'План готов' if prepared else 'Ошибка планирования' if status == 'failed' else 'Планирование'
        return {'planning_only':True,'display_status':label,'finished_at':None,
                'planning_finished_at':job.finished_at if job.kind == 'auto_pilot_preview' else job.payload.get('planning_finished_at')}
    if job.kind == 'maintenance_report':
        rows = (job.result or {}).get('entries', [])
        if rows and all(r.get('status') in {'completed','partial','failed','skipped'} for r in rows):
            status = 'partial' if any(r.get('status') in {'failed','partial'} for r in rows) else 'completed'
            if finished_at is None:
                ends = [r.get('finished_at') for r in rows if r.get('finished_at')]
                finished_at = max(ends) if len(ends) == len(rows) else None
        elif any(r.get('status') in {'pending','running','waiting','queued'} for r in rows):
            status = 'running'
    label = {'completed':'Выполнено','partial':'Выполнено частично','failed':'Ошибка выполнения','cancelled':'Остановлено','queued':'Выполняется','running':'Выполняется','waiting':'Ожидает подтверждения'}.get(status,status)
    return {'planning_only':False,'display_status':label,'finished_at':finished_at if status in {'completed','partial','failed','cancelled'} else None}
