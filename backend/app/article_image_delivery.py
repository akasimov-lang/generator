"""Copy article illustrations into their Webdev project before publishing text.

The panel asset is a generation/preview source, never the published image URL.
Uploads have durable receipts and are not repeated after an ambiguous response.
"""
import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from html import escape, unescape
from io import BytesIO
import re
from urllib.parse import urljoin, urlsplit

import httpx
from PIL import Image

from app import models
from app.core.config import get_settings
from app.project_network import Remote, network_lock

MAX_BYTES = 12_000_000
TAG = re.compile(r'<(?:img|source)\b[^>]*>', re.I)
ATTR = re.compile(r'''(?P<prefix>\b(?:src|data-src|data-lazy-src)\s*=\s*)(?P<q>["'])(?P<url>.*?)(?P=q)''', re.I | re.S)
SET = re.compile(r'''\b(?:srcset|data-srcset)\s*=\s*(["'])(.*?)\1''', re.I | re.S)


def external(url):
    return bool(urlsplit(str(url)).netloc or str(url).startswith('data:'))


def image_urls(content):
    """References from article content only; links and global templates are untouched."""
    found = []
    def visit(value):
        if isinstance(value, dict):
            if value.get('type') == 'image' and isinstance(value.get('data'), dict):
                data = value['data']; file = data.get('file')
                url = file.get('url') if isinstance(file, dict) else data.get('url')
                if isinstance(url, str) and url: found.append(url)
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
        elif isinstance(value, str):
            for tag in TAG.finditer(value):
                found.extend(unescape(m['url']) for m in ATTR.finditer(tag[0]))
                for match in SET.finditer(tag[0]):
                    # Do not silently miss an external responsive source.
                    found.extend(unescape(part.strip().split()[0]) for part in match[2].split(',') if part.strip())
    visit(content)
    return found


def replace_urls(content, mapping):
    result = deepcopy(content)
    mapping = {old:new for old,new in mapping.items() if old != new}
    if not mapping: return result
    def markup(value):
        def tag_replace(tag):
            raw = ATTR.sub(lambda m: m['prefix'] + m['q'] + escape(mapping.get(unescape(m['url']), unescape(m['url'])), quote=True) + m['q'], tag[0])
            def srcset(m):
                parts = []
                for part in m[2].split(','):
                    bits = part.strip().split()
                    if bits: bits[0] = mapping.get(unescape(bits[0]), unescape(bits[0]))
                    parts.append(' '.join(bits))
                return m[0].replace(m[2], escape(', '.join(parts), quote=True), 1)
            return SET.sub(srcset, raw)
        return TAG.sub(tag_replace, value)
    def visit(value):
        if isinstance(value, dict):
            if value.get('type') == 'image' and isinstance(value.get('data'), dict):
                data = value['data']; file = data.get('file')
                target = file if isinstance(file, dict) else data
                if target.get('url') in mapping: target['url'] = mapping[target['url']]
            for key, child in value.items(): value[key] = visit(child)
        elif isinstance(value, list): value = [visit(v) for v in value]
        elif isinstance(value, str) and TAG.search(value): value = markup(value)
        return value
    return visit(result)


def picture(raw):
    if not raw or len(raw) > MAX_BYTES: raise ValueError('Некорректный размер изображения статьи.')
    with Image.open(BytesIO(raw)) as image:
        if image.width * image.height > 25_000_000: raise ValueError('Слишком большое изображение статьи.')
        image.load()
        size = image.size
        output = BytesIO()
        # Native Webdev supports PNG/JPEG uploads, not WebP or SVG.
        image.convert('RGBA' if 'A' in image.getbands() else 'RGB').save(output, 'PNG')
    if output.tell() > MAX_BYTES: raise ValueError('Изображение статьи превышает лимит загрузки.')
    return output.getvalue(), size


def public_image(url):
    """Fetch without credentials, validating all redirect targets and bounding bytes."""
    import ipaddress, socket
    with httpx.Client(timeout=25, follow_redirects=False, trust_env=False) as client:
        for _ in range(5):
            parsed = urlsplit(url)
            if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.port not in {None,80,443}:
                raise ValueError('Недопустимый адрес изображения.')
            addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                raise ValueError('Изображение должно находиться на публичном адресе.')
            with client.stream('GET', url) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers['location']); continue
                response.raise_for_status()
                if not response.headers.get('content-type','').lower().startswith('image/'):
                    raise ValueError('Вместо изображения сервер вернул другой документ.')
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_BYTES: raise ValueError('Изображение превышает лимит загрузки.')
                return bytes(data)
    raise ValueError('Слишком много перенаправлений изображения.')


def source_bytes(db, url):
    parsed = urlsplit(url)
    match = re.fullmatch(r'/api/article-images/media/([a-f0-9-]{36})\.webp', parsed.path)
    if match and parsed.netloc == urlsplit(get_settings().app_public_url).netloc:
        asset = db.get(models.ArticleImage, match[1])
        if not asset or asset.status != 'ready' or not asset.image_data:
            raise ValueError('Подготовленное изображение статьи не найдено.')
        return asset.image_data
    if url.startswith('data:image/'):
        header, data = url.split(',', 1)
        if ';base64' not in header or len(data) > MAX_BYTES * 4 // 3 + 4: raise ValueError('Некорректное встроенное изображение.')
        return base64.b64decode(data, validate=True)
    return public_image('https:' + url if url.startswith('//') else url)


def upload(db, site, remote, origin, url):
    raw = source_bytes(db, url)
    fingerprint = hashlib.sha256(raw).hexdigest()
    key = 'article-delivery:' + site.id + ':' + fingerprint[:20]
    receipt = db.get(models.AutoReglueConfig, key)
    if receipt and receipt.value.get('status') in {'confirmed', 'uploaded'} and receipt.value.get('path'):
        path = receipt.value['path']
        picture(public_image(urljoin(origin, path)))
        receipt.value = {**receipt.value, 'status':'confirmed', 'checked_at':datetime.now(timezone.utc).isoformat()}
        db.commit()
        return path
    if receipt:
        raise ValueError('Предыдущая загрузка изображения не подтверждена. Повторная запись остановлена до сверки.')
    png, size = picture(raw)
    receipt = models.AutoReglueConfig(key=key, value={'status':'pending','site_id':site.id,'source':url,
        'sha256':fingerprint,'started_at':datetime.now(timezone.utc).isoformat()})
    db.add(receipt); db.commit()
    try:
        _, response = remote.request('POST','/projects/image', {'folder':site.name,
            'name':'article-' + fingerprint[:24] + '.png','buffer':base64.b64encode(png).decode(),
            'customPath':'articles'})
        path = response.get('webpPath') or response.get('imagePath') if isinstance(response,dict) else None
        if not isinstance(response,dict) or response.get('error') != 'none' or not isinstance(path,str) or not path.startswith('/uploads/') or '..' in path or urlsplit(path).netloc:
            raise ValueError('Webdev не подтвердил загрузку изображения статьи.')
        receipt.value = {**receipt.value, 'status':'uploaded','path':path,'response':response}; db.commit()
        _, actual_size = picture(public_image(urljoin(origin, path)))
        if actual_size != size: raise ValueError('Размеры загруженного изображения не совпадают с исходником.')
        receipt.value = {**receipt.value,'status':'confirmed','checked_at':datetime.now(timezone.utc).isoformat()}; db.commit()
        return path
    except Exception as error:
        receipt.value = {**receipt.value,'error':str(error)[:500]}; db.commit()
        raise


def localize_payload(db, site, payload, remote=None, project=None):
    pages = payload.get('pages', []) if isinstance(payload,dict) else []
    urls = list(dict.fromkeys(url for page in pages if isinstance(page,dict)
        for url in image_urls(page.get('content'))))
    if not urls: return deepcopy(payload)
    if remote is None:
        with network_lock(db,site.id), Remote(db,site) as connection:
            return localize_payload(db,site,payload,connection,connection.project())
    canon = (project or remote.project())['settings'].get('canon')
    if not canon: raise ValueError('Main проекта не определён; изображения не загружены.')
    origin = (canon if '://' in canon else 'https://' + canon).rstrip('/') + '/'
    mapping = {}
    result = deepcopy(payload)
    checked = set()
    # Resolve a relative path against its own page, not against the first page
    # that happens to use the same filename.
    for page in result.get('pages', []):
        local = {}
        for url in image_urls(page.get('content')):
            if external(url): continue
            absolute = urljoin(urljoin(origin, str(page.get('slug') or '/').lstrip('/')), url)
            if absolute not in checked:
                picture(public_image(absolute)); checked.add(absolute)
            parsed = urlsplit(absolute)
            local[url] = parsed.path + ('?' + parsed.query if parsed.query else '')
        page['content'] = replace_urls(page.get('content'), local)
    for url in urls:
        if not external(url): continue
        parsed = urlsplit(url)
        if parsed.netloc == urlsplit(origin).netloc and parsed.path.startswith('/uploads/'):
            picture(public_image(urljoin(origin, parsed.path)))
            mapping[url] = parsed.path + ('?' + parsed.query if parsed.query else '')
        else:
            mapping[url] = upload(db,site,remote,origin,url)
    for page in result.get('pages',[]):
        if isinstance(page,dict): page['content'] = replace_urls(page.get('content'),mapping)
    result.setdefault('generation_meta',{})['image_delivery'] = {'status':'confirmed','project':site.name,
        'images':mapping,'checked_at':datetime.now(timezone.utc).isoformat()}
    return result
