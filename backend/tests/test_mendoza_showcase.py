from copy import deepcopy
import pytest
from app.mendoza_showcase import prepare, BRANDS


def fixture():
    groups={'basic':[{'key':'logo','type':'gallery','data':[{'id':1,'src':'/old.png'}]}]}
    wrappers=[]
    for i,brand in enumerate(BRANDS,1):
        bonus=f'100% hasta {i}000 ARS'
        groups[f'pagepilot_standard_{i}']=[[{'key':k,'type':'text','value':v} for k,v in {
            'brand':brand,'bonus':bonus,'rating':'4','conditions':f'{brand} 4/5 Bono de bienvenida {bonus} Más información',
            'actions_html':f'<button data-split="brand-{i}">Obtener bonificación</button>'}.items()]]
        wrappers.append('<div class="casinos-wrapper">{{> casinos-standard-'+str(i)+'}}'+f'<div class="min-dep"><span>{i}00 ARS</span></div><div class="max-dep"><span>{i}00000 ARS</span></div><div class="info-deposit"><span>Visa, Bank transfer</span></div></div>')
    return {'data':{'casinos':groups},'shortcodes':[{'name':'casinos.hbs','data':''.join(wrappers)}]}


def test_mendoza_preserves_offer_rating_actions_and_gallery_and_associates_visible_limits():
    project=fixture();original=deepcopy(project);plan=prepare(project)
    assert project==original
    assert plan['casinos_after']['basic']==original['data']['casinos']['basic']
    for i in range(1,8):
        old=original['data']['casinos'][f'pagepilot_standard_{i}'][0]
        new=plan['casinos_after'][f'pagepilot_standard_{i}'][0]
        assert new[:len(old)]==old
        values={f['key']:f['value'] for f in new}
        assert values['minDep']==f'{i}00 ARS'
        assert values['maxPayout']==f'{i}00000 ARS'
        assert values['paymentMethods']=='Visa, Transferencia bancaria'
    assert '<details' not in plan['shortcode_after']
    assert 'Más información' not in plan['shortcode_after']
    assert plan['shortcode_after'].count('class="casino-card md-card"')==7


def test_mendoza_refuses_to_hide_additional_conditions():
    project=fixture()
    project['data']['casinos']['pagepilot_standard_1'][0][3]['value']+=' Depósito necesario.'
    with pytest.raises(ValueError,match='Additional conditions'):
        prepare(project)
