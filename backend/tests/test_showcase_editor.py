from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app import models, project_pages, showcase_editor as editor
from test_project_pages import setup


def showcase_project():
    return {'settings': {}, 'data': {'pages': [{'id': 'home', 'slug': '/', 'content': {'blocks': [
        {'type': 'shortcode', 'data': {'shortcode': 'casinos'}}]}}], 'casinos': {
        'basic': [{'key': 'logo', 'type': 'gallery', 'data': [{'id': 44, 'alt': 'Unused logo'}]}],
        'standard': [
            [{'key': 'brand', 'type': 'text', 'value': 'Smash'},
             {'key': 'bonus', 'type': 'text', 'value': 'Original bonus'},
             {'key': 'split', 'type': 'text', 'value': 'smash-tracking'},
             {'key': 'logo', 'type': 'logo', 'id': 44},
             {'key': 'conditions', 'type': 'list', 'data': ['First', 'Second']}],
            [{'key': 'brand', 'type': 'text', 'value': 'Spinskull'},
             {'key': 'bonus', 'type': 'text', 'value': 'Other offer'}]],
        'old': [[{'key': 'brand', 'type': 'text', 'value': 'Unused'}]]}}}


def test_cache_cards_include_text_and_exclude_gallery_and_unused_groups():
    project = showcase_project()
    before = deepcopy(project)
    result = editor.view(project, 'cache')
    assert [row['brand'] for row in result['rows']] == ['Smash', 'Spinskull']
    assert [f['key'] for f in result['rows'][0]['fields']] == ['brand', 'bonus', 'conditions']
    assert result['rows'][0]['fields'][2]['value'] == 'First\nSecond'
    assert project == before


def test_unreferenced_native_dataset_is_not_presented_as_showcase():
    project = showcase_project()
    project['data']['pages'][0]['content']['blocks'] = []
    assert editor.rows(project) == []


def test_templates_select_actual_group_and_ignore_old_cards():
    project = showcase_project()
    project['shortcodes'] = [{'name': 'casinos.hbs', 'data': '{{#each casinos.old}}{{brand}}{{/each}}'}]
    assert [r['brand'] for r in editor.rows(project)] == ['Unused']


def test_edit_preserves_tracking_logos_other_cards_and_source_object():
    project = showcase_project()
    before = deepcopy(project)
    card = editor.rows(project)[0]
    changed = editor.edited_casinos(project, card['id'], {'1': 'Updated offer', '4': 'One\nTwo\nThree'})
    assert changed['standard'][0][1]['value'] == 'Updated offer'
    assert changed['standard'][0][4]['data'] == ['One', 'Two', 'Three']
    assert changed['standard'][0][2:4] == before['data']['casinos']['standard'][0][2:4]
    assert changed['standard'][1:] == before['data']['casinos']['standard'][1:]
    assert changed['basic'] == before['data']['casinos']['basic']
    assert project == before


def test_arbitrary_technical_field_cannot_be_edited():
    project = showcase_project()
    with pytest.raises(editor.HTTPException) as error:
        editor.edited_casinos(project, editor.rows(project)[0]['id'], {'2': 'replace tracking'})
    assert error.value.status_code == 422


@pytest.fixture
def api_setup(setup, monkeypatch):
    client, db, site, state = setup
    state['project'] = showcase_project()
    base = project_pages.Remote
    class Remote(base):
        def __init__(self, *args):
            self.client = SimpleNamespace(headers={})
        def request(self, method, path, payload):
            assert self.client.headers['Accept'] == 'application/json;v=2'
            assert method == 'POST'
            if path == '/projects/image':
                state.setdefault('uploads', []).append(deepcopy(payload))
                if state.get('upload_failure'):
                    raise state['upload_failure']
                return 201, {'error': 'none', 'webpPath': '/uploads/img/vitrina/logo/webp/new.webp'}
            assert path == '/projects/casinos'
            state['requests'].append(deepcopy(payload))
            if state['failure']:
                raise state['failure']
            if state['apply']:
                state['project']['data']['casinos'] = deepcopy(payload['casinos'])
            return 201, {'success': True}
    monkeypatch.setattr(editor, 'Remote', Remote)
    monkeypatch.setattr(editor, 'get_settings', lambda: SimpleNamespace(project_cache_username='service-account'))
    monkeypatch.setattr(editor, 'read_project', lambda *_, **kw: (deepcopy(state['project']), 'cache', None))
    client.app.include_router(editor.router)
    return client, db, site, state


def edit_request(client, site):
    path = f'/sites/{site.id}/showcase'
    data = client.get(path).json()
    return path, {'request_id': str(uuid4()), 'revision': data['revision'],
                  'row_id': data['rows'][0]['id'], 'fields': {'1': 'New bonus'}}


def test_showcase_load_is_independent_and_does_not_write(api_setup):
    client, db, site, state = api_setup
    response = client.get(f'/sites/{site.id}/showcase')
    assert response.status_code == 200 and response.json()['count'] == 2
    assert response.json()['source'] == 'cache'
    assert not state['requests']


def test_save_confirmed_audited_and_idempotent(api_setup):
    client, db, site, state = api_setup
    path, payload = edit_request(client, site)
    response = client.put(path, json=payload)
    assert response.status_code == 200 and response.json()['status'] == 'confirmed'
    assert response.json()['showcase']['rows'][0]['fields'][1]['value'] == 'New bonus'
    audit = db.get(models.ProjectPageEdit, payload['request_id'])
    assert audit.before_page['casinos']['standard'][0][1]['value'] == 'Original bonus'
    assert audit.after_page['casinos']['standard'][0][1]['value'] == 'New bonus'
    assert state['requests'][0]['project'] == site.name
    assert state['requests'][0]['initiator'] == 'service-account'
    assert client.put(path, json=payload).json()['status'] == 'confirmed'
    assert len(state['requests']) == 1


def test_concurrent_remote_change_prevents_save(api_setup):
    client, db, site, state = api_setup
    path, payload = edit_request(client, site)
    state['project']['data']['casinos']['standard'][1][1]['value'] = 'Someone changed another card'
    assert client.put(path, json=payload).status_code == 409
    assert not state['requests']


def test_timeout_is_not_retried_and_readback_confirms_later(api_setup):
    client, db, site, state = api_setup
    path, payload = edit_request(client, site)
    state['failure'] = httpx.ReadTimeout('upstream stalled')
    assert client.put(path, json=payload).json()['status'] == 'unknown'
    assert client.put(path, json=payload).json()['status'] == 'unknown'
    assert len(state['requests']) == 1
    state['project']['data']['casinos'] = deepcopy(state['requests'][0]['casinos'])
    checked = client.get(path + '/edits/' + payload['request_id'])
    assert checked.json()['status'] == 'confirmed'
    assert len(state['requests']) == 1


def test_wrong_site_access_never_loads_or_saves(api_setup):
    from app.security import require_auth
    client, db, site, state = api_setup
    path, payload = edit_request(client, site)
    client.app.dependency_overrides[require_auth] = lambda: {'username': 'limited', 'allowed_site_ids': []}
    assert client.get(path).status_code == 404
    assert client.put(path, json=payload).status_code == 404
    assert not state['requests']


def test_request_id_cannot_be_reused_for_other_text(api_setup):
    client, db, site, state = api_setup
    path, payload = edit_request(client, site)
    assert client.put(path, json=payload).json()['status'] == 'confirmed'
    payload['fields'] = {'1': 'Different text'}
    assert client.put(path, json=payload).status_code == 409
    assert len(state['requests']) == 1


def test_showcase_route_is_registered_in_application():
    from app.main import app
    assert '/api/sites/{site_id}/showcase' in {r.path for r in app.routes}


def test_confirmed_receipt_is_not_downgraded_after_later_changes(api_setup):
    client, db, site, state = api_setup
    path, payload = edit_request(client, site)
    assert client.put(path, json=payload).json()['status'] == 'confirmed'
    state['project']['data']['casinos']['standard'][0][1]['value'] = 'Later legitimate edit'
    assert client.get(path + '/edits/' + payload['request_id']).json()['status'] == 'confirmed'
    assert len(state['requests']) == 1


def logo_payload():
    import base64
    from io import BytesIO
    from PIL import Image
    out = BytesIO()
    Image.new('RGB', (12, 8), 'blue').save(out, 'PNG')
    return {'name': 'logo.png', 'data': base64.b64encode(out.getvalue()).decode()}


def test_logo_upload_preserves_gallery_other_cards_and_is_idempotent(api_setup):
    client, db, site, state = api_setup
    before = deepcopy(state['project']['data']['casinos'])
    path, payload = edit_request(client, site)
    payload['logo'] = logo_payload()
    response = client.put(path, json=payload)
    assert response.json()['status'] == 'confirmed'
    after = state['project']['data']['casinos']
    assert after['standard'][1:] == before['standard'][1:]
    assert after['basic'][0]['data'][0] == before['basic'][0]['data'][0]
    assert after['standard'][0][3]['id'] == after['basic'][0]['data'][-1]['id']
    assert state['uploads'][0]['customPath'] == 'vitrina/logo'
    assert state['uploads'][0]['name'].endswith('.png')
    assert client.put(path, json=payload).json()['status'] == 'confirmed'
    assert len(state['uploads']) == len(state['requests']) == 1


def test_logo_upload_timeout_never_posts_card_and_readcheck_allows_explicit_new_save(api_setup):
    client, db, site, state = api_setup
    path, payload = edit_request(client, site)
    payload['logo'] = logo_payload()
    state['upload_failure'] = httpx.ReadTimeout('upload stalled')
    assert client.put(path, json=payload).json()['status'] == 'unknown'
    assert client.put(path, json=payload).json()['status'] == 'unknown'
    assert not state['requests'] and len(state['uploads']) == 1
    assert client.get(path + '/edits/' + payload['request_id']).json()['status'] == 'failed'
    assert not state['requests'] and len(state['uploads']) == 1


def test_logo_card_timeout_confirms_without_reupload(api_setup):
    client, db, site, state = api_setup
    path, payload = edit_request(client, site)
    payload['logo'] = logo_payload()
    state['failure'] = httpx.ReadTimeout('card stalled')
    assert client.put(path, json=payload).json()['status'] == 'unknown'
    state['project']['data']['casinos'] = deepcopy(state['requests'][0]['casinos'])
    assert client.get(path + '/edits/' + payload['request_id']).json()['status'] == 'confirmed'
    assert len(state['uploads']) == len(state['requests']) == 1


def test_invalid_logo_never_contacts_remote(api_setup):
    client, db, site, state = api_setup
    path, payload = edit_request(client, site)
    import base64
    payload['logo'] = {'name': 'bad.svg', 'data': base64.b64encode(b'<svg><script>alert(1)</script></svg>').decode()}
    assert client.put(path, json=payload).status_code == 422
    assert not state['requests'] and not state.get('uploads')
