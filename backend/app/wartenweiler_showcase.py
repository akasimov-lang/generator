"""A project-specific open comparison layout for Wartenweiler's native cards."""
from copy import deepcopy
from pathlib import Path

SITE='e34e6f4a-e814-4c74-b0b9-194ae226146a'
KEY='showcase-wartenweiler:original-2026-11-06'
CONCEPT={'id':'wartenweiler-coral-comparison-v1','reference':'mendoza-green-grid-v1',
 'differences':['Full-width comparison rows instead of a two-column card grid',
 'Oversized outline sequence numbers and brand typography instead of logo tiles',
 'Coral bonus panel with a separate licence/features column instead of deposit/payment panels'],
 'palette':['#2d2a2c','#bf4c42','#fffdf8'],'layout':'number / brand / bonus / open terms'}


def template(group):
    if group not in {'pagepilot_standard_1','pagepilot_standard_2'}:raise ValueError('Unexpected group')
    css=(Path(__file__).parent/'data/site_repairs/wartenweiler-showcase.css').read_text()
    return '<style>'+css+'</style>'+'''<section class="ww-showcase" aria-label="Casino-Vergleich">{{#each casinos.__GROUP__}}<article class="casino-card ww-card">
<div class="ww-identity"><span class="ww-number" aria-hidden="true"></span><div><span class="ww-eyebrow">Online Casino</span><strong class="casino-brand ww-brand">{{findValueInObjectByKey this "brand" "value" false}}</strong>{{#if (findValueInObjectByKey this "rating" "value" false)}}<span class="ww-rating">Bewertung: {{findValueInObjectByKey this "rating" "value" false}}</span>{{/if}}</div></div>
<div class="ww-bonus"><span class="ww-eyebrow">Willkommensbonus</span><strong class="bonus-value">{{findValueInObjectByKey this "bonus" "value" false}}</strong>{{#if (findValueInObjectByKey this "actions_html" "value" false)}}<div class="ww-actions">{{{findValueInObjectByKey this "actions_html" "value" false}}}</div>{{/if}}</div>
<div class="ww-facts">{{#if (findValueInObjectByKey this "ww_license" "value" false)}}<div class="ww-license"><span>Lizenz</span><strong>{{findValueInObjectByKey this "ww_license" "value" false}}</strong></div>{{/if}}<span class="ww-eyebrow">Auf einen Blick</span><p>{{findValueInObjectByKey this "ww_features" "value" false}}</p>{{#if (findValueInObjectByKey this "icons_html" "value" false)}}<div class="ww-icons">{{{findValueInObjectByKey this "icons_html" "value" false}}}</div>{{/if}}</div>
</article>{{/each}}</section>'''.replace('__GROUP__',group)


def prepare(project):
    casinos=deepcopy(project['data']['casinos']);shortcodes={}
    for group,count in [('pagepilot_standard_1',5),('pagepilot_standard_2',10)]:
        if len(casinos[group])!=count:raise ValueError('Card list changed')
        for card in casinos[group]:
            values={f['key']:f.get('value','') for f in card}
            if any(f['key'].startswith('ww_') for f in card):raise ValueError('Already transformed')
            lines=values['conditions'].splitlines()
            if lines[:2]!=['Casino: '+values['brand'],'Bonusangebot: '+values['bonus']]:raise ValueError('Offer association changed')
            fields={}
            for line in lines[2:]:
                key,sep,value=line.partition(': ')
                if not sep or key not in {'Lizenz','Besonderheiten','Bonus-Highlights'} or key in fields:raise ValueError('Unknown condition must be reviewed')
                fields[key]=value
            features=fields.get('Besonderheiten',fields.get('Bonus-Highlights'))
            if not features:raise ValueError('Missing visible conditions')
            card.extend([{'key':'ww_license','type':'text','value':fields.get('Lizenz','')},{'key':'ww_features','type':'text','value':features}])
        filename='casinos-standard-'+group.rsplit('_',1)[1]+'.hbs'
        before=next(s['data'] for s in project['shortcodes'] if s['name']==filename)
        if '{{#each casinos.'+group+'}}' not in before:raise ValueError('Wrong connected source')
        shortcodes[filename]={'before':before,'after':template(group)}
    return {'casinos_before':project['data']['casinos'],'casinos_after':casinos,'shortcodes':shortcodes,'concept':CONCEPT}
