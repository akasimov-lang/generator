"""Dynamic copies of the home page managed by Webdev settings.alternate."""
import re


def normalize_fake_path(value):
    path = str(value or '').strip().strip('/')
    if not path or len(path) > 248 or not re.fullmatch(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*', path):
        raise ValueError('Укажите путь страницы, например test1 или /events/, без домена и параметров.')
    if path.split('/')[0].lower() in {'api', 'admin', 'assets', 'static'}:
        raise ValueError('Этот путь зарезервирован системой.')
    return '/' + path + '/'


def fake_paths(alternate):
    result = []
    values = alternate.get('fakeMain', [])
    for value in values if isinstance(values, list) else []:
        try:
            path = normalize_fake_path(value)
        except ValueError:
            continue
        if path not in result:
            result.append(path)
    return result


def create_fake_settings(project, value):
    path = normalize_fake_path(value)
    settings = project.get('settings') or {}
    alternate = dict(settings.get('alternate') or {})
    data = project.get('data') or {}
    for page in data.get('pages', []) if isinstance(data, dict) else []:
        if isinstance(page, dict) and '/' + str(page.get('slug') or '').strip('/') + '/' == path:
            raise ValueError('По этому пути уже есть обычная страница. Выберите другой путь.')
    current = alternate.get('currentFakeMain') or ''
    if alternate.get('redirectFakeMainsToCurrent') and current and normalize_fake_path(current) != path:
        raise ValueError('Включён редирект фейковых страниц на другой текущий путь. Сначала измените эту настройку в Webdev.')
    existing = list(alternate.get('fakeMain') or [])
    if path not in fake_paths(alternate):
        existing.append(path)
    alternate.update(fakeMain=existing, enableDynamicRoutes=True)
    if not current:
        alternate['currentFakeMain'] = path
    return alternate
