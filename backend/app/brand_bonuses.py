"""Authenticated reference catalog of collected PL/CZ brand offers.

Provenance is retained in the versioned dataset, but is not returned to the UI.
Reading this catalog never changes project showcases or contacts their servers.
"""
from functools import lru_cache
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from app.security import AuthUser

router = APIRouter(prefix='/brand-bonuses', tags=['Brand bonuses'])
DATA = Path(__file__).parent / 'data' / 'brand_bonuses.json'
COUNTRIES = [
    {'code': 'PL', 'name': 'Польша', 'flag': '🇵🇱'},
    {'code': 'CZ', 'name': 'Чехия', 'flag': '🇨🇿'},
]


@lru_cache(maxsize=1)
def dataset():
    return json.loads(DATA.read_text(encoding='utf-8'))


def public_offer(offer):
    return {key: offer[key] for key in (
        'id', 'title', 'category', 'facts', 'observed_at', 'status', 'valid_until'
    ) if key in offer}


def public_brand(brand):
    return {key: brand[key] for key in ('id', 'name', 'geo', 'logo_url')} | {
        'offers': [public_offer(offer) for offer in brand['offers']],
    }


@router.get('')
def listing(user: AuthUser, response: Response, geo: str | None = None):
    response.headers['Cache-Control'] = 'private, no-store'
    if geo is not None and geo.upper() not in {'PL', 'CZ'}:
        raise HTTPException(422, 'Выберите Польшу или Чехию.')
    data = dataset()
    items = [public_brand(item) for item in data['items'] if not geo or item['geo'] == geo.upper()]
    return {'updated_at': data['updated_at'], 'items': items, 'total': len(items),
            'offers_total': sum(len(item['offers']) for item in items),
            'countries': [country | {
                'brands': sum(item['geo'] == country['code'] for item in data['items']),
                'offers': sum(len(item['offers']) for item in data['items'] if item['geo'] == country['code']),
            } for country in COUNTRIES]}


@router.get('/{geo}/{brand_id}')
def detail(geo: str, brand_id: str, user: AuthUser, response: Response):
    response.headers['Cache-Control'] = 'private, no-store'
    item = next((item for item in dataset()['items'] if item['geo'] == geo.upper() and item['id'] == brand_id), None)
    if item is None:
        raise HTTPException(404, 'Бренд не найден в выбранной стране.')
    return public_brand(item)
