"""Route by the work performed, including durable jobs created before deployment."""
from app import models

SHORT_ACTIONS = {'meta_headings', 'headings', 'full_title_h1', 'full_title_headings', 'emoji', 'trim_50', 'trim_99'}


def queue_for(db, job):
    if job.kind == 'pilot_row_replan':
        return 'short_generation' if (job.result or {}).get('phase') == 'headings' else 'planning'
    if job.kind == 'auto_pilot_preview':
        return 'planning'
    if job.kind == 'pilot_text':
        return 'short_generation' if job.payload.get('field') == 'title_h1' else 'pilot_texts'
    if job.kind == 'project_page_ai':
        draft = db.get(models.ProjectPageDraft, job.payload.get('draft_id'))
        return 'short_generation' if draft and draft.action in SHORT_ACTIONS else 'generation'
    if job.kind == 'maintenance_report' and job.payload.get('planning_only'):
        return 'planning'
    return {
        'fibery_reglue': 'maintenance',
        'menu_generation': 'short_generation', 'generation_retry': 'generation',
        'maintenance_report': 'automation', 'mass_reglue_list': 'automation',
        'pilot_internal_pages': 'short_generation', 'template_knowledge': 'maintenance',
        'project_page_save': 'publication', 'publication': 'publication', 'page_autolink': 'publication', 'pilot_content_publication': 'publication',
        'transfer_report_check': 'automation', 'site_template': 'generation',
        'auto_lb': 'generation', 'article_image': 'short_generation',
    }.get(job.kind, 'cache_sync')
