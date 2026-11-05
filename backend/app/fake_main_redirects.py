"""Retarget saved redirects when the active fake homepage changes."""
from copy import deepcopy
from urllib.parse import urlsplit

from app.fake_main import normalize_fake_path


def retarget(project, old_path, new_path, main):
    if not old_path or not new_path or old_path == new_path:
        return {}
    old_path, new_path = normalize_fake_path(old_path), normalize_fake_path(new_path)
    main_key = main.lower().rstrip('.').removeprefix('www.')
    settings = project.get('settings') or {}

    def target(value):
        # Webdev domain redirects also store destinations without a scheme.
        url = urlsplit(value if '://' in value or value.startswith('//') else '//' + value)
        if (url.scheme not in ('', 'http', 'https') or url.username or url.password
                or (url.hostname or '').lower().rstrip('.').removeprefix('www.') != main_key
                or url.path != old_path):
            return value
        end = min([len(value), *[value.index(c) for c in '?#' if c in value]])
        return value[:end - len(old_path)] + new_path + value[end:]

    changes = {}
    for key in ('redirects', 'pageRedirects'):
        original = settings.get(key, [])
        if not isinstance(original, list):
            raise ValueError('Не получен полный список редиректов Webdev. Обновите данные перед сменой внутряка.')
        rows = deepcopy(original)
        groups = rows if key == 'pageRedirects' else [{'redirects': rows}]
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get('redirects'), list) or (key == 'pageRedirects' and not isinstance(group.get('domain'), str)):
                raise ValueError('Некорректный список редиректов Webdev. Смена внутряка отменена.')
            kept = []
            for row in group['redirects']:
                if not isinstance(row, dict) or not isinstance(row.get('url'), str) or not isinstance(row.get('value'), str):
                    raise ValueError('Некорректный редирект Webdev. Смена внутряка отменена.')
                updated = target(row['value'])
                if updated != row['value']:
                    source_domain = group['domain'] if key == 'pageRedirects' else row['url']
                    source_is_main = source_domain.lower().rstrip('.').removeprefix('www.') == main_key
                    if source_is_main and (key == 'redirects' or row['url'] == new_path):
                        continue  # The newly active page must not redirect to itself.
                    row['value'] = updated
                kept.append(row)
            group['redirects'][:] = kept
        if rows != original:
            changes[key] = rows
    return changes
