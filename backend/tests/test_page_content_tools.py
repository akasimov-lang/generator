import copy
import pytest
from app.page_content_tools import interlink, validate_rewrite, targets


def test_second_brand_occurrence_respects_links_and_preserves_other_markup():
    content={'version':'2.1','blocks':[
        {'type':'header','data':{'level':1,'text':'BetOnRed casino'}},
        {'type':'paragraph','data':{'text':'Review <strong>Bet-On-Red</strong> today. <a href="https://else.test">Other</a>'}}]}
    before=copy.deepcopy(content)
    result,_,changed=interlink(content,'BetOnRed')
    assert changed and result['blocks'][1]['data']['text']=='Review <strong><a href="/">Bet-On-Red</a></strong> today. <a href="https://else.test">Other</a>'
    assert content==before
    same,_,changed=interlink(result,'BetOnRed')
    assert not changed and same==result


def test_interlink_ignores_attributes_script_and_non_matching_words():
    content={'blocks':[{'type':'paragraph','data':{'text':'<span title="Brand">Branded</span> Brand\nBrand <script>Brand</script>'}}]}
    result,_,changed=interlink(content,'Brand')
    assert changed and result['blocks'][0]['data']['text']=='<span title="Brand">Branded</span> Brand\n<a href="/">Brand</a> <script>Brand</script>'


def test_rewrite_guards_facts_and_structure():
    before='Brand: <strong>100</strong> EUR, <a href="/bonus/">terms</a>.'
    assert validate_rewrite(before,'Brand offers <strong>100</strong> EUR; <a href="/bonus/">conditions</a>.','Brand')
    for revised in [before.replace('100','200'),before.replace('/bonus/','https://else.test'),before.replace('Brand','Other'),before+'<!-- AI -->']:
        with pytest.raises(ValueError): validate_rewrite(before,revised,'Brand')


def test_emoji_targeting_keeps_table_header_and_existing_emoji():
    content={'blocks':[{'type':'table','data':{'withHeadings':True,'content':[['Heading','Value'],['Deposit','10'],['🎁 Bonus','100']]}}]}
    assert targets(content,'emoji')==[{'block':0,'row':1,'text':'Deposit','context':['Deposit','10']}]
