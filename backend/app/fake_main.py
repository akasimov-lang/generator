"""Dynamic copies of the home page managed by Webdev settings.alternate."""
import re


def alphabetic_suffix(index):
    """Zero-based, deterministic sequence a..z, aa..az, ba.. without digits."""
    value = index + 1
    result = ''
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(97 + remainder) + result
    return result


def allow_numeric_fake_paths(state):
    current = set()
    for value in [*state.get('fake_main_paths', []), state.get('fake_main_current')]:
        if not value: continue
        try: path = normalize_fake_path(value)
        except ValueError: continue
        if re.search(r'\d', path): current.add(path.casefold())
    return len(current) > 10


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


def create_fake_settings(project, value, *, activate=False):
    path = normalize_fake_path(value)
    settings = project.get('settings') or {}
    alternate = dict(settings.get('alternate') or {})
    data = project.get('data') or {}
    for page in data.get('pages', []) if isinstance(data, dict) else []:
        if isinstance(page, dict) and '/' + str(page.get('slug') or '').strip('/') + '/' == path:
            raise ValueError('По этому пути уже есть обычная страница. Выберите другой путь.')
    current = alternate.get('currentFakeMain') or ''
    if not activate and alternate.get('redirectFakeMainsToCurrent') and current and normalize_fake_path(current) != path:
        raise ValueError('Включён редирект фейковых страниц на другой текущий путь. Сначала измените эту настройку в Webdev.')
    existing = list(alternate.get('fakeMain') or [])
    if path not in fake_paths(alternate):
        existing.append(path)
    alternate.update(fakeMain=existing, enableDynamicRoutes=True)
    if activate or not current:
        alternate['currentFakeMain'] = path
    return alternate


def select_fake_settings(project, value):
    path = normalize_fake_path(value)
    alternate = dict((project.get('settings') or {}).get('alternate') or {})
    if path not in fake_paths(alternate):
        raise ValueError('Выбранная фейковая страница отсутствует в актуальных настройках проекта.')
    alternate['currentFakeMain'] = path
    return alternate


def delete_fake_settings(project, value):
    path = normalize_fake_path(value)
    alternate = dict((project.get('settings') or {}).get('alternate') or {})
    if path not in fake_paths(alternate):
        raise ValueError('Выбранная фейковая страница отсутствует в актуальных настройках проекта.')
    current = alternate.get('currentFakeMain')
    if current and normalize_fake_path(current) == path:
        raise ValueError('Перед удалением текущей фейковой страницы назначьте другую.')
    def keep(value):
        try:
            return normalize_fake_path(value) != path
        except ValueError:
            return True
    alternate['fakeMain'] = [value for value in alternate.get('fakeMain', []) if keep(value)]
    return alternate


def next_fake_path(site, state, cfg, *, allocation_index=None):
    from app.site_brands import GENERAL

    geo = (getattr(site, 'cache_geo', None) or '').lower()
    language = (getattr(site, 'cache_language', None) or cfg.language).lower().replace('_', '-').split('-')[0]
    brand = (getattr(site, 'brand', None) or '').strip()
    generic = not brand or brand == GENERAL
    has_casino = 'casino' in brand.lower()
    if has_casino:
        # Handles both "Ice Casino" and catalog spellings such as "CatCasino".
        words = re.sub('casino', ' ', brand, flags=re.IGNORECASE).strip(' -_').split()
        brand = words[0] if words else ''
        generic = generic or not brand
    brand = re.sub(r'[^a-z0-9]', '', brand.lower())
    if not re.fullmatch('[a-z]{2}', geo) or not re.fullmatch('[a-z]{2,3}', language) or (not generic and not brand):
        raise ValueError('Для имени фейковой страницы нужны GEO, язык проекта и бренд латиницей (кроме общих ключей).')
    names = [geo, geo + '-' + language]
    if not generic:
        names.extend([brand + '-' + geo, brand + '-' + language, brand + language])
        if not has_casino:
            names.extend([brand + '-casino-' + geo, brand + '-casino-' + language])
    if allocation_index is not None:
        from app.naming_variants import names as diverse_names
        names = [*diverse_names(getattr(site, 'brand', '') or '', geo, language, index=allocation_index,
                               seed=getattr(site, 'id', '') or getattr(site, 'name', ''), style='hyphen'), *names]
    # Digits belonging to a brand are also digits in the new path. Keep a
    # readable alphabetic spelling until the current network permits numbers.
    plain = [re.sub(r'\d', '', name).strip('-') for name in names]
    names = list(dict.fromkeys(name for name in plain if name))
    if allow_numeric_fake_paths(state):
        names.extend(geo + str(i) for i in range(1, 11))
    occupied = set()
    for value in [*state.get('fake_main_history', []), *state.get('fake_main_paths', []), state.get('fake_main_current')]:
        if value and str(value).strip().strip('/'):
            occupied.add(normalize_fake_path(value).casefold())
    # Existing editorial URLs may contain Unicode, dots or other valid URL characters.
    # Compare their paths for collisions without validating them as new fake paths.
    occupied.update(('/' + str(value).strip().strip('/') + '/').casefold() for value in state.get('content_page_paths', []) if value)
    for name in dict.fromkeys(names):
        candidate = normalize_fake_path(name)
        if candidate.casefold() not in occupied:
            return candidate
    # A finite occupied set always leaves a free alphabetic suffix, including
    # when historical names or same-brand peer plans occupy the simple names.
    for index in range(len(occupied) + 1):
        candidate = normalize_fake_path(names[0] + '-' + alphabetic_suffix(index))
        if candidate.casefold() not in occupied:
            return candidate


def fake_canonical_markup(path):
    return '<link rel="canonical" href="https://{{settings.canon}}' + normalize_fake_path(path) + '" />'


def retarget_fake_head(state, old_path, new_path):
    """Change only link hrefs to the old fake page, preserving all other markup."""
    from urllib.parse import urlsplit
    if not old_path or not str(old_path).strip('/') or not new_path:
        return {}
    old_path, new_path = normalize_fake_path(old_path), normalize_fake_path(new_path)
    if old_path == new_path:
        return {}
    hosts = {str(host).lower() for host in [state.get('canon'), *state.get('domains', [])] if host}
    hosts.add('{{settings.canon}}')
    attribute = re.compile(r'''\b([\w-]+)\s*=\s*(["'])(.*?)\2''', re.DOTALL)

    def replace_link(match):
        tag = match.group(0)
        attrs = {attr.group(1).lower(): attr for attr in attribute.finditer(tag)}
        if 'href' not in attrs or 'rel' not in attrs or not set(attrs['rel'].group(3).lower().split()) & {'canonical', 'alternate'}:
            return tag
        href = attrs['href']
        value = href.group(3)
        try:
            url = urlsplit(value)
            if url.scheme and url.scheme.lower() not in {'http', 'https'}:
                return tag
            if url.netloc and (url.username or url.password or (url.hostname or '').lower() not in hosts):
                return tag
            if url.path != old_path or (not url.netloc and not value.startswith('/')):
                return tag
        except ValueError:
            return tag
        # Keep query strings, fragments, quoting, attribute order and spacing byte-for-byte.
        # The path is the exact suffix of the URL before its query/fragment.
        end = min([len(value), *[value.index(char) for char in '?#' if char in value]])
        updated = value[:end - len(old_path)] + new_path + value[end:]
        return tag[:href.start(3)] + updated + tag[href.end(3):]

    changes = {}
    for key in ('alternateMarkup', 'canonicalDefaultMarkup', 'canonicalFakeMainMarkup'):
        value = state.get(key) or ''
        updated = re.sub(r'<link\b[^>]*>', replace_link, value, flags=re.IGNORECASE)
        if updated != value:
            changes[key] = updated
    return changes
