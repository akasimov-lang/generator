"""Publish homepage edits separately for manually launched saved plans."""
from datetime import datetime, timezone
from uuid import UUID, uuid5

from app import models


def failure_status(db, run, before_network):
    if not before_network:
        return 'partial'
    return 'partial' if any(
        (edit := db.get(models.ProjectPageEdit, str(uuid5(UUID(run.id), action))))
        and edit.status == 'confirmed' for action in ('title-h1-save', 'paragraphs-save')
    ) else 'failed'


def before_network(db, run, state):
    """Keep network resume phases intact, including after an uncertain page save.

    Manual plans delegate content to durable publication jobs. Other runs retain
    the existing requirement to confirm content before changing Main.
    """
    if not any(run.plan.get(key) for key in ('rewrite_title_h1', 'rewrite_paragraphs')):
        return True
    old_main, new_main = run.plan.get('old_main'), run.plan.get('new_main')
    prefix = 'cross:' if run.plan.get('execution_mode') == 'cross_network' else ''
    main_receipt = db.get(models.NetworkOperation, str(uuid5(UUID(run.id), prefix + 'reglue')))
    if state['canon'] != old_main and not (
            state['canon'] == new_main and main_receipt and main_receipt.status == 'confirmed'):
        raise ValueError('Main изменился вне этого запуска. Сохранение контента остановлено.')
    from app.pilot_content_publication import attach
    if attach(db, run):
        run.phase = run.plan.get('content_return_phase', run.phase)
        run.plan = {key: value for key, value in run.plan.items() if key != 'content_return_phase'}
        db.commit()
        return True
    original_phase = run.plan.get('content_return_phase', run.phase)
    run.plan = {**run.plan, 'content_return_phase': original_phase}
    db.commit()
    from app.reglue_title_h1 import finish as title
    from app.reglue_paragraphs import finish as paragraphs
    for finish in (title, paragraphs):
        if not finish(db, run, before_network=state['canon'] == old_main):
            return False
    run.plan = {**run.plan, 'content_prepared_at': datetime.now(timezone.utc).isoformat()}
    run.plan = {key: value for key, value in run.plan.items() if key != 'content_return_phase'}
    run.phase = original_phase
    db.commit()
    return True
