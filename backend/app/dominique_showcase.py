"""Native, project-specific open cards for Dominique's Polish showcase."""
from copy import deepcopy
from pathlib import Path

SITE = '6a01bc1c-63f9-451f-8125-76cbd575b5c8'
REPORT = '4ddc2b49-3265-4b13-832d-12b40474c382'
KEY = 'showcase-dominique:original-2026-11-07'
BRANDS = ['Lemon Casino', 'NV Casino', 'Wild Robin', 'Hugo Casino', 'AllySpin',
          'RoboCat', 'Bison Casino', 'GoldSpin', 'WinShark', '1Bet']
CONCEPT = {
    'id': 'dominique-forest-editorial-v1',
    'references': ['mendoza-green-grid-v1', 'wartenweiler-coral-comparison-v1'],
    'differences': [
        'Three-column vertical cards instead of two-column panels or comparison rows',
        'A full-width logo stage and a separate brand masthead',
        'A large cream bonus panel over a compact deposit/licence strip and open payment footer',
    ],
    'palette': ['#103d32', '#fffaf1', '#b58a42'],
    'layout': 'logo / brand / bonus / deposit and licence / payment methods',
}


def template():
    css = (Path(__file__).parent / 'data/site_repairs/dominique-showcase.css').read_text()
    markup = '''<section class="dd-showcase" aria-label="Porównanie kasyn online">
{{#each casinos.pagepilot_standard_1}}<article class="casino-card dd-card">
<div class="dd-logo {{findValueInObjectByKey this "dd_logo_theme" "value" false}}">
{{#if (findValueInObjectByKey this "logo" "id" false)}}<img src="{{findLogo this ../casinos.basic "src"}}" alt="{{findValueInObjectByKey this "brand" "value" false}}" width="210" height="90" loading="lazy">{{/if}}
</div>
<div class="dd-masthead"><h3 class="casino-brand">{{findValueInObjectByKey this "brand" "value" false}}</h3><span class="dd-index" aria-hidden="true"></span></div>
<div class="dd-offer"><span class="dd-label">Bonus powitalny</span><strong class="bonus-value">{{findValueInObjectByKey this "bonus" "value" false}}</strong></div>
<dl class="dd-facts"><div><dt>Minimalny depozyt</dt><dd>{{findValueInObjectByKey this "dd_deposit" "value" false}}</dd></div><div><dt>Licencja</dt><dd>{{findValueInObjectByKey this "dd_license" "value" false}}</dd></div></dl>
<p class="dd-payments"><span class="dd-label">Metody płatności</span>{{findValueInObjectByKey this "dd_payments" "value" false}}</p>
{{#if (findValueInObjectByKey this "rating" "value" false)}}<p class="dd-rating">Ocena: {{findValueInObjectByKey this "rating" "value" false}}</p>{{/if}}
{{#if (findValueInObjectByKey this "actions_html" "value" false)}}<div class="dd-actions">{{{findValueInObjectByKey this "actions_html" "value" false}}}</div>{{/if}}
{{#if (findValueInObjectByKey this "icons_html" "value" false)}}<div class="dd-icons">{{{findValueInObjectByKey this "icons_html" "value" false}}}</div>{{/if}}
</article>{{/each}}</section>'''
    return '<style>\n' + css + '\n</style>' + markup


def prepare(project):
    casinos = deepcopy(project['data']['casinos'])
    cards = casinos['pagepilot_standard_1']
    if len(cards) != len(BRANDS):
        raise ValueError('Card list changed')
    for card, brand in zip(cards, BRANDS):
        values = {field['key']: field.get('value', '') for field in card}
        if values.get('brand') != brand or any(key.startswith('dd_') for key in values):
            raise ValueError('Brand association changed or already transformed')
        fields = {}
        for line in values['conditions'].splitlines():
            key, sep, value = line.partition(': ')
            if not sep or key not in {'Nazwa kasyna', 'Licencja', 'Bonus', 'Minimalny depozyt', 'Metody płatności'} or key in fields:
                raise ValueError('Additional conditions require review')
            fields[key] = value
        if fields.get('Nazwa kasyna') != brand or fields.get('Bonus') != values['bonus']:
            raise ValueError('Offer association changed')
        for key, source in [('dd_deposit', 'Minimalny depozyt'), ('dd_license', 'Licencja'), ('dd_payments', 'Metody płatności')]:
            if not fields.get(source):
                raise ValueError('Missing visible condition: ' + source)
            card.append({'key': key, 'type': 'text', 'value': fields[source]})
        card.append({'key': 'dd_logo_theme', 'type': 'text', 'value': 'dd-logo-light' if brand in {'Wild Robin', 'AllySpin', '1Bet'} else 'dd-logo-dark'})
    before = next(s['data'] for s in project['shortcodes'] if s['name'] == 'casinos-standard-1.hbs')
    if '{{#each casinos.pagepilot_standard_1}}' not in before:
        raise ValueError('Connected source changed')
    return {'casinos_before': deepcopy(project['data']['casinos']), 'casinos_after': casinos,
            'shortcode_before': before, 'shortcode_after': template(), 'concept': CONCEPT}
