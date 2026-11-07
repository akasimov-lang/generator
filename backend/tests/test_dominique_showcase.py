from copy import deepcopy
import pytest
from app.dominique_showcase import BRANDS, prepare


def project():
    cards = []
    for brand in BRANDS:
        bonus = '100% do 150 zł'
        cards.append([
            {'key': 'brand', 'type': 'text', 'value': brand},
            {'key': 'bonus', 'type': 'text', 'value': bonus},
            {'key': 'conditions', 'type': 'text', 'value': f'Nazwa kasyna: {brand}\nLicencja: Curacao\nBonus: {bonus}\nMinimalny depozyt: 50 zł\nMetody płatności: BLIK, Visa'},
            {'key': 'rating', 'type': 'text', 'value': ''},
            {'key': 'actions_html', 'type': 'text', 'value': '<a href="/go/existing">Oferta</a>'},
        ])
    return {'data': {'casinos': {'basic': [{'key': 'logo', 'data': []}], 'pagepilot_standard_1': cards,
                               'unconnected': [{'keep': True}]}},
            'shortcodes': [{'name': 'casinos-standard-1.hbs', 'data': '{{#each casinos.pagepilot_standard_1}}old{{/each}}'}]}


def test_preserves_offers_actions_and_unconnected_cards_while_exposing_terms():
    before = project(); snapshot = deepcopy(before)
    result = prepare(before)
    assert before == snapshot
    assert result['casinos_after']['unconnected'] == before['data']['casinos']['unconnected']
    for old, new in zip(before['data']['casinos']['pagepilot_standard_1'], result['casinos_after']['pagepilot_standard_1']):
        assert new[:len(old)] == old
        values = {f['key']: f.get('value') for f in new}
        assert values['dd_deposit'] == '50 zł'
        assert values['dd_license'] == 'Curacao'
        assert values['dd_payments'] == 'BLIK, Visa'
    assert '<details' not in result['shortcode_after']


def test_unknown_terms_are_not_silently_hidden():
    source = project()
    source['data']['casinos']['pagepilot_standard_1'][0][2]['value'] += '\nWager: 40x'
    with pytest.raises(ValueError, match='Additional conditions'):
        prepare(source)


def test_mismatched_brand_offer_is_rejected():
    source = project()
    source['data']['casinos']['pagepilot_standard_1'][0][1]['value'] = 'Changed offer'
    with pytest.raises(ValueError, match='Offer association'):
        prepare(source)
