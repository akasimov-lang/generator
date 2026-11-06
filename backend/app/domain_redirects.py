"""Edit one Webdev settings.redirects entry without replacing other settings."""
import re
from copy import deepcopy
from urllib.parse import urlsplit
from app.network_state import domain_name


def verified_redirects(state):
    rows = state.get('domain_redirects')
    if (not state.get('redirects_verified', state.get('has_domain_redirects'))
            or not isinstance(rows, list) or any(not isinstance(row, dict)
            or not isinstance(row.get('url'), str) or not isinstance(row.get('value'), str) for row in rows)):
        raise ValueError('REDIRECTS_NOT_VERIFIED: Не получены актуальные доменные редиректы. Операция запрещена до обновления данных Webdev.')
    return rows


def require_transfer_free(state, domains):
    rows = verified_redirects(state)
    keys = {domain_name(d).removeprefix('www.'): d for d in domains}
    for row in rows:
        for value in (row['url'], row['value']):
            key = domain_name(value).removeprefix('www.')
            if key and key in keys:
                raise ValueError(f"DOMAIN_REDIRECT: Домен {keys[key]} участвует в редиректе {row['url']} → {row['value']}. Перенос между сетками запрещён.")


def retarget_redirects(state, old_main, new_main):
    """Retarget old Main endpoints, retaining custom destinations and intermediate chains."""
    rows = deepcopy(verified_redirects(state))
    old_key = domain_name(old_main).removeprefix('www.')
    new_key = domain_name(new_main)
    result = []
    for row in rows:
        source = domain_name(row['url'])
        target = domain_name(row['value']).removeprefix('www.')
        if source == new_key:
            continue  # The new Main must serve content instead of redirecting to itself.
        if target == old_key:
            row['value'] = new_main
        result.append(row)
    return result


def redirect_domain(value):
    raw = value.strip().lower().rstrip('.')
    try:
        domain = raw.encode('idna').decode()
    except UnicodeError:
        domain = ''
    if ('.' not in domain or len(domain) > 253 or not all(
            re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
            for label in domain.split('.'))):
        raise ValueError('Укажите домен без протокола, пути и порта.')
    return domain


def redirect_address(value, *, source=False):
    """Accept pasted HTTP URLs; preserve the destination path exactly."""
    raw = value.strip().lstrip('/')
    raw = re.sub(r'^https?://', '', raw, flags=re.IGNORECASE).lstrip('/')
    if not raw or '\\' in raw or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in raw):
        raise ValueError('Укажите корректный адрес без пробелов.')
    try:
        url = urlsplit('https://' + raw)
        if url.username is not None or url.password is not None or url.port is not None:
            raise ValueError('Укажите адрес без логина, пароля и порта.')
        host = redirect_domain(url.hostname or '')
    except ValueError:
        raise ValueError('Укажите корректный домен без логина, пароля и порта.') from None
    if source:
        if url.path not in ('', '/') or url.query or url.fragment:
            raise ValueError('Откуда: укажите домен без пути, параметров и якоря.')
        return host
    return host + url.path + ('?' + url.query if url.query else '') + ('#' + url.fragment if url.fragment else '')


def all_to_main(state):
    """Preserve sources/metadata, replace every destination, and remove self-redirects."""
    main = redirect_domain(state.get('canon') or '')
    rows = deepcopy(verified_redirects(state))
    result = []
    for row in rows:
        source = redirect_domain(row['url'])
        if source.removeprefix('www.') == main.removeprefix('www.'):
            continue
        row['value'] = main
        result.append(row)
    return result


def update_redirects(project, source, target, original_source=''):
    settings = project.get('settings') or {}
    current = settings.get('redirects')
    if not isinstance(current, list) or any(
            not isinstance(row, dict) or not isinstance(row.get('url'), str)
            or not isinstance(row.get('value'), str) for row in current):
        raise ValueError('Webdev не вернул полный список доменных редиректов. Обновите данные проекта.')
    source, target = redirect_address(source, source=True), redirect_address(target)
    original = redirect_address(original_source, source=True) if original_source else ''
    if source == domain_name(target):
        raise ValueError('Домен не может перенаправлять на самого себя.')
    redirects = deepcopy(current)
    original_rows = [i for i, row in enumerate(redirects) if row['url'].strip().lower().rstrip('.') == original] if original else []
    if original and len(original_rows) != 1:
        raise ValueError('Редирект для редактирования изменился или отсутствует. Обновите данные.')
    index = original_rows[0] if original_rows else len(redirects)
    if any(i != index and row['url'].strip().lower().rstrip('.') == source for i, row in enumerate(redirects)):
        raise ValueError('Редирект с этого домена уже существует. Отредактируйте существующую строку.')
    row = {**(redirects[index] if index < len(redirects) else {}), 'url': source, 'value': target}
    if index < len(redirects):
        redirects[index] = row
    else:
        redirects.append(row)
    edges = {domain_name(r['url']): domain_name(r['value']) for r in redirects}
    seen, cursor = set(), source
    while cursor in edges:
        if cursor in seen:
            raise ValueError('Редирект создаёт замкнутую цепочку перенаправлений.')
        seen.add(cursor)
        cursor = edges[cursor]
    return redirects


def for_reglue(state, payload):
    """Auto plans retarget the complete network; manual reglue retains its policy."""
    destination = payload.get('redirect_target')
    if not destination:
        return retarget_redirects(state, payload['source_domain'], payload['reserve'])
    main = redirect_domain(payload['reserve'])
    if domain_name(destination) != main:
        raise ValueError('Цель редиректов должна принадлежать новому Main.')
    rows = deepcopy(verified_redirects(state))
    result = []
    for row in rows:
        if domain_name(row['url']).removeprefix('www.') == main.removeprefix('www.'): continue
        row['value'] = destination
        result.append(row)
    if payload.get('redirect_old_main'):
        old = redirect_domain(payload['source_domain'])
        if old.removeprefix('www.') != main.removeprefix('www.'):
            # Existing entry is already retargeted; no duplicate sources.
            if not any(domain_name(r['url']).removeprefix('www.') == old.removeprefix('www.') for r in result):
                result.append({'url': old, 'value': destination})
    return result
