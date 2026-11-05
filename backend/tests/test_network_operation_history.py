from datetime import datetime,timezone,timedelta
from uuid import uuid4
import pytest
from app import models, project_network as network
from test_project_network import env


def test_active_operations_are_kept_above_recent_twenty_completed(env):
    db,site,_=env
    start=datetime(2026,1,1,tzinfo=timezone.utc)
    pending=models.NetworkOperation(id=str(uuid4()),site_id=site.id,action='reserve',status='pending',initiator='test',request_payload={},created_at=start)
    db.add(pending)
    for i in range(25):
        db.add(models.NetworkOperation(id=str(uuid4()),site_id=site.id,action='reserve',status='confirmed',initiator='test',request_payload={},created_at=start+timedelta(days=i+1)))
    db.commit()
    history=network.operation_history(db,site)
    assert len(history)==21 and history[0]['id']==pending.id


@pytest.mark.parametrize('field,attribute',[('main','main_history'),('alternate','alternate_history'),('x_default','x_default_history'),('ban','domain_bans')])
def test_domain_checkbox_can_be_added_and_removed_without_webdev(env,monkeypatch,field,attribute):
    db,site,_=env
    site.cache_geo="CZ"; db.commit()
    network.read_network(db,site)
    monkeypatch.setattr(network,'Remote',lambda *_:pytest.fail('Checkbox saving must not contact Webdev'))
    saved=network.update_domain_history(db,site,network.DomainHistoryUpdate(domain='next.test',field=field,checked=True),'test')
    assert (saved[attribute]['next.test'] if field=='ban' else 'next.test' in saved[attribute])
    saved=network.update_domain_history(db,site,network.DomainHistoryUpdate(domain='next.test',field=field,checked=False),'test')
    assert not (saved[attribute]['next.test'] if field=='ban' else 'next.test' in saved[attribute])
