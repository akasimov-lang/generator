from types import SimpleNamespace
from app.branded_domains import apply_brand_domain_types
from app.domain_classification import classify_domains


def test_brand_marks_roots_without_promoting_branded_children():
    site = SimpleNamespace(name='project.test', brand='Pinco',
        cache_domains=['pinco.com', 'pinco.example.com', 'example.com', '1xslots.com.br',
                       'qizilbilet.co.uk', 'pinco.blogspot.com', 'www.pelican.com'],
        domain_types={'example.com': 'drop', 'pinco.com': 'drop'})
    changes = apply_brand_domain_types(site, overwrite_drops=True)
    assert {c['domain'] for c in changes} == {'pinco.com', '1xslots.com.br', 'qizilbilet.co.uk', 'www.pelican.com'}
    assert next(c for c in changes if c['domain']=='pinco.com')['before'] == 'drop'
    assert site.domain_types['example.com'] == 'drop'
    child = classify_domains(site.cache_domains, site.domain_types)['pinco.example.com']
    assert child['parent_type'] == 'drop' and child['is_subdomain']
    assert 'pinco.example.com' not in site.domain_types
    assert 'pinco.blogspot.com' not in site.domain_types
    assert apply_brand_domain_types(site, overwrite_drops=True) == []


def test_incremental_sync_preserves_explicit_drop_and_missing_parent_child():
    site=SimpleNamespace(name='project.test', brand='CustomBrand',
        cache_domains=['custombrand.com', 'pinco.com', 'pelican.missingparent.com'],
        domain_types={'pinco.com':'drop'})
    changes=apply_brand_domain_types(site)
    assert [c['domain'] for c in changes] == ['custombrand.com']
    assert site.domain_types['pinco.com']=='drop'
    child=classify_domains(site.cache_domains, site.domain_types)['pelican.missingparent.com']
    assert child['is_subdomain'] and child['parent_domain']=='missingparent.com'
    assert child['parent_type'] is None


def test_default_types_persist_missing_parents_and_preserve_existing():
    from app.domain_classification import apply_default_domain_types, NEWREG_ZONES
    roots = ["example." + zone for zone in NEWREG_ZONES]
    site = SimpleNamespace(cache_domains=["pinco.unknown.com", "www.explicit.site", "ordinary.org", *["child." + root for root in roots]], domain_types={"explicit.site": "drop"})
    apply_default_domain_types(site)
    assert site.domain_types["unknown.com"] == "drop"
    assert site.domain_types["ordinary.org"] == "drop"
    assert site.domain_types["www.explicit.site"] == "drop"
    roles = classify_domains(site.cache_domains, site.domain_types)
    for root in roots:
        assert site.domain_types[root] == "newreg"
        assert roles["child." + root]["parent_domain"] == root
        assert roles["child." + root]["parent_type"] == "newreg"
    assert "pinco.unknown.com" not in site.domain_types
    assert apply_default_domain_types(site) == []


def test_jp_net_registrations_are_roots_with_newreg_children():
    from app.domain_classification import apply_default_domain_types, registrable_root, default_domain_type
    from app.site_statistics import network_domain_counts
    domains=['lemoncasino.jp.net','www.other.jp.net','child.lemoncasino.jp.net','notjp.net','jp.net.example.com']
    site=SimpleNamespace(cache_domains=domains,domain_types={'jp.net':'drop','notjp.net':'drop','example.com':'drop'})
    assert registrable_root('lemoncasino.jp.net')=='lemoncasino.jp.net'
    assert registrable_root('child.lemoncasino.jp.net')=='lemoncasino.jp.net'
    assert default_domain_type('https://LEMONCASINO.jp.net/')=='newreg'
    assert default_domain_type('notjp.net')=='drop'
    assert default_domain_type('jp.net.example.com')=='drop'
    apply_default_domain_types(site)
    roles=classify_domains(domains,site.domain_types)
    assert not roles['lemoncasino.jp.net']['is_subdomain']
    assert not roles['www.other.jp.net']['is_subdomain']
    assert roles['child.lemoncasino.jp.net']['parent_type']=='newreg'
    assert roles['jp.net.example.com']['parent_type']=='drop'
    assert site.domain_types['lemoncasino.jp.net']=='newreg'
    assert site.domain_types['www.other.jp.net']=='newreg'
    assert network_domain_counts(site)==dict(domains=5,drop=1,newreg=2,subdomains=2,amp=0,unknown=0)
    assert apply_default_domain_types(site)==[]


def test_jp_net_correction_updates_existing_drops_and_preserves_amp_and_other_zones():
    import importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('classify_jp_net_domains',Path(__file__).parents[1]/'scripts/classify_jp_net_domains.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    site=SimpleNamespace(name='project.test',cache_canon='lemoncasino.jp.net',
        cache_domains=['lemoncasino.jp.net','child.other.jp.net','www.saved.jp.net','mobile.jp.net','old.it.com','other.net'],
        main_domain_history=['historical.jp.net'],alternate_domain_history=[],x_default_history=[],
        domain_types={'jp.net':'drop','lemoncasino.jp.net':'drop','www.saved.jp.net':'drop','mobile.jp.net':'amp','old.it.com':'drop','other.net':'drop'})
    before=dict(site.domain_types)
    types,changes=module.corrected_types(site)
    assert site.domain_types==before
    assert types['lemoncasino.jp.net']==types['other.jp.net']==types['saved.jp.net']==types['www.saved.jp.net']==types['historical.jp.net']=='newreg'
    assert types['mobile.jp.net']=='amp' and types['old.it.com']==types['other.net']=='drop'
    assert 'child.other.jp.net' not in types
    assert all(c['domain'].endswith('.jp.net') for c in changes)
    site.domain_types=types
    assert module.corrected_types(site)==(types,[])
