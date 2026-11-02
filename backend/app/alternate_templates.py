"""Versioned project templates imported from user-provided CSV files."""
import json
from pathlib import Path
import re
from html import escape
from types import SimpleNamespace


def base_alternate_markup(domain, language, geo, fake_path):
    from app.fake_main import normalize_fake_path
    language = (language or '').strip().lower().replace('_', '-').split('-')[0]
    geo = (geo or '').strip().upper().replace('_', '-').split('-')[-1]
    if not re.fullmatch(r'[a-z]{2,3}', language) or not re.fullmatch(r'[A-Z]{2}', geo):
        raise ValueError('Для базового альтернейта нужны язык и GEO проекта.')
    path = normalize_fake_path(fake_path)
    return '\n'.join(f'<link rel="alternate" href="https://{escape(domain, quote=True)}{path}" hreflang="{lang}" />'
                     for lang, path in [(language, '/'), (f'{language}-{geo}', path), ('x-default', '/')])


def next_base_fake_path(site, state, language, geo):
    from app.fake_main import next_fake_path
    normalized = SimpleNamespace(brand=getattr(site, 'brand', None), cache_language=language, cache_geo=geo)
    return next_fake_path(normalized, state, SimpleNamespace(language=language))


def template_catalog() -> list[dict]:
    return json.loads((Path(__file__).parent / 'data' / 'alternate_templates.json').read_text())['profiles']

