from types import SimpleNamespace
from sqlalchemy import select
from app import models
from app.site_brands import detect_brand, update_detected_brand, backfill, GENERAL
from test_api_serialization import make_client


def test_detection_requires_clear_cached_identity():
    def detect(title, name='project.test'):
        return detect_brand(SimpleNamespace(homepage_title=title, name=name, cache_canon='drop.test'))
    assert detect('BetOnRed Casino CZ 2026') == 'BetOnRed'
    assert detect('Pin-Up Casino Azərbaycanda') == 'Pin-Up'
    assert detect('1xslots Casino — Official') == '1xslots'
    assert detect('1X Slots Casino') == '1xslots'
    assert detect('Qizilbilet — rəsmi sayt') == 'Qizilbilet'
    assert detect('Qızılbilet Casino') == 'Qizilbilet'
    assert detect('Pelican — Official Site') == 'Pelican'
    assert detect('PELICAN Casino') == 'Pelican'
    assert detect('Pinco — официальный сайт') == 'Pinco'
    assert detect('Пинко казино') == 'Pinco'
    assert detect('1win – Top Sports Betting') == '1win'
    assert detect('Mostbet vs 1win — comparison') == GENERAL
    assert detect('Best Online Casino Australia') == GENERAL
    assert detect(None) == GENERAL
    for generic in ['Meilleur', 'Nye', 'Crypto', 'No deposit', 'Plinko', 'Aviator']:
        assert detect(generic + ' Casino', generic.replace(' ', '-') + '-casino.test') == GENERAL
    assert detect('VOX Casino') == detect('Vox Casino') == 'Vox'
    assert detect('ExampleBrand Casino 2026', 'examplebrand-casino.test') == 'ExampleBrand'
    assert detect('ExampleBrand Casino 2026') == GENERAL
    assert detect('Online Casino Canada', 'online-casino.test') == GENERAL


def test_brand_shared_api_manual_override_and_idempotent_backfill():
    client, sessions = make_client()
    with sessions() as db:
        site = db.scalar(select(models.Site)); site.homepage_title = 'Mostbet Casino'
        db.commit()
        result = backfill(db)
        assert result['defined'] == 1 and site.brand == 'Mostbet'
        site_id = site.id
    from app.security import require_auth
    client.app.dependency_overrides[require_auth] = lambda: {'id': 'reader', 'username': 'reader', 'is_admin': False}
    # Shared brand editing is available to authenticated users.
    response = client.patch(f'/api/sites/{site_id}/brand', json={'brand': ' My Brand '})
    assert response.status_code == 200, response.text
    assert response.json()['brand'] == 'My Brand'
    with sessions() as db:
        site = db.get(models.Site, site_id)
        site.homepage_title = 'Pin-Up Casino'
        update_detected_brand(site)
        assert site.brand == 'My Brand'
        db.commit()
        assert backfill(db)['brands'] == {'My Brand': 1}
    assert client.patch(f'/api/sites/{site_id}/brand', json={'brand': ''}).json()['brand'] == GENERAL
    assert client.patch(f'/api/sites/{site_id}/brand', json={'brand': 'x' * 161}).status_code == 422
