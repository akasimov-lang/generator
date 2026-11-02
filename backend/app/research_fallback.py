"""An empty SERP must not prevent writing from existing project knowledge."""
from app import models, reference_context


def saved_brief(db, item):
    task = db.get(models.GenerationTask, item.task_id)
    site_id = item.site_id or (task.site_id if task else None)
    site = db.get(models.Site, site_id) if site_id else None
    context = reference_context.collect(db, site, geo=task.geo if task else None)
    warning = ('Новые страницы конкурентов не найдены или недоступны. '
               'Используем сохранённую базу знаний и материалы проекта.')
    item.competitor_brief = {'research_status': 'saved_context', 'warning': warning,
        'reference_context': reference_context.audit(context), 'competitor_summary': [],
        'competitor_urls': [], 'content_gaps': [], 'topics_to_cover': []}
    item.competitor_brief_text = warning + reference_context.prompt(context)
    item.competitor_research_status = 'brief_ready'
    item.competitor_research_progress = 100
    item.competitor_research_error = None
    item.generation_context = {**(item.generation_context or {}), 'research_notice': warning}
    db.commit()
    return item
