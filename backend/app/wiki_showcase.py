"""Open, project-specific comparison tickets for wiki-fame.com.

The original native records stay intact. Presentation fields are extracted only
when their entire source sentence matches, including the particular offer label.
"""
from copy import deepcopy
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import quote, urlsplit, urlunsplit

SITE = '8ef0b46b-bb53-4130-aed5-b624ccc834f5'
KEY = 'site-template-repair:wiki-fame-showcase-2026-11-07'
LEDGER = 'showcase-wiki:2026-11-07'
REPORT = '4ddc2b49-3265-4b13-832d-12b40474c382'
CONCEPT = {
    'id': 'wiki-midnight-ticket-v1',
    'references': ['dominique-forest-editorial-v1', 'wartenweiler-coral-comparison-v1'],
    'differences': [
        'Two-column comparison tickets, followed by a separate three-card discovery group, instead of a three-column logo-stage grid or full-width rows',
        'Brand and numeric rating form the masthead; an inset orange bonus band is the main visual focus',
        'Dark navy surfaces with an orange edge and open feature lists or labelled facts replace cream panels and deposit/licence strips',
    ],
    'palette': ['#111b2b', '#ff8b38', '#f4f7fc'],
    'layout': 'brand and rating / exact bonus label and value / open features / existing action',
}

FEATURED = [
    ('Betano Casino', 'Populární', 'Synot • Apollo • Pragmatic Play', 'Uvítací bonus',
     ['Přes 1 500 online automatů', 'Ověření přes Bank ID', 'Bezplatný demo režim']),
    ('Tipsport Vegas', 'Rychlá platba', 'Kajot • Synot • NetEnt • Yggdrasil', 'Bonus za registraci',
     ['Bleskové výplaty výher', 'Denní Vegas turnaje', 'Všechny automaty v demu']),
    ('Synot Tip', 'Česká klasika', 'Synot Games • Kajot • Playson', 'Vstupní bonus',
     ['Exkluzivní domácí tituly', 'Demo i bez přihlášení', 'Licencovaný online poker']),
    ('MerkurXtip', 'Velké jackpoty', 'Amusnet • Synot • CT Interactive', 'Bonus za vklad',
     ['Moderní a rychlé rozhraní', 'Špičkové řazení automatů', 'Štědré síťové turnaje']),
]
DISCOVERY = [
    ('Kingsbet', 'Vstupní bonus', '600+ nových 3D slotů', 'Live casino s krupiéry', 'Plná licence MFČR'),
    ('MerkurXtip', 'Bonus za registraci', '500+ her včetně CZ klasiky', 'Turnaje o 1 000 000+ Kč', 'Plná licence MFČR'),
    ('Tokyo Casino', 'Vstupní bonus', '300+ asijských a ovocných her', 'Svižné mobilní rozhraní', 'Plná licence MFČR'),
]


def template(group):
    if group not in (1, 2):
        raise ValueError('Unsupported connected group')
    css = (Path(__file__).parent / 'data/site_repairs/wiki-showcase.css').read_text()
    facts = '''<p class="wf-providers">{{findValueInObjectByKey this "wf_providers" "value" false}}</p>
<ul class="wf-features"><li>{{findValueInObjectByKey this "wf_feature_1" "value" false}}</li><li>{{findValueInObjectByKey this "wf_feature_2" "value" false}}</li><li>{{findValueInObjectByKey this "wf_feature_3" "value" false}}</li></ul>''' if group == 1 else '''<dl class="wf-facts"><div><dt>Automaty</dt><dd>{{findValueInObjectByKey this "wf_games" "value" false}}</dd></div><div><dt>Výhoda</dt><dd>{{findValueInObjectByKey this "wf_advantage" "value" false}}</dd></div><div><dt>Licence</dt><dd>{{findValueInObjectByKey this "wf_license" "value" false}}</dd></div></dl>'''
    markup = '''<section class="wf-showcase wf-group-GROUP" aria-label="Přehled online casin">
{{#each casinos.pagepilot_standard_GROUP}}<article class="casino-card wf-card">
<header class="wf-masthead"><div><span class="wf-kicker">{{findValueInObjectByKey this "wf_kicker" "value" false}}</span><h3 class="casino-brand">{{findValueInObjectByKey this "brand" "value" false}}</h3></div>
{{#if (findValueInObjectByKey this "rating" "value" false)}}<div class="wf-score"><span aria-hidden="true">★</span><strong class="casino-rating">{{findValueInObjectByKey this "rating" "value" false}}</strong><small>Hodnocení</small></div>{{/if}}</header>
{{#if (findValueInObjectByKey this "logo" "id" false)}}<div class="wf-logo"><img src="{{findLogo this ../casinos.basic "src"}}" alt="{{findValueInObjectByKey this "brand" "value" false}}" loading="lazy"></div>{{/if}}
<div class="wf-offer"><span>{{findValueInObjectByKey this "wf_bonus_label" "value" false}}</span><strong class="bonus-value">{{findValueInObjectByKey this "bonus" "value" false}}</strong></div>
FACTS
<footer class="wf-actions">{{{findValueInObjectByKey this "actions_html" "value" false}}}</footer>
{{#if (findValueInObjectByKey this "icons_html" "value" false)}}<div class="wf-icons">{{{findValueInObjectByKey this "icons_html" "value" false}}}</div>{{/if}}
</article>{{/each}}</section>'''.replace('GROUP', str(group)).replace('FACTS', facts)
    return '<style>\n' + css + '\n</style>' + markup


def prepare(project):
    if (project.get('settings') or {}).get('canon', '').removeprefix('www.') != 'wiki-fame.com':
        raise ValueError('Current Main changed')
    casinos = deepcopy(project['data']['casinos'])
    groups = [('pagepilot_standard_1', FEATURED), ('pagepilot_standard_2', DISCOVERY)]
    for group, specs in groups:
        cards = casinos[group]
        if len(cards) != len(specs):
            raise ValueError('Card list changed: ' + group)
        for card, spec in zip(cards, specs):
            values = {field['key']: field.get('value', '') for field in card}
            brand = spec[0]
            if values.get('brand') != brand or any(key.startswith('wf_') for key in values):
                raise ValueError('Brand association changed or presentation already prepared')
            if group.endswith('_1'):
                _, kicker, providers, label, features = spec
                expected = f'{kicker} {brand} {providers} {label} {values["bonus"]} {" ".join(features)} Hrát nyní'
                added = {'wf_kicker': kicker, 'wf_providers': providers, 'wf_bonus_label': label,
                         **{f'wf_feature_{i}': feature for i, feature in enumerate(features, 1)}}
            else:
                _, label, games, advantage, license_name = spec
                expected = f'Nové {brand} {label} {values["bonus"]} Automaty: {games} Výhoda: {advantage} Licence: {license_name}'
                added = {'wf_kicker': 'Nové', 'wf_bonus_label': label, 'wf_games': games,
                         'wf_advantage': advantage, 'wf_license': license_name}
            if values.get('conditions') != expected:
                raise ValueError('Conditions changed; review exact offer before publishing: ' + brand)
            card.extend({'key': key, 'type': 'text', 'value': value} for key, value in added.items())
    templates = []
    for i in (1, 2):
        filename = f'casinos-standard-{i}.hbs'
        before = next(s['data'] for s in project['shortcodes'] if s['name'] == filename)
        if '{{#each casinos.pagepilot_standard_' + str(i) + '}}' not in before:
            raise ValueError('Connected source changed: ' + filename)
        templates.append({'name': filename, 'before': before, 'after': template(i)})
    return {'casinos_before': deepcopy(project['data']['casinos']), 'casinos_after': casinos,
            'templates': templates, 'concept': deepcopy(CONCEPT)}


def prepare_tracking(project):
    """Bind the seven existing actions to this project's saved Webdev tracker.

    Called only for the separately authorized tracking repair. Original offer
    records and action bodies stay intact; no affiliate URL is inferred.
    """
    settings = project.get('settings') or {}
    if settings.get('canon', '').removeprefix('www.') != 'wiki-fame.com':
        raise ValueError('Current Main changed')
    tracking = str(settings.get('trackLink') or '').strip()
    parts = urlsplit(tracking)
    if parts.scheme not in ('https', 'http') or not parts.hostname or parts.username or parts.password:
        raise ValueError('A saved Webdev tracking URL is required')
    if any(char in tracking for char in '\r\n{}'):
        raise ValueError('Unresolved or invalid tracking URL')
    casinos = deepcopy(project['data']['casinos'])
    for group, specs in (('pagepilot_standard_1', FEATURED), ('pagepilot_standard_2', DISCOVERY)):
        cards = casinos[group]
        if len(cards) != len(specs):
            raise ValueError('Card list changed: ' + group)
        for card, spec in zip(cards, specs):
            values = {field['key']: field.get('value', '') for field in card}
            if values.get('brand') != spec[0]:
                raise ValueError('Brand association changed')
            action = str(values.get('actions_html') or '')
            match = re.fullmatch(r'\s*(<(a|button)\b[^>]*>)(.*?)</\2>\s*', action, re.S)
            if not match or re.search(r'<(?:a|button)\b', match[3], re.I):
                raise ValueError('Action structure changed: ' + spec[0])

            class StartTag(HTMLParser):
                def handle_starttag(self, tag, attrs):
                    self.attrs = attrs

            parser = StartTag(convert_charrefs=True)
            parser.feed(match[1])
            attrs = dict(parser.attrs)
            if any(key.startswith('on') for key in attrs):
                raise ValueError('Action handler requires review: ' + spec[0])
            split = attrs.get('data-split')
            target = tracking
            if split:
                query = parts.query + ('&' if parts.query else '') + 'split=' + quote(split, safe='')
                target = urlunsplit(parts._replace(query=query))
            if match[2] == 'a' and attrs.get('href') not in ('{{offerUrl}}', target):
                raise ValueError('Existing action URL requires review: ' + spec[0])
            attrs.pop('type', None)
            attrs['href'] = target
            attrs['rel'] = ' '.join(dict.fromkeys((attrs.get('rel') or '').split() + ['nofollow', 'sponsored']))
            opening = '<a' + ''.join(' ' + key + ('' if val is None else '="' + escape(val, quote=True) + '"') for key, val in attrs.items()) + '>'
            updated = opening + match[3] + '</a>'
            next(field for field in card if field['key'] == 'actions_html')['value'] = updated
    return {'casinos_before': deepcopy(project['data']['casinos']), 'casinos_after': casinos,
            'tracking_source': 'settings.trackLink', 'actions': 7}
