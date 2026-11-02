from types import SimpleNamespace
import pytest
from app.subdomain_naming import next_subdomain


def naming(domains=(), brand='Pinco'):
    state = {'domains': ['root22.com', *domains]}
    site = SimpleNamespace(id='project', name='project.test', brand=brand, cache_geo='AZ', cache_language='az',
        cache_domains=state['domains'], domain_types={'root22.com': 'drop'}, main_domain_history=[], alternate_domain_history=[])
    cfg = SimpleNamespace(parent_kind='drop', language='az', subdomain_name_style='mixed', subdomain_add_casino=False)
    return site, state, cfg


def test_geo_then_geo_brand_without_numbers_in_new_network():
    site, state, cfg = naming()
    assert next_subdomain(site, state, cfg, 'root22.com', prefer_geo=True) == 'az.root22.com'
    state['domains'].append('az.root22.com')
    assert next_subdomain(site, state, cfg, 'root22.com', prefer_geo=True) == 'azpinco.root22.com'


@pytest.mark.parametrize('brand', ['Pinco', '22Bet', 'Общие ключи'])
def test_no_numbered_names_without_current_numbered_subdomains(brand):
    site, state, cfg = naming(brand=brand)
    site.main_domain_history = ['old7.root22.com']  # History/root digits do not enable numeric names.
    generated = []
    for _ in range(100):
        try: name = next_subdomain(site, state, cfg, 'root22.com', prefer_geo=True)
        except ValueError: break
        generated.append(name); state['domains'].append(name)
    else: pytest.fail('Expected finite nonnumeric choices')
    assert generated and all(not any(c.isdigit() for c in name.split('.')[0]) for name in generated)


def test_numeric_fallback_requires_existing_numbered_label_and_preserves_history():
    site, state, cfg = naming(['old2.root22.com'])
    site.main_domain_history = ['az1.root22.com']
    for _ in range(30):
        name = next_subdomain(site, state, cfg, 'root22.com', prefer_geo=True)
        assert name != 'az1.root22.com'
        if any(c.isdigit() for c in name.split('.')[0]): break
        state['domains'].append(name)
    else: pytest.fail('Numbered fallback was unavailable despite existing numbered subdomain')


def test_historic_plan_share_survives_summary_update():
    from app.pilot_variations import update_summary
    result = {'groups': [{'plans': [{'site_id': str(i)} for i in range(20)]}], 'variation_summary': {'title_h1_percent': 20}}
    update_summary(result)
    assert result['variation_summary']['subdomains_requested'] == 3
    assert result['variation_summary']['subdomains_percent'] == 15
    result['variation_summary']['subdomains_percent'] = 10
    update_summary(result)
    assert result['variation_summary']['subdomains_requested'] == 2
