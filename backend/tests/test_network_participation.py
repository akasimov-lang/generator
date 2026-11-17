"""The project network panel always reads participation from the saved project flag."""
from sqlalchemy.orm import Session

from app import models
from test_permissions import api


def test_participation_toggle_persists_across_network_and_queue_refresh(api):
    client, engine, _ = api
    with Session(engine) as db:
        site = db.get(models.Site, 'own')
        site.network_state = {'domains': ['own.test'], 'canon': 'own.test',
                              'alternateMarkup': '', 'has_head': True,
                              'has_page_redirects': True, 'reglue_participation': True}
        db.commit()

    assert client.get('/api/sites/own/network').json()['reglue_participation'] is True
    disabled = client.patch('/api/auto-reglue/projects/own/participation', json={'enabled': False})
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()['reglue_participation'] is False
    network = client.get('/api/sites/own/network')
    assert network.status_code == 200, network.text
    assert network.json()['reglue_participation'] is False
    assert client.get('/api/sites/own/network/edit-queue').json()['network']['reglue_participation'] is False
    with Session(engine) as db:
        site = db.get(models.Site, 'own')
        assert site.reglue_participation is False
        assert site.network_state['reglue_participation'] is True

    enabled = client.patch('/api/auto-reglue/projects/own/participation', json={'enabled': True})
    assert enabled.status_code == 200
    assert client.get('/api/sites/own/network').json()['reglue_participation'] is True


def test_network_participation_cannot_be_changed_for_another_project(api):
    client, engine, _ = api
    response = client.patch('/api/auto-reglue/projects/other/participation', json={'enabled': False})
    assert response.status_code == 404
    with Session(engine) as db:
        assert db.get(models.Site, 'other').reglue_participation is True
