from uuid import uuid4
from datetime import datetime,timezone
from app import models,auto_reglue as auto,mass_action_reports as reports,transfer_confirmation as confirmation
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool
from test_domain_redistribution import prepare


def test_manual_transfer_keeps_main_even_when_participation_is_disabled(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool)
    run.plan={**run.plan,'mass_filter':{'brand':'Pin-Up','geo':'AZ'}}
    source.reglue_participation=target.reglue_participation=False;db.commit()
    auto.execute(db,run.id)
    assert run.status=='completed',run.message
    assert remotes[target.id].data['settings']['canon']=='target.test'
    assert all(path!='/site-config/reglue' for remote in remotes.values() for path,_ in remote.calls)


def test_actual_guard_error_is_not_replaced_by_confirmation_message(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool)
    run.status='failed';run.message='Участвует в переклее: Нет. Запуск остановлен.';db.commit()
    result=reports.entry(run)
    assert result['message']==run.message
    assert result['domain_errors'][0]['message']==run.message
    assert result['domain_errors'][0]['code']=='TRANSFER_STOPPED'


def test_waiting_timer_survives_reload_and_stops_without_inventing_failure(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool);remotes[source.id].job_ready=False
    auto.execute(db,run.id)
    assert run.status=='waiting'
    assert confirmation.record_check(db,run,0)
    first=confirmation.view(run);db.expire_all();db.refresh(run)
    assert confirmation.view(run)==first
    assert first['next_check_at'] and first['limit']==30 and first['interval_seconds']==15
    assert reports.entry(run)['domain_errors']==[]
    assert not confirmation.record_check(db,run,30)
    assert run.status=='waiting' and confirmation.view(run)['exhausted']
    assert confirmation.view(run)['next_check_at'] is None
    remotes[source.id].job_ready=True;auto.execute(db,run.id)
    assert run.status=='completed'
    assert not confirmation.record_check(db,run,31)
    assert not confirmation.view(run)['exhausted']
    assert len([p for p,_ in remotes[source.id].calls if p=='/site-config/delete'])==1


def test_batch_confirmation_limit_and_terminal_error(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool);run.plan={**run.plan,'batch_id':str(uuid4())};run.status='waiting';db.commit()
    assert confirmation.record_check(db,run,9)
    assert confirmation.view(run)['limit']==10
    assert not confirmation.record_check(db,run,10)
    run.status='failed';run.message='DNS failed';db.commit()
    assert not confirmation.record_check(db,run,2)
    assert not confirmation.view(run)['exhausted']
    assert confirmation.view(run)['next_check_at'] is None


def test_preview_handles_unicode_editorial_urls_and_keeps_ascii_collision_guard():
    from types import SimpleNamespace
    from app.fake_main import next_fake_path
    site=SimpleNamespace(cache_geo='AZ',cache_language='az',brand='Pin-Up')
    state={'content_page_paths':['/odənis-usulları/','/review.html/','/az/'],'fake_main_current':'/az1/'}
    assert next_fake_path(site,state,SimpleNamespace(language='az'))=='/az2/'


def test_one_invalid_scheme_does_not_fail_other_projects_in_preview(pool):
    from app import cross_reglue_batch as batch
    db,source,target,remotes,add=pool
    source.project_status=target.project_status='working';db.commit()
    donor=add('donor.test',size=6,free=3)
    bad=add('bad.test',cache_language='az');good=add('good.test',cache_language='az')
    remotes[bad.id].data['settings']['alternate']={'enableDynamicRoutes':True,'currentFakeMain':'/az/','fakeMain':['/az/']}
    remotes[bad.id].data['head']['alternateMarkup']='<link rel="alternate" hreflang="az" href="https://{{wrong}}/" />'
    preview=batch.build(db,[bad,good],'test')
    assert [p['site_id'] for p in preview['plans']]==[good.id]
    assert preview['skipped'][0]['site_id']==bad.id
    assert 'полный адрес' in preview['skipped'][0]['error']
    assert all(not r.calls for r in remotes.values())


def test_waiting_for_network_does_not_exhaust_remote_confirmation_budget(pool):
    db,*_=pool;run=prepare(pool)
    run.plan={**run.plan,'batch_id':str(uuid4()),'waiting_for_network':True};run.status='waiting';db.commit()
    assert confirmation.record_check(db,run,confirmation.BATCH_LIMIT)
    assert not confirmation.view(run)['exhausted']
    run.plan={**run.plan,'waiting_for_network':False};db.commit()
    assert not confirmation.record_check(db,run,confirmation.BATCH_LIMIT)


def test_worker_requeues_busy_run_with_same_confirmation_attempt(pool,monkeypatch):
    from contextlib import nullcontext
    from app import worker
    from app.project_network import NetworkBusy
    db,*_=pool;run=prepare(pool)
    monkeypatch.setattr(worker,'SessionLocal',lambda:nullcontext(db))
    def busy(*args):raise NetworkBusy('Занято')
    monkeypatch.setattr(auto,'execute',busy)
    sent=[];monkeypatch.setattr(worker.auto_reglue_job,'apply_async',lambda **kw:sent.append(kw))
    worker.auto_reglue_job.run(run.id,3)
    assert sent==[{'args':[run.id,3],'countdown':confirmation.INTERVAL}]
