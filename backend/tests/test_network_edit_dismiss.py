"""Failed redirect drafts can be dismissed without changing Webdev or losing history."""
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models, network_edit_queue as queue, project_network as network
from test_network_edit_queue import add, prepare
from test_permissions import api
from test_project_network import env


INVALID_SOURCE = 'chimeraprime.com/careers/regular-hubspot-developer'


def failed_redirect(env, source=INVALID_SOURCE):
    ident = add(env, redirect_source=source, redirect_target='main.test')
    assert queue.execute_step(env[0], ident)['status'] == 'failed'
    return ident


def visible_ids(db, site):
    return {item['id'] for item in queue.snapshot(db, site)['items']}


def test_dismiss_invalid_source_preserves_history_and_saved_redirects(env, monkeypatch):
    db, site, remote = env
    prepare(env)
    ident = failed_redirect(env)
    job = db.get(models.BackgroundJob, ident)
    before_payload = deepcopy(job.payload)
    before_error = job.error
    before_remote = deepcopy(remote.data)
    assert ident in visible_ids(db, site)
    monkeypatch.setattr(network, 'Remote', lambda *_: pytest.fail('Dismiss contacted Webdev'))

    result = queue.dismiss(db, site, ident, 'anton')

    assert ident not in {item['id'] for item in result['items']}
    db.expire_all()
    assert ident not in visible_ids(db, site)
    job = db.get(models.BackgroundJob, ident)
    assert job.status == 'failed'
    assert job.payload == before_payload
    assert job.error == before_error
    assert job.result['dismissed_at']
    assert job.result['dismissed_by'] == 'anton'
    assert remote.data == before_remote
    assert remote.calls == []
    assert queue.execute_step(db, ident)['status'] == 'skipped'


def test_dismiss_is_idempotent_and_retains_first_actor(env):
    db, site, _ = env
    prepare(env)
    ident = failed_redirect(env)
    queue.dismiss(db, site, ident, 'anton')
    first_result = deepcopy(db.get(models.BackgroundJob, ident).result)

    queue.dismiss(db, site, ident, 'someone-else')

    assert db.get(models.BackgroundJob, ident).result == first_result
    assert ident not in visible_ids(db, site)


def test_dismiss_latest_also_hides_older_failed_attempt_for_same_source(env):
    db, site, _ = env
    prepare(env)
    older = failed_redirect(env)
    latest = failed_redirect(env)

    queue.dismiss(db, site, latest, 'anton')

    assert older not in visible_ids(db, site)
    assert latest not in visible_ids(db, site)
    assert db.get(models.BackgroundJob, older).status == 'failed'


def test_dismiss_older_attempt_preserves_newer_failure_for_same_source(env):
    db, site, _ = env
    prepare(env)
    older = failed_redirect(env)
    newer = failed_redirect(env)

    queue.dismiss(db, site, older, 'anton')

    assert older not in visible_ids(db, site)
    assert newer in visible_ids(db, site)
    assert not db.get(models.BackgroundJob, newer).result.get('dismissed_at')


def test_dismiss_preserves_failure_for_different_source(env):
    db, site, _ = env
    prepare(env)
    other = failed_redirect(env, 'other.test/path')
    selected = failed_redirect(env)

    queue.dismiss(db, site, selected, 'anton')

    assert selected not in visible_ids(db, site)
    assert other in visible_ids(db, site)


def test_dismiss_preserves_active_attempt_for_same_source(env):
    db, site, _ = env
    prepare(env)
    failed = failed_redirect(env)
    active = add(env, redirect_source=INVALID_SOURCE, redirect_target='main.test')

    queue.dismiss(db, site, failed, 'anton')

    assert failed not in visible_ids(db, site)
    assert active in visible_ids(db, site)
    assert db.get(models.BackgroundJob, active).status == 'queued'


@pytest.mark.parametrize('status', ['queued', 'running', 'waiting', 'completed'])
def test_dismiss_rejects_nonfailed_job(env, status):
    db, site, _ = env
    prepare(env)
    ident = add(env, redirect_source=INVALID_SOURCE, redirect_target='main.test')
    job = db.get(models.BackgroundJob, ident)
    job.status = status
    db.commit()

    with pytest.raises(network.NetworkConflict):
        queue.dismiss(db, site, ident, 'anton')

    assert not db.get(models.BackgroundJob, ident).result.get('dismissed_at')


def test_dismiss_rejects_failed_nonredirect_job(env):
    db, site, _ = env
    prepare(env)
    ident = add(env, 'reserve', domain='next.test')
    db.get(models.BackgroundJob, ident).status = 'failed'
    db.commit()

    with pytest.raises(network.NetworkConflict):
        queue.dismiss(db, site, ident, 'anton')


def test_dismiss_missing_job_returns_not_found(env):
    db, site, _ = env
    prepare(env)

    with pytest.raises(HTTPException) as error:
        queue.dismiss(db, site, str(uuid4()), 'anton')

    assert error.value.status_code == 404


def test_dismiss_job_from_another_site_returns_not_found(env):
    db, site, _ = env
    prepare(env)
    ident = failed_redirect(env)
    other_site = models.Site(name='another.test', base_url='https://another.test', publication_endpoint='https://another.test/api')
    db.add(other_site)
    db.commit()

    with pytest.raises(HTTPException) as error:
        queue.dismiss(db, other_site, ident, 'anton')

    assert error.value.status_code == 404
    assert ident in visible_ids(db, site)


def test_dismiss_job_of_another_kind_returns_not_found(env):
    db, site, _ = env
    prepare(env)
    ident = failed_redirect(env)
    job = db.get(models.BackgroundJob, ident)
    job.kind = 'publication'
    db.commit()

    with pytest.raises(HTTPException) as error:
        queue.dismiss(db, site, ident, 'anton')

    assert error.value.status_code == 404
    assert not job.result.get('dismissed_at')


def api_failed_job(engine, site_id='own'):
    ident = str(uuid4())
    with Session(engine) as db:
        db.add(models.BackgroundJob(id=ident, kind=queue.KIND, status='failed', error='Invalid source',
            payload={'site_id': site_id, 'project': site_id + '.test', 'sequence': 1, 'actor': 'editor',
                     'request': {'action': 'domain_redirect', 'redirect_source': INVALID_SOURCE,
                                 'redirect_original_source': '', 'redirect_target': 'main.test',
                                 'expected': {'rows': []}}},
            result={'phase': 'failed', 'message': 'Invalid source'}))
        db.commit()
    return ident


def test_dismiss_api_requires_authentication(api):
    client, engine, _ = api
    ident = api_failed_job(engine)
    client.headers.pop('Authorization')

    response = client.delete(f'/api/sites/own/network/edit-queue/{ident}')

    assert response.status_code == 401
    with Session(engine) as db:
        assert not db.get(models.BackgroundJob, ident).result.get('dismissed_at')


def test_dismiss_api_respects_project_access(api):
    client, engine, _ = api
    ident = api_failed_job(engine, 'other')

    response = client.delete(f'/api/sites/other/network/edit-queue/{ident}')

    assert response.status_code == 404
    with Session(engine) as db:
        assert not db.get(models.BackgroundJob, ident).result.get('dismissed_at')


def test_dismiss_api_cannot_use_own_site_path_for_another_sites_job(api):
    client, engine, _ = api
    ident = api_failed_job(engine, 'other')

    response = client.delete(f'/api/sites/own/network/edit-queue/{ident}')

    assert response.status_code == 404
    with Session(engine) as db:
        assert not db.get(models.BackgroundJob, ident).result.get('dismissed_at')


def test_dismiss_api_returns_persistent_snapshot_and_records_actor(api):
    client, engine, _ = api
    ident = api_failed_job(engine)

    response = client.delete(f'/api/sites/own/network/edit-queue/{ident}')

    assert response.status_code == 200, response.text
    assert response.json()['items'] == []
    assert client.get('/api/sites/own/network/edit-queue').json()['items'] == []
    with Session(engine) as db:
        job = db.get(models.BackgroundJob, ident)
        assert job.status == 'failed' and job.error == 'Invalid source'
        assert job.result['dismissed_by'] == 'editor'


def test_dismiss_api_returns_conflict_for_active_job(api):
    client, engine, _ = api
    ident = api_failed_job(engine)
    with Session(engine) as db:
        db.get(models.BackgroundJob, ident).status = 'queued'
        db.commit()

    response = client.delete(f'/api/sites/own/network/edit-queue/{ident}')

    assert response.status_code == 409, response.text
