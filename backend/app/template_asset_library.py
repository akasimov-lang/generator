"""Versioned local asset catalog; generated documents retain immutable image snapshots."""
import base64
import json
import mimetypes
from pathlib import Path
import re
import unicodedata
from html import escape

ROOT = Path(__file__).parent / 'data' / 'template_assets'


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())


def catalog():
    path = ROOT / 'manifest.json'
    return json.loads(path.read_text()) if path.exists() else {'version': 1, 'brands': [], 'payments': [], 'providers': []}


def image_snapshot(entry, field='logo'):
    filename = entry.get(field)
    if not filename:
        return None
    path = (ROOT / filename).resolve()
    if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
        raise ValueError('Неверный путь изображения в библиотеке')
    mime = mimetypes.guess_type(path.name)[0] or 'image/png'
    return {'name': entry['name'], 'id': entry['id'], 'filename': path.name,
            'mime': mime, 'data': base64.b64encode(path.read_bytes()).decode(),
            'source': entry.get('source', ''), 'kind': entry.get('kind', 'wordmark'), 'surface': entry.get('surface', 'dark')}


def uri(image):
    return f'data:{image["mime"]};base64,{image["data"]}'


def supported(entry, mention, brand, research, facts):
    quote = mention.evidence.strip()
    if len(quote) < 12 or not any(normalized(a) in normalized(quote) for a in [entry['name'], *entry.get('aliases', [])]):
        return False
    if mention.source_url == 'facts':
        return quote.casefold() in facts.casefold()
    if normalized(brand) not in normalized(quote):
        return False
    return any(s.get('status') == 'fetched' and s.get('url') == mention.source_url
               and quote.casefold() in s.get('excerpt', '').casefold() for s in (research or {}).get('sources', []))


def build_snapshot(brand, content, research, facts):
    lib = catalog()
    result = {'version': lib['version'], 'payments': [], 'providers': []}
    identity = next((b for b in lib['brands'] if normalized(brand) in {normalized(x) for x in [b['name'], *b.get('aliases', [])]}), None)
    if identity:
        result['logo'] = image_snapshot(identity)
        result['favicon'] = image_snapshot(identity, 'favicon')
    for group, mentions in [('payments', content.payment_systems), ('providers', content.game_providers)]:
        entries = {e['id']: e for e in lib[group]}
        used = set()
        for mention in mentions:
            entry = entries.get(mention.id)
            if entry and mention.id not in used and supported(entry, mention, brand, research, facts):
                image = image_snapshot(entry)
                if image:
                    result[group].append({**image, 'evidence': mention.evidence, 'source_url': mention.source_url})
                    used.add(mention.id)
    return result


def markup(document):
    snapshot = document.get('library_assets') or {}
    content = document.get('content') or {}
    rows = []
    for group, heading_key in [('payments', 'payments_heading'), ('providers', 'providers_heading')]:
        entries = snapshot.get(group, [])
        if not entries:
            continue
        images = ''.join(f'<div class="asset-badge asset-{e.get("surface", "dark")}"><img src="{uri(e)}" alt="{escape(e["name"])}" width="140" height="56" loading="lazy"><span>{escape(e["name"])}</span></div>' for e in entries)
        heading = content.get(heading_key) or ' / '.join(e['name'] for e in entries)
        rows.append(f'<section class="section" id="brand-{group}"><h2>{escape(heading)}</h2><div class="asset-strip">{images}</div></section>')
    return ''.join(rows)


def exported_assets(document):
    snap = document.get('library_assets') or {}
    files = {}
    for key in ['logo', 'favicon']:
        image = snap.get(key)
        if image:
            files[f'assets/library-{key}-{image["filename"]}'] = base64.b64decode(image['data'])
    for group in ['payments', 'providers']:
        for image in snap.get(group, []):
            files[f'assets/{group}-{image["filename"]}'] = base64.b64decode(image['data'])
    return files


def externalize(html, document):
    snap = document.get('library_assets') or {}
    for key in ['logo', 'favicon']:
        image = snap.get(key)
        if image:
            html = html.replace(uri(image), f'assets/library-{key}-{image["filename"]}')
    for group in ['payments', 'providers']:
        for image in snap.get(group, []):
            html = html.replace(uri(image), f'assets/{group}-{image["filename"]}')
    return html


ASSET_CSS = '.asset-strip{display:flex;flex-wrap:wrap;gap:18px}.asset-badge{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:18px;min-width:160px;background:#273241;color:#fff;border-radius:12px}.asset-badge.asset-light{background:#fff;color:#172433;border:1px solid #d8e0e8}.asset-badge img{display:block;width:140px;height:56px;object-fit:contain}.asset-badge span{font:14px/1.3 Arial,sans-serif}.logo{min-height:56px;width:clamp(140px,20vw,240px)}.logo img{max-width:100%;height:auto}@media(max-width:760px){.asset-strip{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.asset-badge{min-width:0;padding:12px}.asset-badge img{max-width:100%}}'
