from copy import deepcopy
from types import SimpleNamespace
import pytest
from app import casino_review_policy as policy
from app.brand_content_buttons import apply_brand_content_buttons, generation_instruction
from app.structure_home_link import place_home_link


def test_review_contract_overrides_saved_generic_button_wording():
    spec=generation_instruction(None, {'content_kind':'casino_review','casino_brand':'Tokyo Casino'}, 'cs','Review')
    assert 'Tokyo Casino — přihlášení' in spec
    assert 'payment' in spec and 'customer support' in spec and 'at least 5' in spec
    assert policy.login_label('Brand','pl-PL')=='Brand — logowanie'
    assert policy.login_label('Brand','xx') is None


def test_review_button_before_table_is_styled_and_stable_on_retry():
    source={'generation_meta':{'content_button':{'brand':'Tokyo','text':'Tokyo — přihlášení'}},'pages':[{'slug':'/review/','content':{'blocks':[
        {'id':'p','type':'paragraph','data':{'text':'Whole paragraph'}},
        {'id':'t','type':'table','data':{'content':[['Field','Value']]*6}}]}}]}
    original=deepcopy(source)
    context={'content_kind':'casino_review','casino_brand':'Tokyo','review_button_placement':'before_table'}
    result=apply_brand_content_buttons(source,None,context)
    rows=result['pages'][0]['content']['blocks']
    assert [b['type'] for b in rows]==['paragraph','code','button','code','table']
    assert '.pp-casino-review-action' in rows[1]['data']['code']
    assert rows[-1]==original['pages'][0]['content']['blocks'][-1]
    assert apply_brand_content_buttons(result,None,context)==result and source==original


def test_random_review_position_uses_whole_blocks(monkeypatch):
    selected=[]
    monkeypatch.setattr(policy.secrets,'choice',lambda choices: selected.extend(choices) or choices[-1])
    assert policy.review_index([{'type':'header'},{'type':'paragraph'},{'type':'list'},{'type':'table'}],{})==4
    assert selected==[2,3,4]


def test_missing_or_placeholder_table_cannot_pass_review_validation():
    with pytest.raises(ValueError,match='таблица'):
        policy.validate_table({'content':{'blocks':[]}})
    policy.validate_table({'content':{'blocks':[{'type':'table','data':{'content':[['Key','Value']]*6}}]}})


def test_contextual_home_link_preserves_breadcrumbs_and_template_links():
    nav={'type':'code','data':{'code':'<nav aria-label="Breadcrumb"><a href="/">Home</a> › Review</nav>'}}
    raw={'type':'raw','data':{'html':'<a href="/">Site navigation</a>'}}
    source={'blocks':[nav,raw,{'type':'paragraph','data':{'text':'Intro words about a casino and its games.'}},
        {'type':'paragraph','data':{'text':'More details <a href="/">casino</a> to explore.'}}]}
    result=place_home_link(source,'casino','example.com','/review/')
    assert result['blocks'][:2]==[nav,raw]
    assert sum(b['data']['text'].count('href="/"') for b in result['blocks'] if b['type']=='paragraph')==1
    assert place_home_link(result,'casino','example.com','/review/')==result
