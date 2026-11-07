from copy import deepcopy

import pytest

from app.wiki_showcase import prepare, prepare_tracking, template


def project():
    source = [
        ('Betano Casino', '600 FREE SPINŮ', '4.7', 'Populární Betano Casino Synot • Apollo • Pragmatic Play Uvítací bonus 600 FREE SPINŮ Přes 1 500 online automatů Ověření přes Bank ID Bezplatný demo režim Hrát nyní'),
        ('Tipsport Vegas', '300 Kč ZDARMA', '4.6', 'Rychlá platba Tipsport Vegas Kajot • Synot • NetEnt • Yggdrasil Bonus za registraci 300 Kč ZDARMA Bleskové výplaty výher Denní Vegas turnaje Všechny automaty v demu Hrát nyní'),
        ('Synot Tip', '500,- BEZ RIZIKA', '4.4', 'Česká klasika Synot Tip Synot Games • Kajot • Playson Vstupní bonus 500,- BEZ RIZIKA Exkluzivní domácí tituly Demo i bez přihlášení Licencovaný online poker Hrát nyní'),
        ('MerkurXtip', '333 FREE SPINŮ', '4.1', 'Velké jackpoty MerkurXtip Amusnet • Synot • CT Interactive Bonus za vklad 333 FREE SPINŮ Moderní a rychlé rozhraní Špičkové řazení automatů Štědré síťové turnaje Hrát nyní'),
        ('Kingsbet', '555 FREE SPINŮ', '3', 'Nové Kingsbet Vstupní bonus 555 FREE SPINŮ Automaty: 600+ nových 3D slotů Výhoda: Live casino s krupiéry Licence: Plná licence MFČR'),
        ('MerkurXtip', '333 FREE SPINŮ', '4.1', 'Nové MerkurXtip Bonus za registraci 333 FREE SPINŮ Automaty: 500+ her včetně CZ klasiky Výhoda: Turnaje o 1 000 000+ Kč Licence: Plná licence MFČR'),
        ('Tokyo Casino', '100% do 10 000 Kč', '4', 'Nové Tokyo Casino Vstupní bonus 100% do 10 000 Kč Automaty: 300+ asijských a ovocných her Výhoda: Svižné mobilní rozhraní Licence: Plná licence MFČR'),
    ]
    cards = [[{'key': key, 'type': 'text', 'value': value} for key, value in zip(('brand', 'bonus', 'rating', 'conditions'), row)] + [{'key': 'actions_html', 'type': 'text', 'value': '<a href="{{offerUrl}}" data-split="a" rel="nofollow sponsored">Hrát nyní</a>'}] for row in source]
    return {'settings': {'canon': 'wiki-fame.com'}, 'data': {'casinos': {
        'pagepilot_standard_1': cards[:4], 'pagepilot_standard_2': cards[4:],
        'basic': [{'key': 'logo', 'type': 'gallery', 'data': []}],
        'unused': [[{'key': 'brand', 'value': 'Untouched'}]],
    }}, 'shortcodes': [{'name': f'casinos-standard-{i}.hbs', 'data': '{{#each casinos.pagepilot_standard_' + str(i) + '}}old{{/each}}'} for i in (1, 2)]}


def value(card, key):
    return next(field['value'] for field in card if field['key'] == key)


def test_preparation_preserves_original_cards_links_and_distinct_merkur_offers():
    original = project()
    snapshot = deepcopy(original)
    plan = prepare(original)
    assert original == snapshot
    assert plan['casinos_after']['basic'] == snapshot['data']['casinos']['basic']
    assert plan['casinos_after']['unused'] == snapshot['data']['casinos']['unused']
    for group in ('pagepilot_standard_1', 'pagepilot_standard_2'):
        assert len(plan['casinos_after'][group]) == len(snapshot['data']['casinos'][group])
        for old, new in zip(snapshot['data']['casinos'][group], plan['casinos_after'][group]):
            assert new[:len(old)] == old
    assert value(plan['casinos_after']['pagepilot_standard_1'][3], 'wf_bonus_label') == 'Bonus za vklad'
    assert value(plan['casinos_after']['pagepilot_standard_2'][1], 'wf_bonus_label') == 'Bonus za registraci'
    assert value(plan['casinos_after']['pagepilot_standard_2'][1], 'wf_advantage') == 'Turnaje o 1 000 000+ Kč'


def test_unrecognized_condition_is_not_silently_lost_during_formatting():
    original = project()
    card = original['data']['casinos']['pagepilot_standard_1'][0]
    next(field for field in card if field['key'] == 'conditions')['value'] += ' Pouze pro nové hráče.'
    with pytest.raises(ValueError, match='Conditions changed'):
        prepare(original)


def test_connected_group_and_main_are_checked_before_rewriting():
    original = project()
    original['settings']['canon'] = 'other.example'
    with pytest.raises(ValueError, match='Main changed'):
        prepare(original)
    original = project()
    original['shortcodes'][0]['data'] = '{{#each casinos.some_other_group}}{{/each}}'
    with pytest.raises(ValueError, match='Connected source changed'):
        prepare(original)


def test_template_renders_each_offer_once_and_keeps_conditions_open():
    markup = template(1)
    assert '<details' not in markup and '<summary' not in markup
    assert markup.count('this "bonus" "value"') == 1
    assert 'this "conditions" "value"' not in markup
    assert 'this "wf_feature_3" "value"' in markup
    assert '{{{findValueInObjectByKey this "actions_html" "value" false}}}' in markup
    assert 'this "rating" "value"' in markup
    assert '/5' not in markup
    assert 'this "wf_license" "value"' in template(2)


def test_tracking_uses_saved_project_link_and_preserves_offer_fields():
    original = project()
    original['settings']['trackLink'] = 'https://tracker.example/click?key=project-test'
    card = original['data']['casinos']['pagepilot_standard_2'][0]
    next(field for field in card if field['key'] == 'actions_html')['value'] = '<button class="button" type="button" data-goal="register">Otevřít casino</button>'
    snapshot = deepcopy(original)
    plan = prepare_tracking(original)
    assert original == snapshot
    assert plan['actions'] == 7
    assert plan['casinos_after']['basic'] == snapshot['data']['casinos']['basic']
    assert plan['casinos_after']['unused'] == snapshot['data']['casinos']['unused']
    for group in ('pagepilot_standard_1', 'pagepilot_standard_2'):
        for before, after in zip(snapshot['data']['casinos'][group], plan['casinos_after'][group]):
            assert [f for f in before if f['key'] != 'actions_html'] == [f for f in after if f['key'] != 'actions_html']
            assert '{{offerUrl}}' not in value(after, 'actions_html')
            assert '<button' not in value(after, 'actions_html')
    action = value(plan['casinos_after']['pagepilot_standard_1'][0], 'actions_html')
    assert 'href="https://tracker.example/click?key=project-test&amp;split=a"' in action
    assert 'data-split="a"' in action and '>Hrát nyní</a>' in action
    button_action = value(plan['casinos_after']['pagepilot_standard_2'][0], 'actions_html')
    assert 'href="https://tracker.example/click?key=project-test"' in button_action
    assert 'split=null' not in button_action and 'data-goal="register"' in button_action
    assert prepare_tracking({**original, 'data': {'casinos': plan['casinos_after']}})['casinos_after'] == plan['casinos_after']


def test_tracking_preserves_svg_and_encodes_existing_split():
    original = project()
    original['settings']['trackLink'] = 'https://tracker.example/click?key=project-test#fragment'
    card = original['data']['casinos']['pagepilot_standard_1'][0]
    next(field for field in card if field['key'] == 'actions_html')['value'] = '<a href="{{offerUrl}}" data-split="bonus &amp; register">Hrát <svg><path d="M0 0" /></svg></a>'
    action = value(prepare_tracking(original)['casinos_after']['pagepilot_standard_1'][0], 'actions_html')
    assert 'split=bonus%20%26%20register#fragment' in action
    assert 'Hrát <svg><path d="M0 0" /></svg>' in action


def test_tracking_requires_existing_project_link():
    with pytest.raises(ValueError, match='saved Webdev tracking URL'):
        prepare_tracking(project())


def test_tracking_refuses_to_overwrite_unrelated_action():
    original = project()
    original['settings']['trackLink'] = 'https://tracker.example/click'
    card = original['data']['casinos']['pagepilot_standard_1'][0]
    next(field for field in card if field['key'] == 'actions_html')['value'] = '<a href="https://other.example/offer">Hrát</a>'
    with pytest.raises(ValueError, match='Existing action URL requires review'):
        prepare_tracking(original)
