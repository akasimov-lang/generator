from copy import deepcopy
from types import SimpleNamespace

import pytest

from app import canonical_allocation, pilot_schemes
from app.fake_main import next_fake_path
from app.network_state import alternate_links
from app.subdomain_naming import next_subdomain
from test_project_network import env


def context(index, brand='Pinco', geo='PL'):
    root = f'project{index}.co.uk'
    state = {'domains': [root]}
    site = SimpleNamespace(id=str(index), name=root, brand=brand, cache_geo=geo, cache_language='pl',
        cache_domains=[root], domain_types={root:'newreg'}, main_domain_history=[], alternate_domain_history=[])
    cfg = SimpleNamespace(parent_kind='newreg', language='pl', subdomain_name_style='hyphen', subdomain_add_casino=False)
    return site, state, cfg, root


def test_sixteen_projects_rotate_four_name_families_stably_without_numbers():
    children, paths = [], []
    for index in range(16):
        site, state, cfg, root = context(index)
        child = next_subdomain(site, state, cfg, root, allocation_index=index)
        path = next_fake_path(site, state, cfg, allocation_index=index)
        assert child == next_subdomain(site, state, cfg, root, allocation_index=index)
        assert path == next_fake_path(site, state, cfg, allocation_index=index)
        assert not any(c.isdigit() for c in child.removesuffix('.'+root) + path)
        children.append(child.removesuffix('.'+root)); paths.append(path)
    assert set(children) == {'pinco-pl', 'pl-pinco', 'pinco-casino', 'pinco'}
    assert all(children.count(name) == 4 for name in set(children))
    assert set(paths) == {'/pinco-pl/', '/pl-pinco/', '/pinco-casino/', '/pinco/'}


def test_mass_names_respect_history_collisions_and_mixed_case_paths():
    site, state, cfg, root = context(1)
    first = next_subdomain(site, state, cfg, root, allocation_index=0)
    site.x_default_history = [first]
    second = next_subdomain(site, state, cfg, root, allocation_index=0)
    assert second != first
    state['fake_main_history'] = ['/PINCO-PL/']
    assert next_fake_path(site, state, cfg, allocation_index=0) != '/pinco-pl/'


def test_generic_names_never_borrow_a_brand_and_custom_brand_still_works():
    seen = set()
    for index in range(12):
        site, state, cfg, root = context(index, 'Общие ключи')
        child = next_subdomain(site, state, cfg, root, allocation_index=index)
        seen.add(child.removesuffix('.'+root))
    assert seen == {'pl-pl', 'casino-pl', 'pl-casino', 'online-casino-pl'}
    site, state, cfg, root = context(0, 'Custom Reef')
    assert next_subdomain(site, state, cfg, root, allocation_index=0) == 'custom-reef-pl.' + root


def plan(index, *, path='/offer/', enabled=True):
    return {'site_id':str(index), 'brand':'Pinco', 'new_main':f'pl.brand{index}.co.uk', 'parent_domain':f'brand{index}.co.uk',
            'fake_main_path':path, 'create_fake_main_path':path, 'enableAlternates':enabled,
            'alternateMarkup':'<link rel="alternate" hreflang="pl" href="https://pl.brand'+str(index)+'.co.uk/offer/" />' if enabled else '',
            'canonical_mode':'self', 'canonicalFakeMainMarkup':'<link rel="canonical" href="https://{{settings.canon}}/" />'}


def test_parent_xdefault_twelve_projects_exact_half_and_order_independent():
    plans = [plan(i) for i in range(12)]
    reverse = deepcopy(plans[::-1])
    pilot_schemes.allocate_parent_x_defaults(plans)
    pilot_schemes.allocate_parent_x_defaults(reverse)
    assert sum(p['x_default_parent_path'] == '/offer/' for p in plans) == 6
    assert {p['site_id']:p for p in plans} == {p['site_id']:p for p in reverse}
    for p in plans:
        assert alternate_links(p['alternateMarkup'])[-1]['href'] == 'https://' + p['parent_domain'] + p['x_default_parent_path']
        assert p['canonical_mode'] == 'self'
        pilot_schemes.validate_parent_x_default(p)


def test_parent_rule_preserves_disabled_and_uses_root_without_internal_page():
    disabled, root = plan(1, enabled=False), plan(2, path=None)
    before = deepcopy(disabled)
    pilot_schemes.allocate_parent_x_defaults([disabled, root])
    assert disabled == before
    assert alternate_links(root['alternateMarkup'])[-1]['href'] == 'https://brand2.co.uk/'


def test_parent_rule_replays_saved_selection_and_rejects_tampered_parent():
    saved = plan(1)
    pilot_schemes.allocate_parent_x_defaults([saved])
    db = SimpleNamespace(info={})
    before = deepcopy(saved)
    with canonical_allocation.replay(db, saved):
        result = {**saved, 'x_default_parent_path':'/'}
        canonical_allocation.apply(db, SimpleNamespace(brand='Pinco'), result)
        assert result == saved
    assert saved == before and db.info == {}
    saved['parent_domain'] = 'foreign.co.uk'
    with pytest.raises(ValueError, match='Родитель'):
        pilot_schemes.validate_parent_x_default(saved)


@pytest.mark.parametrize('clean', [False, True])
def test_legacy_reviewed_within_plan_replays_without_adding_new_naming_field(env, monkeypatch, clean):
    from app import auto_reglue as auto
    from test_auto_reglue import prepare_fake_run
    db, site, _ = env
    run = prepare_fake_run(env, monkeypatch)
    if clean:
        cfg = auto.config(db); cfg.scheme_mode = 'clean'; auto.save_config(db, cfg)
        reviewed = auto.preview(db, site)
    else:
        reviewed = deepcopy(run.plan)
    reviewed.pop('naming_allocation_index', None)
    reviewed.pop('preview_token', None); reviewed['preview_token'] = auto.digest(reviewed)
    before = deepcopy(reviewed)
    with canonical_allocation.replay(db, reviewed):
        regenerated = auto.preview(db, site)
    assert 'naming_allocation_index' not in regenerated
    assert regenerated['preview_token'] == reviewed['preview_token']
    assert reviewed == before
