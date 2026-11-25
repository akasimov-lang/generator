"""Explicit Webdev switch for old dynamic homepage redirects."""
from app.fake_main import fake_paths


def configure_old_redirects(project, enabled):
    alternate = (project.get('settings') or {}).get('alternate')
    if not isinstance(alternate, dict):
        raise ValueError('Не получены настройки фейковых страниц. Обновите данные.')
    if enabled and alternate.get('currentFakeMain') not in fake_paths(alternate):
        raise ValueError('Сначала выберите действующую фейковую страницу.')
    return {**alternate, 'redirectFakeMainsToCurrent': enabled}
