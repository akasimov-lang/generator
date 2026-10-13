from types import SimpleNamespace
from app.site_statistics import mass_action_statistics


def site(**kwargs):
    return SimpleNamespace(**dict(dict(id='one', name='example.com', fibery_name=None, hidden_from_projects=False,
        project_status='mass_actions', cache_geo='ru-KZ', site_type=None, brand='Pin-Up',
        cache_domains=['https://EXAMPLE.com/', 'example.com', 'sub.example.com', 'fresh.xyz', 'unknown.net', 'amp.org'],
        domain_types={'example.com':'drop', 'fresh.xyz':'newreg', 'amp.org':'amp'}, cache_synced_at=None), **kwargs))


def test_network_statistics_counts_and_scope():
    first=site()
    rows=mass_action_statistics([first, first, site(id='hidden',hidden_from_projects=True),site(id='vitalina',project_status='vitalina')])['projects']
    assert len(rows)==1
    row=rows[0]
    assert row['geo']=='KZ'
    assert row['site_type']=='monobrand' and row['brand']=='Pin-Up'
    assert {k:row[k] for k in ('domains','drop','newreg','subdomains','amp','unknown')}==dict(domains=5,drop=1,newreg=1,subdomains=1,amp=1,unknown=1)


def test_manual_type_unknown_geo_and_no_domains():
    row=mass_action_statistics([site(site_type='general',cache_geo=None,cache_domains=[])])['projects'][0]
    assert row['site_type']=='general' and row['brand']=='Общие ключи'
    assert row['geo']=='UNKNOWN' and row['domains']==0


def test_separate_ru_kz_scopes():
    sites = [site(id='ru', project_status='geo_ru', cache_geo='RU'), site(id='kz', project_status='geo_kz'), site(id='mass'), site(id='hidden', project_status='geo_ru', hidden_from_projects=True)]
    assert [r['id'] for r in mass_action_statistics(sites, 'geo_ru')['projects']] == ['ru']
    assert [r['id'] for r in mass_action_statistics(sites, 'geo_kz')['projects']] == ['kz']
    assert [r['id'] for r in mass_action_statistics(sites)['projects']] == ['mass']


def test_hands_only_scope():
    rows = mass_action_statistics([site(id='hands', project_status='hands_only'), site(id='mass'), site(id='hidden', project_status='hands_only', hidden_from_projects=True)], 'hands_only')['projects']
    assert [r['id'] for r in rows] == ['hands']
