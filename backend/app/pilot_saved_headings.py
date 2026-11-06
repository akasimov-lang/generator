"""Keep project headings across plan rebuilds; row refresh is the explicit reset."""
from copy import deepcopy
from app import models

CACHE = 'saved_project_headings'


def capture(db, job, result):
    from app.pilot_text_jobs import generation, identity
    saved = deepcopy(result.get(CACHE, {}))
    for group in result.get('groups', []):
        for plan in group.get('plans', []):
            candidate = deepcopy(plan)
            # A worker may have finished just before the planner collected it.
            if not candidate.get('title_h1_preview') and candidate.get('rewrite_title_h1'):
                child = db.get(models.BackgroundJob, identity(job, plan, 'title_h1'))
                if child and child.status == 'completed' and not child.error:
                    candidate['title_h1_preview'] = (child.result or {}).get('preview')
            if candidate.get('title_h1_preview') and not candidate.get('title_h1_error'):
                saved[plan['site_id']] = {
                    'generation_id': generation(job),
                    **{key: deepcopy(candidate[key]) for key in
                       ('title_h1_preview', 'title_rewrite_mode', 'short_h1', 'language') if key in candidate}}
            elif candidate.get('title_h1_error') and not candidate.get('title_h1_reused'):
                # A failed explicit row refresh must not revive an older version.
                saved.pop(plan['site_id'], None)
    return saved


def restore(db, result, plan):
    saved = result.get(CACHE, {}).get(plan['site_id'])
    if not saved or not plan.get('rewrite_title_h1'):
        return
    preview = saved.get('title_h1_preview') or {}
    if not preview:
        return
    for key in ('title_h1_preview', 'title_rewrite_mode', 'short_h1'):
        if key in saved:
            plan[key] = deepcopy(saved[key])
        else:
            plan.pop(key, None)
    plan['title_h1_reused'] = {'generation_id': saved['generation_id'], 'draft_id': preview.get('draft_id')}
    plan.pop('title_h1_error', None)
    draft = db.get(models.ProjectPageDraft, preview['draft_id']) if preview.get('draft_id') else None
    if (not draft or draft.site_id != plan['site_id'] or draft.status != 'ready'
            or saved.get('language') != plan.get('language')):
        plan['title_h1_error'] = 'Сохранённые метаданные требуют проверки. Нажмите «Обновить» у проекта для новой схемы и метаданных.'


def reused(plan):
    saved = plan.get('title_h1_reused') or {}
    return bool(saved.get('draft_id') and saved['draft_id'] == (plan.get('title_h1_preview') or {}).get('draft_id'))
