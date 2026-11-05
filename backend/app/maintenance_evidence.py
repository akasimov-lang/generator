"""Task-specific report facts; never infer publication from a plan or a terminal job."""
from copy import deepcopy


def enrich(job, entries, db=None):
    rows = deepcopy(entries)
    for row in rows:
        facts = []
        def add(label, value):
            facts.append({'label': label, 'value': str(value) if value is not None else 'Не подтверждено'})
        if job.payload.get('task_type') == 'toc_repair':
            pages = {p['slug']: p for p in row.get('page_results', []) if p.get('slug') is not None}
            errors = {slug for slug, p in pages.items() if p.get('changed') or p.get('previous_repair_confirmed')}
            fixed = {slug for slug in errors if pages[slug].get('status') == 'confirmed' or pages[slug].get('previous_repair_confirmed')}
            add('Проверено страниц', row.get('pages_checked'))
            add('Страниц с содержанием', len(pages) if 'page_results' in row else row.get('toc_pages'))
            add('Страниц с ошибкой до исправления', len(errors) if 'page_results' in row else None)
            add('Страниц исправлено и сохранено', len(fixed) if 'page_results' in row else None)
            add('Проверено исправлений на сайте', sum(bool(pages[slug].get('public', {}).get('verified')) for slug in fixed))
            add('Действие', 'Проверка ссылок содержания; создание якорей разделов и сохранение исправленных страниц.')
            add('Исправлено сохранённых документов генерации', sum(p.get('status') == 'confirmed' for p in row.get('draft_results', [])))
            add('Завершение проверки (UTC)', row.get('finished_at'))
        else:
            audit = row.get('audit') or {}
            brands = list(dict.fromkeys(r.get('brand') for r in audit.get('rows', []) if r.get('brand')))
            add('Источник проверки', audit.get('source'))
            add('Дата проверки (UTC)', row.get('audit_at'))
            add('Обнаруженные бренды', ', '.join(brands) or 'Карточки не определены; требуется проверка подключённого шаблона')
            add('Брендов до', len(brands) if brands else None)
            published = job.payload.get('showcase_publish') or {}
            if row.get('project') == 'whitbyluckyducks.com':
                pages = published.get('page_results') or []
                confirmed = [p for p in pages if p.get('receipt_id') and p.get('verified_at')]
                add('Действия с витриной', 'Публикация карточек через casinos; загрузка логотипов; оценки из исходной таблицы; адаптация мобильного названия бренда.')
                add('Страниц с подтверждённой публикацией витрины', len(confirmed))
                add('Брендов после', 10 if confirmed and all(p.get('cards') == 10 for p in confirmed) else None)
                add('Оценки подтверждены (UTC)', published.get('ratings_confirmed_at'))
                task_id = job.payload.get('homepage_task_id')
                if task_id and db is not None:
                    from app import models
                    task = db.get(models.GenerationTask, task_id)
                    if task and task.site_id == row['site_id']:
                        add('Задача на главную страницу', task.title)
                        add('Статус задачи генерации', {'draft': 'Черновик — генерация и публикация ещё не запущены'}.get(task.status, task.status))
                        add('ID задачи', task.id)
                add('ТЗ главной', 'Обзоры брендов витрины, изображения брендов, таблицы возможностей, платежей и проверенных лимитов; общие разделы о лицензии и ответственной игре; содержание с якорями.')
            else:
                add('Выполненное действие', 'Проверка подключений и карточек. Публикация изменений в этом проекте не подтверждена.')
                add('Брендов после', 'Без подтверждённых изменений')
            plan = row.get('showcase_plan')
            if plan:
                add('План — бренды', ', '.join(plan['brands']))
                add('План — количество брендов', len(plan['brands']))
                add('План — статус', 'Подготовлен; не опубликован')
                add('ТЗ — рекомендация для мета главной', plan.get('meta_recommendation'))
        row['facts'] = facts
    return rows
