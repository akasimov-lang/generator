"""Point repair for the connected native Mendoza showcase; preserve offers/tracking."""
from copy import deepcopy
from pathlib import Path
import re
from app.showcase_management import Tree

SITE = '22625c45-7d3c-418b-9dbb-8b72418e88f6'
REPORT = '4ddc2b49-3265-4b13-832d-12b40474c382'
KEY = 'showcase-mendoza:original-2026-11-06'
BRANDS = ['Codere', 'BC.Game', 'bet365', 'Melbet', 'Paripesa', 'CBet', 'Betway']


def template(groups):
    def value(key):
        return '{{findValueInObjectByKey this "' + key + '" "value" false}}'
    card = '''<article class="casino-card md-card">
<div class="md-top"><div class="md-brand">
<div class="md-logo __LOGO_CLASS__">{{#if (findValueInObjectByKey this "logo" "id" false)}}<img src="{{findLogo this ../casinos.basic "src"}}" alt="__BRAND__" loading="lazy" width="160" height="60">{{else}}<strong class="casino-brand">__BRAND__</strong>{{/if}}</div>
<div class="md-rating" aria-label="Valoración: __RATING__ de 5"><span class="md-stars" style="--md-score:__RATING__" aria-hidden="true">★★★★★</span><span>__RATING__ / 5</span></div>
</div><dl class="md-stats"><div><dt>Depósito mínimo</dt><dd>__MIN__</dd></div><div><dt>Límite máximo de pago</dt><dd>__MAX__</dd></div></dl></div>
<div class="md-offer-row"><div><span class="md-label">Bono de bienvenida</span><strong class="bonus-value">__BONUS__</strong></div><div class="md-actions">{{{findValueInObjectByKey this "actions_html" "value" false}}}</div></div>
<p class="md-payments"><span>Métodos de pago</span>__PAYMENTS__</p>
</article>'''
    for token, key in [('BRAND','brand'),('RATING','rating'),('MIN','minDep'),('MAX','maxPayout'),('BONUS','bonus'),('PAYMENTS','paymentMethods')]:
        card = card.replace('__' + token + '__', value(key))
    css = (Path(__file__).parent / 'data/site_repairs/mendoza-showcase.css').read_text()
    cards = []
    for group, dark in groups:
        if not re.fullmatch(r'pagepilot_standard_[1-7]', group):
            raise ValueError('Unexpected group')
        cards.append('{{#each casinos.' + group + '}}' + card.replace('__LOGO_CLASS__', 'md-logo-dark' if dark else '') + '{{/each}}')
    return '<style>\n' + css + '\n</style><section class="md-showcase" aria-label="Casinos y bonos">' + '\n'.join(cards) + '</section>'


def prepare(project):
    """Read exact old deposits/payment limits; no bonus/rating/action changes."""
    before = next(s['data'] for s in project['shortcodes'] if s['name'] == 'casinos.hbs')
    wrappers = [n for n in Tree(before).root.walk() if 'casinos-wrapper' in n.classes]
    if len(wrappers) != 7:
        raise ValueError('Showcase source changed; expected seven wrappers')
    casinos = deepcopy(project['data']['casinos'])
    groups = []
    for i, (wrapper, brand) in enumerate(zip(wrappers, BRANDS), 1):
        group = 'pagepilot_standard_' + str(i)
        if '{{> casinos-standard-' + str(i) + '}}' not in wrapper.text():
            raise ValueError('Offer association changed')
        if len(casinos[group]) != 1:
            raise ValueError('Card count changed')
        record = casinos[group][0]
        values = {f['key']: f.get('value') for f in record}
        if values['brand'] != brand or not re.fullmatch(r'[0-5](?:\.\d+)?', values['rating']):
            raise ValueError('Brand or rating requires review')
        # The legacy details contain only a duplicate of already visible fields.
        expected = f"{brand} {values['rating']}/5 Bono de bienvenida {values['bonus']} Más información"
        if values['conditions'] != expected:
            raise ValueError('Additional conditions must be shown, not discarded')
        for cls, field in [('min-dep','minDep'),('max-dep','maxPayout'),('info-deposit','paymentMethods')]:
            node = wrapper.first({cls})
            value = node.first(tags={'span'}).text() if node else None
            if not value or any(f['key'] == field for f in record):
                raise ValueError('Offer fields changed')
            if field == 'paymentMethods':
                value = value.replace('Bank transfer', 'Transferencia bancaria').replace('Transferencias Bancarias', 'Transferencias bancarias')
                value = re.sub(r',\s*', ', ', value)
            record.append({'key':field,'type':'text','value':value})
        groups.append((group, brand in {'BC.Game','Melbet','CBet','Betway'}))
    return {'shortcode_before':before, 'shortcode_after':template(groups),
            'casinos_before':deepcopy(project['data']['casinos']), 'casinos_after':casinos}
