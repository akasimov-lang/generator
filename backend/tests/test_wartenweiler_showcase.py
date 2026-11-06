from copy import deepcopy
import pytest
from app.wartenweiler_showcase import prepare


def fixture():
    casinos={}
    for i,n in [(1,5),(2,10)]:
        casinos[f'pagepilot_standard_{i}']=[[{'key':'brand','value':f'Brand {j}'},{'key':'bonus','value':'100 €'},{'key':'rating','value':''},
            {'key':'conditions','value':f'Casino: Brand {j}\nBonusangebot: 100 €\nLizenz: Existing licence\nBesonderheiten: Existing terms.'},
            {'key':'actions_html','value':'<a data-split="original" href="/go">Bonus</a>'}] for j in range(n)]
    return {'data':{'casinos':casinos},'shortcodes':[{'name':f'casinos-standard-{i}.hbs','data':'{{#each casinos.pagepilot_standard_'+str(i)+'}}old{{/each}}'} for i in (1,2)]}


def test_open_comparison_preserves_offers_links_and_all_conditions():
    project=fixture();before=deepcopy(project);plan=prepare(project)
    assert project==before
    for group,cards in before['data']['casinos'].items():
        for old,new in zip(cards,plan['casinos_after'][group]):
            assert new[:len(old)]==old
            assert new[-2:]==[{'key':'ww_license','type':'text','value':'Existing licence'},{'key':'ww_features','type':'text','value':'Existing terms.'}]
    assert all('<details' not in s['after'] and 'ww_features' in s['after'] and 'ww_license' in s['after'] for s in plan['shortcodes'].values())


def test_unrecognized_condition_prevents_publication():
    project=fixture();project['data']['casinos']['pagepilot_standard_1'][0][3]['value']+='\nWithdrawal condition: preserve me'
    with pytest.raises(ValueError,match='Unknown condition'):prepare(project)
