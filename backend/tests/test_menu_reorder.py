from copy import deepcopy
import httpx
import pytest
from sqlalchemy import select
from app import models, menu_reorder as reorder
from app.security import require_auth
from test_api_serialization import make_client


def tree():
    return [
        {'id': 1, 'title': 'Casinos', 'slug': '/casino/', 'order': 5, 'class': 'custom', 'children': [
            {'id': 2, 'title': 'A', 'slug': '/casino/a/', 'order': 4, 'rel': 'nofollow'},
            {'id': 3, 'title': 'B', 'slug': '/casino/b/', 'order': 8, 'children': [{'id': 4, 'slug': '/deep/', 'order': 7}]},
        ]},
        {'id': 5, 'title': 'Bonus', 'slug': '/bonus/', 'order': 9},
        {'id': 6, 'title': 'Home', 'slug': '/', 'order': 15},
    ]


def test_root_move_keeps_whole_subtree_and_all_metadata():
    before = tree()
    result = reorder.move_item(before, [0], [2], 'after')
    assert [row['id'] for row in result] == [5, 6, 1]
    assert [row['order'] for row in result] == [0, 1, 2]
    assert result[2]['children'] == before[0]['children']
    assert result[2]['class'] == 'custom' and before == tree()


def test_nested_move_keeps_parent_urls_and_other_branches():
    before = tree()
    result = reorder.move_item(before, [0, 1], [0, 0], 'before')
    assert [row['id'] for row in result[0]['children']] == [3, 2]
    assert result[0]['children'][0]['children'] == before[0]['children'][1]['children']
    assert result[1:] == before[1:]
    assert result[0]['order'] == 5 and result[0]['slug'] == '/casino/'


def test_noop_does_not_renumber_existing_order():
    assert reorder.move_item(tree(), [1], [2], 'before') == tree()


def test_cannot_move_into_another_parent():
    with pytest.raises(ValueError, match='одного раздела'):
        reorder.move_item(tree(), [0, 1], [2], 'after')


def test_stale_or_negative_address_cannot_target_another_item():
    with pytest.raises(ValueError):
        reorder.move_item(tree(), [-1], [1], 'before')
    with pytest.raises(ValueError):
        reorder.move_item(tree(), [9], [1], 'before')


def setup(monkeypatch, menu_type='header'):
    client, sessions = make_client()
    client.app.include_router(reorder.router, prefix='/api')
    with sessions() as db:
        site = db.scalar(select(models.Site))
        site.default_menu = {'header': tree(), 'footer': tree()}
        db.commit()
        site_id = site.id
    state = {'menu': {'header': tree(), 'footer': tree()}, 'writes': [], 'reads': 0}
    class Remote:
        def __init__(self, *args): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def project(self):
            state['reads'] += 1
            if state.get('read_error') and state['reads'] > 1:
                raise httpx.ReadTimeout('Timeout')
            return {'data': {'menu': deepcopy(state['menu'])}}
        def request(self, method, path, payload):
            assert method == 'POST' and path == '/projects/menu'
            state['writes'].append(deepcopy(payload))
            if not state.get('reject'):
                state['menu'][payload['type']] = deepcopy(payload['list'])
            if state.get('timeout'):
                raise httpx.ReadTimeout('Timeout')
            return 200, {}
    monkeypatch.setattr(reorder, 'Remote', Remote)
    return client, sessions, site_id, state, f'/api/sites/{site_id}/menu/{menu_type}/reorder'


def payload():
    return {'source': [2], 'target': [0], 'position': 'before', 'expected_menu': tree()}


def test_header_order_persists_only_after_remote_readback(monkeypatch):
    client, sessions, site_id, state, url = setup(monkeypatch)
    response = client.post(url, json=payload())
    assert response.status_code == 200 and response.json()['success']
    assert state['reads'] == 2 and len(state['writes']) == 1
    with sessions() as db:
        menu = db.get(models.Site, site_id).default_menu
        assert [row['id'] for row in menu['header']] == [6, 1, 5]
        assert menu['footer'] == tree()
        log = db.scalar(select(models.PublicationLog))
        assert log.response_body['confirmed'] and log.request_payload['menu_before'] == tree()


def test_footer_reorder_does_not_touch_header(monkeypatch):
    client, sessions, site_id, state, url = setup(monkeypatch, 'footer')
    assert client.post(url, json=payload()).status_code == 200
    with sessions() as db:
        menu = db.get(models.Site, site_id).default_menu
        assert menu['header'] == tree()
        assert [row['id'] for row in menu['footer']] == [6, 1, 5]


def test_stale_snapshot_refreshes_cache_without_overwriting_remote_change(monkeypatch):
    client, sessions, site_id, state, url = setup(monkeypatch)
    state['menu']['header'][0]['title'] = 'Edited elsewhere'
    assert client.post(url, json=payload()).status_code == 409
    assert not state['writes']
    with sessions() as db:
        assert db.get(models.Site, site_id).default_menu['header'][0]['title'] == 'Edited elsewhere'


def test_remote_rejection_does_not_claim_success_or_save_requested_order(monkeypatch):
    client, sessions, site_id, state, url = setup(monkeypatch)
    state['reject'] = True
    assert client.post(url, json=payload()).status_code == 409
    with sessions() as db:
        assert db.get(models.Site, site_id).default_menu['header'] == tree()


def test_timeout_is_confirmed_by_read_without_retrying_write(monkeypatch):
    client, _, _, state, url = setup(monkeypatch)
    state['timeout'] = True
    assert client.post(url, json=payload()).status_code == 200
    assert len(state['writes']) == 1


def test_unconfirmed_write_is_reported_as_error(monkeypatch):
    client, sessions, site_id, state, url = setup(monkeypatch)
    state['read_error'] = True
    assert client.post(url, json=payload()).status_code == 502
    assert len(state['writes']) == 1
    with sessions() as db:
        assert db.get(models.Site, site_id).default_menu['header'] == tree()
        assert db.scalar(select(models.PublicationLog)).error_message


def test_project_permissions_block_reordering(monkeypatch):
    client, _, _, state, url = setup(monkeypatch)
    client.app.dependency_overrides[require_auth] = lambda: {'username':'other', 'allowed_site_ids':[]}
    assert client.post(url, json=payload()).status_code == 404
    assert state['reads'] == 0 and not state['writes']
