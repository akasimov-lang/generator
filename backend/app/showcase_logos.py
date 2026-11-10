"""Validated native showcase logo uploads; mutations are never retried."""
import base64
import binascii
from io import BytesIO
from urllib.parse import urlsplit, unquote

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field


class LogoUpload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=200)
    data: str = Field(max_length=2800000)


def prepare(logo):
    try:
        raw = base64.b64decode(logo.data, validate=True)
        if not raw or len(raw) > 2 * 1024 * 1024:
            raise ValueError('size')
        with Image.open(BytesIO(raw)) as img:
            if img.format not in {'PNG', 'JPEG', 'WEBP'} or img.width * img.height > 16000000:
                raise ValueError('format or dimensions')
            img.load()
            output = BytesIO()
            img.convert('RGBA').save(output, format='PNG')
            if output.tell() > 4 * 1024 * 1024:
                raise ValueError('decoded size')
            return '.png', base64.b64encode(output.getvalue()).decode()
    except (ValueError, binascii.Error, UnicodeError, UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(422, 'Загрузите PNG, JPEG или WebP, размером до 2 МБ.')


def target(casinos, row_id):
    import json
    group, index = json.loads(row_id)
    if not isinstance(casinos, dict) or not isinstance(casinos.get('basic'), list):
        raise HTTPException(422, 'У этой витрины нет галереи логотипов.')
    record = casinos[group][index]
    gallery = next((g for g in casinos['basic'] if g.get('key') == 'logo' and g.get('type') == 'gallery' and isinstance(g.get('data'), list)), None)
    field = next((f for f in record if isinstance(f, dict) and f.get('key') == 'logo' and f.get('type') == 'logo'), None) if isinstance(record, list) else None
    if gallery is None or field is None:
        raise HTTPException(422, 'Эта карточка не поддерживает загрузку логотипа.')
    return gallery, field


def upload(remote, project_name, request_id, prepared):
    extension, buffer = prepared
    code, response = remote.request('POST', '/projects/image', {
        'name': f'brand-{request_id}{extension}', 'folder': project_name,
        'buffer': buffer, 'customPath': 'vitrina/logo'})
    if not isinstance(response, dict) or response.get('error') != 'none':
        raise ValueError('Image upload not confirmed')
    path = response.get('webpPath') or response.get('imagePath')
    if not isinstance(path, str) or not path.startswith('/uploads/') or '..' in path or urlsplit(path).netloc:
        raise ValueError('Invalid uploaded image path')
    return path


def attach(casinos, row_id, path, name, logo_id):
    gallery, field = target(casinos, row_id)
    while any(str(item.get('id')) == str(logo_id) for item in gallery['data']):
        logo_id += 1
    gallery['data'].append({'id': logo_id, 'src': path, 'alt': name})
    field['id'] = logo_id


def url(project, record):
    if not isinstance(record, list):
        return None
    casinos = (project.get('data') or {}).get('casinos')
    if not isinstance(casinos, dict):
        return None
    logo_id = next((f.get('id') for f in record if isinstance(f, dict) and f.get('key') == 'logo'), None)
    for gallery in casinos.get('basic', []):
        if gallery.get('key') != 'logo':
            continue
        for item in gallery.get('data', []):
            if logo_id is not None and str(item.get('id')) == str(logo_id):
                src = item.get('src', '')
                if isinstance(src, str) and src.startswith('/'):
                    # Legacy project logos also live in /casinos/, /images/ or
                    # the project root. Resolve them against Main, not PagePilot.
                    path = unquote(src)
                    if path.startswith('//') or '\\' in path or '..' in path.split('/'):
                        return None
                    canon = (project.get('settings') or {}).get('canon')
                    if not isinstance(canon, str) or not canon:
                        return None
                    try:
                        origin = urlsplit(canon if '://' in canon else 'https://' + canon)
                    except ValueError:
                        return None
                    if origin.scheme in {'http', 'https'} and origin.netloc and not origin.username:
                        return f'{origin.scheme}://{origin.netloc}' + src
                if isinstance(src, str) and urlsplit(src).scheme in {'https', 'http'}:
                    return src
    return None
