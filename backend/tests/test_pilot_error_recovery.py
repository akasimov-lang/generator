from copy import deepcopy
from uuid import uuid4

from app import models, mass_reglue_launch as launch
from app.pilot_error_recovery import retry_former_main_rows
from test_project_network import env


def test_retry_selects_only_matching_unstarted_rows_and_preserves_targets(env):
    db, site, remote = env
    wanted, other, completed, started = [str(uuid4()) for _ in range(4)]
    error = 'Выбранный домен уже использовался как Main в этой сетке.'
    rows = {
        wanted: {'status': 'failed', 'reason': error},
        other: {'status': 'failed', 'reason': 'БАН'},
        completed: {'status': 'completed', 'reason': error},
        started: {'status': 'failed', 'reason': error, 'run_id': str(uuid4())},
    }
    plans = [{'site_id': sid, 'new_main': sid + '.test'} for sid in rows]
    job = models.BackgroundJob(id=str(uuid4()), kind=launch.KIND, status='completed',
        payload={'streaming_start': True},
        result={'items': rows, 'groups': [{'site_ids': list(rows), 'status': 'done', 'plans': plans}]})
    db.add(job); db.commit()
    before = deepcopy(job.result)
    receipt = retry_former_main_rows(db, job.id, 'test')
    assert receipt['retried'] == [wanted]
    assert job.status == 'queued' and job.result['items'][wanted]['status'] == 'pending'
    assert job.result['groups'][0]['plans'] == before['groups'][0]['plans']
    assert job.result['items'][other] == before['items'][other]
    assert job.result['items'][completed] == before['items'][completed]
    assert job.result['items'][started] == before['items'][started]
    assert db.get(models.AutoReglueConfig, receipt['backup_key']).value['result_before'] == before
    assert retry_former_main_rows(db, job.id, 'test')['retried'] == []
