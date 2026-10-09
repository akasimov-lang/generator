from uuid import uuid4

from sqlalchemy import select

from app import models
from app.auto_reglue_api import router
from app.security import require_auth
from test_api_serialization import make_client


def test_authenticated_user_sees_and_controls_only_assigned_projects():
    client, sessions = make_client()
    client.app.include_router(router, prefix='/api')

    with sessions() as db:
        visible = db.scalar(select(models.Site))
        visible.project_status = 'mass_actions'
        hidden = models.Site(
            name='hidden.example',
            base_url='https://hidden.example',
            publication_endpoint='https://hidden.example/api/pages',
            payload_mode='simple_page',
            project_status='mass_actions',
        )
        db.add(hidden)
        db.flush()
        visible_run = models.AutoReglueRun(
            id=str(uuid4()), site_id=visible.id, initiator='admin', plan={}, status='completed', phase='done'
        )
        hidden_run = models.AutoReglueRun(
            id=str(uuid4()), site_id=hidden.id, initiator='admin', plan={}, status='waiting', phase='reglue'
        )
        db.add_all([visible_run, hidden_run])
        db.commit()
        visible_id = visible.id
        hidden_id = hidden.id
        hidden_run_id = hidden_run.id

    client.app.dependency_overrides[require_auth] = lambda: {
        'id': 'user-id',
        'username': 'user',
        'is_admin': False,
        'allowed_site_ids': [visible_id],
    }

    response = client.get('/api/auto-reglue')
    assert response.status_code == 200
    assert [project['id'] for project in response.json()['projects']] == [visible_id]
    assert [run['site_id'] for run in response.json()['runs']] == [visible_id]
    assert client.get(f'/api/auto-reglue/projects/{visible_id}').status_code == 200
    assert client.get(f'/api/auto-reglue/projects/{hidden_id}').status_code == 404
    assert client.post(f'/api/auto-reglue/runs/{hidden_run_id}/cancel').status_code == 404

    settings = response.json()['settings']
    assert client.put('/api/auto-reglue/settings', json=settings).status_code == 200
