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
