import httpx
import pytest
from uuid import uuid4
from app import models,auto_reglue as auto,project_network as network,cross_reglue as cross,reglue_dns as dns
from test_project_network import env
from test_cross_reglue import setup,launch,dns_error_job


def test_mass_run_does_not_wait_for_public_pages_but_keeps_warning(setup,monkeypatch):
 db,source,target,sr,tr=setup
 run=launch(setup);run.plan={**run.plan,'list_launch_id':str(uuid4())};db.commit()
 def unavailable(urls):raise httpx.ConnectError('[Errno -2] Name or service not known')
 monkeypatch.setattr(auto,'verify_pages',unavailable)
 dns.verify_pages(db,target,run,{'domains':['next.test']})
 run.status='completed';db.commit()
 dns.audit_pages(db,run)
 assert run.status=='completed'
 assert 'Name or service' in run.plan['dns_warnings'][0]['message']
 assert run.plan['availability_checked_at']


def test_mass_provisioning_dns_failure_accepts_only_actual_webdev_membership(setup,monkeypatch):
 db,source,target,sr,tr=setup
 run=launch(setup);auto.execute(db,run.id)
 op=db.get(models.NetworkOperation,cross.receipt_id(run,'create_domains'))
 run.plan={**run.plan,'list_launch_id':str(uuid4())};op.status='failed';db.commit()
 monkeypatch.setattr(auto,'verify_pages',lambda _:(_ for _ in ()).throw(AssertionError('No public health gate')))
 assert cross.recovered_dns_job(db,target,op,dns_error_job())
 assert op.status=='confirmed' and op.request_payload['dns_recovery']['dns_advisory']
 tr.data['settings']['domains']=[]
 assert not cross.recovered_dns_job(db,target,op,dns_error_job())


def test_root_placeholder_is_not_a_fake_route():
 from app.fake_main import retarget_fake_head
 assert retarget_fake_head({'canon':'main.test'},'/', '/az11/')=={}


def test_mass_pipeline_saves_all_settings_before_optional_public_check(setup,monkeypatch):
 from app import mass_reglue_launch as launch
 db,source,target,sr,tr=setup
 job=launch.enqueue(db,uuid4(),[target.id],'test');sent=[]
 launch.execute_step(db,job.id,sent.append)
 assert len(sent)==1
 run=db.get(models.AutoReglueRun,sent[0])
 monkeypatch.setattr(auto,'verify_pages',lambda _:(_ for _ in ()).throw(AssertionError('Public health must not block writes')))
 auto.execute(db,run.id)
 assert run.status=='completed',run.message
 assert tr.data['settings']['canon']==run.plan['new_main']
 assert tr.data['head']['alternateMarkup']==run.plan['alternateMarkup']
 assert not any(path.endswith('check-domain') for path,_ in tr.calls)


@pytest.mark.parametrize('matches',[True,False])
def test_http_400_is_advisory_only_when_webdev_settings_match(setup,matches):
 db,source,target,sr,tr=setup
 run=launch(setup);run.plan={**run.plan,'list_launch_id':str(uuid4())};db.commit()
 expected='<link rel="alternate" href="https://next.test/" hreflang="x-default" />'
 op=models.NetworkOperation(id=cross.receipt_id(run,'alternates'),site_id=target.id,action='alternates',
  status='failed',response_status=400,initiator='test',message='Webdev вернул HTTP 400.',
  request_payload={'auto_run_id':run.id,'alternateMarkup':expected,'enableAlternates':True})
 db.add(op);db.commit()
 if matches:tr.data['head'].update(alternateMarkup=expected,enableAlternates=True)
 state=network.read_network(db,target)
 if matches:
  assert cross.change(db,run,target,'alternates',state)
  assert op.status=='confirmed' and 'HTTP 400' in run.plan['dns_warnings'][0]['message']
 else:
  with pytest.raises(ValueError,match='HTTP 400'):cross.change(db,run,target,'alternates',state)
  assert op.status=='failed'
 assert not tr.calls
