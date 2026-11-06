from xml.etree import ElementTree
import httpx
from test_project_network import env
from app.pelican_missing_favicons import icon, is_image, public_state
from io import BytesIO
from PIL import Image
import base64


def test_png_variants_are_valid_distinct_small_images_for_native_api():
    from app.pelican_missing_favicons import png_icon
    variants = [png_icon(i) for i in range(7)]
    assert len(set(variants)) == 7
    for raw in variants:
        assert len(raw) < 16000
        with Image.open(BytesIO(raw)) as img:
            img.load()
            assert img.format == 'PNG' and img.size == (128,128)
            assert img.getpixel((0,0))[3] == 0


def test_seven_distinct_favicons_are_self_contained_svg():
    icons = [icon(i) for i in range(7)]
    assert len(set(icons)) == 7
    for value in icons:
        root = ElementTree.fromstring(value)
        assert root.attrib['viewBox'] == '0 0 64 64'
        assert not any(x.tag.split('}')[-1] in {'script','image','foreignObject'} for x in root.iter())


def test_existing_public_favicon_is_preserved_even_if_native_setting_is_empty():
    def handler(request):
        if request.url.path == '/': return httpx.Response(200, text='<link rel="icon" href="/brand.svg">')
        assert request.url.path == '/brand.svg'
        return httpx.Response(200, text=icon(0), headers={'content-type': 'image/svg+xml'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = public_state(client, 'https://site.test')
    assert result['state'] == 'present' and result['linked'] and result['url'].endswith('/brand.svg')


def test_missing_images_are_distinguished_from_html_fallbacks_and_unavailable_sites():
    def handler(request):
        if request.url.path == '/': return httpx.Response(200, text='<link rel="icon" href="/favicon.png">')
        return httpx.Response(200, text='<html>not found</html>', headers={'content-type':'image/png'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert public_state(client, 'https://site.test')['state'] == 'missing'
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(403))) as client:
        assert public_state(client, 'https://site.test')['state'] == 'unavailable'


def test_a_configured_file_is_not_mistaken_for_a_publicly_linked_icon():
    def handler(request):
        if request.url.path == '/brand.svg':
            return httpx.Response(200, text=icon(1), headers={'content-type':'image/svg+xml'})
        return httpx.Response(200, text='<html>No favicon link</html>')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=public_state(client,'https://site.test','<link rel="icon" href="/brand.svg">')
    assert result['state']=='present' and not result['linked']


def test_ledger_keys_fit_the_database_limit_and_are_unique_per_project():
    from uuid import uuid4
    from app import models
    from app.pelican_missing_favicons import ledger_key
    first, second = str(uuid4()), str(uuid4())
    assert len(ledger_key(first)) <= models.AutoReglueConfig.__table__.c.key.type.length
    assert ledger_key(first) == ledger_key(first)
    assert ledger_key(first) != ledger_key(second)


def test_native_upload_updates_only_favicon_and_is_not_repeated(env, monkeypatch):
    from copy import deepcopy
    from contextlib import nullcontext
    from app import pelican_missing_favicons as favicons
    db, site, _ = env
    project = {'settings': {'canon': 'site.test'}, 'head': {'favicon': '', 'enableCanonical': True, 'canonicalDefaultMarkup': 'keep'}}
    before = deepcopy(project); calls = []; uploaded = {}
    path = '/uploads/brand/favicon/pelican.png'
    class Remote:
        def project(self): return deepcopy(project)
        def request(self, method, endpoint, payload):
            calls.append(endpoint)
            if endpoint == '/projects/image':
                assert payload['name'].endswith('.png')
                uploaded[path] = base64.b64decode(payload['buffer']); return 201, {'error': 'none', 'imagePath': path}
            assert endpoint == '/projects/update-head' and set(payload) == {'folder','favicon'}
            project['head']['favicon'] = payload['favicon']; return 200, {}
    def handler(request):
        if request.url.path == '/': return httpx.Response(200, text=project['head']['favicon'])
        if request.url.path in uploaded: return httpx.Response(200, content=uploaded[path], headers={'content-type':'image/png'})
        return httpx.Response(404)
    client = httpx.Client
    monkeypatch.setattr(favicons, 'Remote', lambda *args: nullcontext(Remote()))
    monkeypatch.setattr(favicons.httpx, 'Client', lambda **kwargs: client(transport=httpx.MockTransport(handler)))
    assert favicons.run_site(db, site.id, 0, apply=True)['status'] == 'completed'
    assert favicons.run_site(db, site.id, 0, apply=True)['status'] == 'completed'
    assert calls == ['/projects/image', '/projects/update-head']
    assert {k:v for k,v in project['head'].items() if k!='favicon'} == {k:v for k,v in before['head'].items() if k!='favicon'}


def test_definite_native_rejection_is_recorded_and_can_be_retried(env, monkeypatch):
    from contextlib import nullcontext
    import pytest
    from app import models, pelican_missing_favicons as favicons
    db, site, _ = env
    attempts = []
    class Remote:
        def project(self): return {'settings': {'canon':'site.test'}, 'head': {}}
        def request(self, *args):
            attempts.append(args)
            response = httpx.Response(400, request=httpx.Request('POST','https://native.test/projects/image'))
            response.raise_for_status()
    client = httpx.Client
    monkeypatch.setattr(favicons,'Remote',lambda *args:nullcontext(Remote()))
    monkeypatch.setattr(favicons.httpx,'Client',lambda **kwargs:client(transport=httpx.MockTransport(
        lambda request:httpx.Response(200,text='<html/>') if request.url.path == '/' else httpx.Response(404))))
    with pytest.raises(httpx.HTTPStatusError): favicons.run_site(db,site.id,0,apply=True)
    receipt=db.get(models.AutoReglueConfig,favicons.ledger_key(site.id)).value
    assert receipt['status']=='rejected' and receipt['upload_http']==400
    with pytest.raises(httpx.HTTPStatusError): favicons.run_site(db,site.id,0,apply=True)
    assert len(attempts)==2


def test_ambiguous_native_timeout_blocks_duplicate_upload(env, monkeypatch):
    from contextlib import nullcontext
    import pytest
    from app import models, pelican_missing_favicons as favicons
    db, site, _ = env
    attempts = []
    class Remote:
        def project(self): return {'settings': {'canon':'site.test'}, 'head': {}}
        def request(self, *args):
            attempts.append(args)
            raise httpx.ReadTimeout('unconfirmed upload')
    client=httpx.Client
    monkeypatch.setattr(favicons,'Remote',lambda *args:nullcontext(Remote()))
    monkeypatch.setattr(favicons.httpx,'Client',lambda **kwargs:client(transport=httpx.MockTransport(
        lambda request:httpx.Response(200,text='<html/>') if request.url.path == '/' else httpx.Response(404))))
    with pytest.raises(httpx.ReadTimeout): favicons.run_site(db,site.id,0,apply=True)
    assert db.get(models.AutoReglueConfig,favicons.ledger_key(site.id)).value['status']=='uploading'
    with pytest.raises(ValueError,match='Повторная отправка остановлена'):
        favicons.run_site(db,site.id,0,apply=True)
    assert len(attempts)==1
