from types import SimpleNamespace
import re

import pytest

from app.fake_main import next_fake_path, allow_numeric_fake_paths, alphabetic_suffix
from app.subdomain_naming import next_subdomain, allow_numeric_subdomains


def context():
    site=SimpleNamespace(id='stable',name='project.test',brand='22Bet',cache_geo='PL',cache_language='pl',
        cache_domains=['root22.com'],domain_types={'root22.com':'drop'},main_domain_history=[],alternate_domain_history=[])
    cfg=SimpleNamespace(parent_kind='drop',language='pl',subdomain_add_casino=False,subdomain_name_style='joined')
    return site,cfg


@pytest.mark.parametrize('count,allowed',[(10,False),(11,True)])
def test_subdomain_numeric_threshold_counts_distinct_current_children_only(count,allowed):
    site,cfg=context()
    children=[f'old{i}.root22.com' for i in range(count)]
    state={'domains':['root22.com',*children,children[0]],'amp_domains':[]}
    site.cache_domains=[*state['domains'],*[f'cached{i}.root22.com' for i in range(30)]]
    site.main_domain_history=[f'past{i}.root22.com' for i in range(50)]
    assert allow_numeric_subdomains(state) is allowed
    produced=[]
    for _ in range(30):
        child=next_subdomain(site,state,cfg,'root22.com',prefer_geo=True)
        assert child==next_subdomain(site,state,cfg,'root22.com',prefer_geo=True)
        produced.append(child);state['domains'].append(child)
    assert len(set(produced))==30
    assert any(re.search(r'\d',child[:-len('.root22.com')]) for child in produced) is allowed


def test_root_digits_and_history_do_not_enable_numbered_subdomains():
    assert not allow_numeric_subdomains({'domains':[f'root{i}.com' for i in range(30)]})
    site,cfg=context();site.main_domain_history=[f'old{i}.root22.com' for i in range(30)]
    state={'domains':['root22.com']}
    assert not re.search(r'\d',next_subdomain(site,state,cfg,'root22.com').split('.')[0])


@pytest.mark.parametrize('count,allowed',[(10,False),(11,True)])
def test_fake_numeric_threshold_ignores_history_and_duplicate_paths(count,allowed):
    site,cfg=context()
    paths=[f'/legacy{i}/' for i in range(count)]
    state={'fake_main_paths':[*paths,paths[0].upper()], 'fake_main_current':paths[-1],
        'fake_main_history':[f'/retired{i}/' for i in range(50)]}
    assert allow_numeric_fake_paths(state) is allowed
    produced=[]
    for _ in range(30):
        path=next_fake_path(site,state,cfg)
        assert path==next_fake_path(site,state,cfg)
        produced.append(path);state['fake_main_paths'].append(path)
    assert len(set(produced))==30
    assert any(re.search(r'\d',path) for path in produced) is allowed


def test_removed_numbered_paths_cannot_enable_numeric_names_or_be_reused():
    site,cfg=context();site.brand='888 Casino'
    state={'fake_main_paths':[], 'fake_main_current':'/pl/',
        'fake_main_history':['/pl-pl/','/pl-a/','/pl-b/',*[f'/pl{i}/' for i in range(50)]],
        'content_page_paths':['/pl-c/']}
    assert not allow_numeric_fake_paths(state)
    assert next_fake_path(site,state,cfg)=='/pl-d/'
    assert alphabetic_suffix(0)=='a' and alphabetic_suffix(25)=='z' and alphabetic_suffix(26)=='aa'


@pytest.mark.parametrize('plan',[
    {'create_subdomain':'pl1.root22.com'},
    {'create_fake_main_path':'/pl1/'},
])
def test_old_reviewed_numeric_plan_requires_refresh_without_mutation(plan):
    from copy import deepcopy
    from app.subdomain_naming import validate_new_names
    before=deepcopy(plan)
    with pytest.raises(ValueError,match='Обновите план'):
        validate_new_names({'domains':['root22.com'],'fake_main_paths':[]},plan)
    assert plan==before
    validate_new_names({'domains':['root22.com',*[f'old{i}.root22.com' for i in range(11)]],
                       'fake_main_paths':[f'/old{i}/' for i in range(11)]},plan)


@pytest.mark.parametrize('cross',[False,True])
def test_prepared_guard_preserves_existing_receipts_and_started_operations(cross):
    from uuid import uuid4,uuid5,UUID
    from app.subdomain_naming import validate_unstarted_plan
    run=SimpleNamespace(id=str(uuid4()),phase='prepared',plan={'create_subdomain':'pl1.root22.com'})
    state={'domains':['root22.com']}
    class Database:
        receipt=None
        def get(self,model,key):return self.receipt if self.receipt and self.receipt.id==key else None
    db=Database()
    with pytest.raises(ValueError,match='Обновите план'):validate_unstarted_plan(db,run,state,cross=cross)
    receipt_id=str(uuid5(UUID(run.id),('cross:' if cross else '')+'create_subdomains'))
    db.receipt=SimpleNamespace(id=receipt_id,status='unknown',request_payload={'keep':'exact'})
    validate_unstarted_plan(db,run,state,cross=cross)
    assert db.receipt.status=='unknown' and db.receipt.request_payload=={'keep':'exact'}
    db.receipt=None;run.phase='create_subdomains'
    validate_unstarted_plan(db,run,state,cross=cross)
