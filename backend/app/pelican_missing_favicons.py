"""Fill missing Pelican favicons from the user-approved report; preserve working icons."""
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree
import argparse
import json
import httpx

from app import models
from app.project_network import Remote, network_lock
from app.maintenance_reports import upsert

REPORT = 'e3bf181f-b4a4-5bbd-9641-1cb4b550f0bf'
NAME = 'Pelican · Favicon на проектах без значка · 06.11.2026'


class Icons(HTMLParser):
    def __init__(self):
        super().__init__(); self.urls = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'link' and 'icon' in (attrs.get('rel') or '').lower().split() and attrs.get('href'):
            self.urls.append(attrs['href'])


def is_image(response):
    if not response.is_success or not response.headers.get('content-type', '').startswith('image/'):
        return False
    raw = response.content
    if raw.startswith((b'\x89PNG\r\n\x1a\n', b'\x00\x00\x01\x00', b'GIF87a', b'GIF89a', b'\xff\xd8')):
        return True
    if raw.startswith(b'RIFF') and raw[8:12] == b'WEBP': return True
    try: return ElementTree.fromstring(raw).tag.split('}')[-1] == 'svg'
    except (ElementTree.ParseError, ValueError): return False


def icon(index):
    colors = ['#f1b900','#ffcb24','#eeb20a','#ffc900','#f4bf18','#ffcf3b','#edb100']
    radius = [12,20,8,32,16,4,24][index % 7]
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><title>Pelican Casino</title><rect x="1" y="1" width="62" height="62" rx="{radius}" fill="{colors[index % 7]}"/><path fill="#121820" fill-rule="evenodd" d="M10 47V17h11q10 0 10 10T21 37h-4v10z M17 24v6h4q3 0 3-3t-3-3z"/><path fill="#121820" d="M54 20v8c-3-3-9-5-11 1v8c2 6 8 4 11 1v8c-6 4-18 1-18-9v-9c0-10 12-13 18-8z"/></svg>'


def public_state(client, origin, markup=''):
    page = client.get(origin + '/')
    if not page.is_success:
        return {'state': 'unavailable', 'http_status': page.status_code}
    parser = Icons(); parser.feed(page.text)
    configured = Icons(); configured.feed(markup or '')
    paths = list(dict.fromkeys([*parser.urls, *configured.urls, '/favicon.ico', '/favicon.png']))
    checked = []
    for path in paths:
        try:
            response = client.get(urljoin(str(page.url), path))
        except httpx.HTTPError:
            return {'state': 'unavailable', 'url': path}
        checked.append({'url': str(response.url), 'http_status': response.status_code})
        if is_image(response): return {'state': 'present', 'url': str(response.url), 'linked': path in parser.urls or path == '/favicon.ico', 'checked': checked}
        if response.status_code not in (200,404,410):
            return {'state': 'unavailable', 'checked': checked}
    return {'state': 'missing', 'checked': checked}


def run_site(db, site_id, index, *, apply=False):
    site = db.get(models.Site, site_id)
    ledger_key = 'pelican-favicon:' + REPORT + ':' + site_id
    with network_lock(db, site_id), Remote(db, site) as remote, httpx.Client(timeout=20, follow_redirects=True) as client:
        project = remote.project(); origin = 'https://' + project['settings']['canon']
        before = deepcopy(project.get('head') or {})
        existing = db.get(models.AutoReglueConfig, ledger_key)
        state = deepcopy(existing.value) if existing else {'site_id': site_id, 'before': before, 'created_at': datetime.now(timezone.utc).isoformat()}
        observed = public_state(client, origin, before.get('favicon'))
        if observed['state'] == 'unavailable':
            return {'status': 'waiting', 'before': observed, 'comment': 'Публичная страница или файл недоступны. Существующие значки не изменялись.'}
        if observed['state'] == 'present':
            ours = state.get('path') and observed['url'] == origin + state['path']
            return {'status': ('completed' if observed.get('linked') else 'waiting') if ours else 'skipped', 'after': observed,
                    'comment': 'Favicon загружен и подтверждён на сайте.' if ours else 'Работающий favicon сохранён.'}
        if not apply:
            return {'status': 'pending', 'before': observed, 'planned': {'action': 'Загрузить favicon Pelican', 'variant': index + 1}}
        if not existing:
            existing = models.AutoReglueConfig(key=ledger_key); db.add(existing)
        if not state.get('path'):
            if state.get('status') == 'uploading':
                raise ValueError('Загрузка файла не подтверждена. Повторная отправка остановлена.')
            state['status'] = 'uploading'; existing.value = deepcopy(state); db.commit()
            code, response = remote.request('POST', '/projects/image', {'folder': site.name,
                'name': f'pelican-favicon-{site_id}.svg', 'customPath': 'brand/favicon', 'buffer': icon(index)})
            path = response.get('imagePath') or response.get('webpPath') if isinstance(response, dict) else None
            if not isinstance(response, dict) or response.get('error') != 'none' or not path or not path.startswith('/uploads/') or '..' in path or urlsplit(path).netloc:
                raise ValueError('Не подтверждён путь загруженного favicon.')
            state.update(path=path, status='uploaded', upload_http=code); existing.value = deepcopy(state); db.commit()
        path = state['path']
        if not is_image(client.get(origin + path)):
            raise ValueError('Загруженный favicon пока не доступен как изображение.')
        markup = f'<link rel="icon" type="image/svg+xml" href="{path}">' if path.endswith('.svg') else f'<link rel="icon" href="{path}">'
        current = remote.project().get('head') or {}
        if current.get('favicon') != markup:
            if current.get('favicon') != state['before'].get('favicon') or state.get('status') == 'writing':
                raise ValueError('Favicon изменён или его запись ещё не подтверждена. Повторная отправка остановлена.')
            state.update(status='writing', markup=markup); existing.value = deepcopy(state); db.commit()
            remote.request('PATCH', '/projects/update-head', {'folder': site.name, 'favicon': markup})
        final = remote.project().get('head') or {}
        if final.get('favicon') != markup:
            raise ValueError('Настройка favicon пока не подтверждена Webdev.')
        state.update(status='applied', updated_at=datetime.now(timezone.utc).isoformat())
        existing.value = deepcopy(state); db.commit()
        public = public_state(client, origin, markup)
        # The configured image alone is insufficient: confirm its link in the public HTML too.
        parser = Icons(); parser.feed(client.get(origin + '/').text)
        confirmed = path in parser.urls and public['state'] == 'present'
        return {'status': 'completed' if confirmed else 'waiting', 'after': {'path': path, 'public': public},
            'confirmed_at': state['updated_at'], 'comment': 'Favicon загружен и подтверждён на сайте.' if confirmed else 'Файл и настройка сохранены. Ожидаем обновления публичной страницы.'}


def main():
    from app.db import SessionLocal
    parser = argparse.ArgumentParser(); parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    with SessionLocal() as db:
        report = db.get(models.BackgroundJob, REPORT)
        if not report or report.kind != 'maintenance_report': raise ValueError('Сначала создайте отчёт группы.')
        ids = report.payload['site_ids']
        entries = []
        for index, site_id in enumerate(ids):
            try: result = run_site(db, site_id, index, apply=args.apply)
            except Exception as error:
                db.rollback(); result = {'status': 'partial', 'comment': str(error)[:300]}
            entries.append({'site_id': site_id, **result})
            upsert(db, REPORT, NAME, 'anton', ids, [entries[-1]])
            print(json.dumps(entries[-1], ensure_ascii=False), flush=True)
        status = 'completed' if all(e['status'] in {'completed','skipped'} for e in entries) else 'partial'
        upsert(db, REPORT, NAME, 'anton', ids, status=status)


if __name__ == '__main__': main()
