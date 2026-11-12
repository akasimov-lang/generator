from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4
import httpx
from app import sitemap_maintenance as audit, network_sitemap as sitemap, maintenance_reports, models
from test_project_network import env


def setup_repair(env, monkeypatch):
    db,site,remote=env
    site.project_status='mass_actions';db.commit()
    remote.data.update(data={'pages':[{'slug':'/'},{'slug':'/bonus/'}]},sitemap='old')
    monkeypatch.setattr(audit,'SessionLocal',lambda:nullcontext(db))
    monkeypatch.setattr(audit,'Remote',lambda *args:nullcontext(remote))
    monkeypatch.setattr(sitemap,'public_check',lambda *args:None)
    def write(method,path,payload):
        from urllib.parse import unquote
        remote.calls.append(path);remote.data['sitemap']=unquote(payload['contents'])
        return 201,{}
    remote.request=write
    return db,site,remote


def test_repair_preserves_backup_and_only_writes_once(env,monkeypatch):
    db,site,remote=setup_repair(env,monkeypatch)
    monkeypatch.setattr(audit,'public_snapshot',lambda *args:{'valid':remote.data['sitemap']!='old','status':200,'count':2})
    rid=str(uuid4());row={'site_id':site.id,'project':site.name,'status':'pending'}
    result=audit.repair(rid,row)
    assert result['status']=='completed' and result['sitemap']['action']=='updated'
    assert result['sitemap']['before']['template']=='old'
    assert result['sitemap']['internal_pages']==1
    again=audit.repair(rid,result)
    assert again['status']=='completed' and len(remote.calls)==1


def test_valid_public_xml_does_not_rewrite_existing_template(env,monkeypatch):
    db,site,remote=setup_repair(env,monkeypatch)
    monkeypatch.setattr(audit,'public_snapshot',lambda *args:{'valid':True,'status':200,'count':2})
    result=audit.repair(str(uuid4()),{'site_id':site.id,'project':site.name})
    assert result['status']=='completed' and result['sitemap']['action']=='verified'
    assert not remote.calls


def test_changed_scope_is_skipped_without_remote_requests(env,monkeypatch):
    db,site,remote=setup_repair(env,monkeypatch);site.project_status='vitalina';db.commit()
    result=audit.repair(str(uuid4()),{'site_id':site.id,'project':site.name})
    assert result['status']=='skipped' and not remote.calls


def test_lost_write_response_can_be_confirmed_by_readback():
    op=SimpleNamespace(status='sitemap_done',response_status=None,request_payload={'before':None,'after':'xml'})
    assert audit.outcome(op,{'valid':True},True)==('completed','updated',None)


def test_saved_webdev_file_is_not_success_when_public_domain_returns_404():
    op=SimpleNamespace(status='sitemap_verify',response_status=201,request_payload={'before':'old','after':'xml'},message='404')
    status,action,error=audit.outcome(op,{'status':404},True)
    assert (status,action)==('partial','saved_unconfirmed')
    assert 'хостинге' in error


def test_successful_http_write_without_readback_is_failed():
    op=SimpleNamespace(status='sitemap_verify',response_status=201,request_payload={'before':'old','after':'xml'},message='Запись не подтверждена')
    assert audit.outcome(op,{'status':200,'valid':False},False)[:2]==('failed','write_error')


def test_public_snapshot_rejects_redirect_even_with_valid_xml(monkeypatch):
    async def allowed(*args): pass
    monkeypatch.setattr(audit,'require_public_url',allowed)
    client=httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(301,headers={'location':'https://other.test/sitemap.xml'},text=sitemap.document(['https://main.test/']))))
    monkeypatch.setattr(audit.httpx,'Client',lambda **kwargs:client)
    result=audit.public_snapshot('main.test',['https://main.test/'])
    assert result['status']==301 and result['valid'] is False


def test_report_view_excludes_full_xml_but_keeps_counts_and_result(env):
    db,site,remote=env
    job=maintenance_reports.upsert(db,str(uuid4()),'Sitemap','anton',[site.id],[{'site_id':site.id,'status':'completed','sitemap':{'before':{'template':'SECRET XML','expected_urls':['private'], 'public':{'count':1,'status':200}},'after':{'count':2,'valid':True},'internal_pages':1}}],status='completed')
    job.payload={**job.payload,'task_type':'sitemap_repair'};db.commit()
    view=maintenance_reports.view(job,db)
    assert view['progress']['total']==1 and view['progress']['percent']==100
    assert view['entries'][0]['sitemap']['before']=={'count':1,'status':200}
    assert 'SECRET XML' not in str(view)
    assert job.result['entries'][0]['sitemap']['before']['template']=='SECRET XML'


def test_sitemap_report_cannot_trigger_reglue_repeat(env):
    import pytest
    from app import maintenance_repeat
    db,site,remote=env
    job=maintenance_reports.upsert(db,str(uuid4()),'Sitemap','anton',[site.id])
    job.payload={**job.payload,'task_type':audit.TASK};db.commit()
    with pytest.raises(ValueError,match='Переклей и рерайт'):
        maintenance_repeat.create(db,job.id,str(uuid4()),{'username':'anton','allowed_site_ids':None})


def test_late_public_confirmation_recovers_expired_operation_without_write(env,monkeypatch):
    db,site,remote=setup_repair(env,monkeypatch)
    rid=str(uuid4());xml=sitemap.document(sitemap.expected(remote.data)[1]);remote.data['sitemap']=xml
    op=sitemap.queue(db,site,rid,'test');op.status='sitemap_failed'
    op.request_payload={'main':'main.test','urls':sitemap.expected(remote.data)[1],'before':'old','after':xml};db.commit()
    monkeypatch.setattr(audit,'public_snapshot',lambda *args:{'valid':True,'status':200,'count':2})
    result=audit.repair(rid,{'site_id':site.id,'project':site.name})
    assert result['status']=='completed' and result['sitemap']['action']=='updated'
    assert op.status=='sitemap_done' and not remote.calls
