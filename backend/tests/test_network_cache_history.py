from copy import deepcopy
from datetime import datetime,timezone
from uuid import uuid4

from app import models
from app.network_state import observe_network, state_revision
from app.network_cache_history import KEY, visible
from app.reglue_journal import recent_for_site
from test_project_network import env


def test_cache_change_has_both_paths_and_repeated_snapshot_does_not_duplicate(env):
    db,site,remote=env
    observe_network(site,remote.project(),db=db); db.commit()
    remote.data['settings']['alternate']['currentFakeMain']='/new/'
    state=observe_network(site,remote.project(),db=db); db.commit()
    event=state[KEY][0]
    assert (event['old_path'],event['new_path'],event['source']) == ('/cz/','/new/','cache')
    observe_network(site,remote.project(),db=db); db.commit()
    assert site.network_state[KEY] == [event]
    assert recent_for_site(db,site)[0] == event


def test_initial_import_is_baseline_not_a_fabricated_change(env):
    db,site,remote=env
    state=observe_network(site,remote.project(),db=db)
    assert not state.get(KEY)


def test_partial_cache_does_not_fabricate_fake_path_change(env):
    db,site,remote=env
    observe_network(site,remote.project(),db=db); db.commit()
    state=observe_network(site,{'settings':{'alternate':{'fakeMain':['/spare/']}}},db=db)
    assert not state.get(KEY)
    assert state['fake_main_current']=='/cz/'
    assert state['canon']=='main.test'


def test_history_metadata_does_not_change_network_revision():
    state={'canon':'main.test'}
    assert state_revision(state)==state_revision({**state,KEY:[{'at':'now'}],'cache_change_baseline':True})


def test_cache_echo_of_confirmed_write_is_shown_once(env):
    db,site,remote=env
    observe_network(site,remote.project(),db=db); db.commit()
    remote.data['settings']['alternate']['currentFakeMain']='/new/'
    observe_network(site,remote.project(),db=db); db.commit()
    now=datetime.now(timezone.utc).isoformat()
    operation=models.NetworkOperation(id=str(uuid4()),site_id=site.id,action='select_fake_main',status='confirmed',initiator='test',
        request_payload={'confirmed_at':now,'alternate':{'currentFakeMain':'/new/','enableDynamicRoutes':True},
        'journal_before':{'main':'main.test','fake_path':'/cz/'},'journal_after':{'main':'main.test','fake_path':'/new/'}})
    db.add(operation);db.commit()
    history=recent_for_site(db,site)
    assert len(history)==1
    assert history[0]['id']==operation.id


def test_existing_cache_difference_from_last_receipt_is_reconciled_once(env):
    db,site,remote=env
    site.network_state={'canon':'main.test','fake_main_current':'/external/'}
    operation=models.NetworkOperation(id=str(uuid4()),site_id=site.id,action='reglue',status='confirmed',initiator='test',
        request_payload={'source_domain':'old.test','reserve':'main.test','journal_after':{'main':'main.test','fake_path':'/previous/'}})
    db.add(operation);db.commit()
    remote.data['settings']['alternate']['currentFakeMain']='/external/'
    observe_network(site,remote.project(),db=db);db.commit()
    assert len(site.network_state[KEY])==1
    event=site.network_state[KEY][0]
    assert event['comparison']=='last_recorded'
    assert (event['old_path'],event['new_path'])==('/previous/','/external/')
    observe_network(site,remote.project(),db=db)
    assert site.network_state[KEY]==[event]


def test_return_to_old_value_is_a_separate_observed_change(env):
    db,site,remote=env
    observe_network(site,remote.project(),db=db); db.commit()
    remote.data['settings']['alternate']['currentFakeMain']='/new/'
    observe_network(site,remote.project(),db=db); db.commit()
    remote.data['settings']['alternate']['currentFakeMain']='/cz/'
    observe_network(site,remote.project(),db=db)
    assert len(site.network_state[KEY])==2
    assert site.network_state[KEY][1]['new_path']=='/cz/'
