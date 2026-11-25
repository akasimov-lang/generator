from types import SimpleNamespace
import pytest
from app.domain_classification import registrable_root, default_domain_type, apply_default_domain_types, classify_domains
from scripts.classify_shared_zone_domains import corrected_types


@pytest.mark.parametrize('domain', ['mostbet.gu.cc', 'mostbetaz.com.tc', 'mostbetaz.eu.com', 'mostbetazgiris.mex.com', 'mostbetgiris.eu.com', 'example.cn.com'])
def test_shared_zone_domain_is_a_newreg_root(domain):
    zone = domain.split('.', 1)[1]
    site = SimpleNamespace(cache_domains=[domain], domain_types={zone: 'drop'})
    assert registrable_root(domain) == domain
    assert default_domain_type(domain) == 'newreg'
    apply_default_domain_types(site)
    assert site.domain_types[domain] == 'newreg'
    assert not classify_domains([domain], site.domain_types)[domain]['is_subdomain']


def test_actual_child_retains_its_parent_and_does_not_become_a_root():
    roles = classify_domains(['child.mostbet.eu.com'], {'mostbet.eu.com': 'newreg'})
    assert roles['child.mostbet.eu.com']['is_subdomain']
    assert roles['child.mostbet.eu.com']['parent_domain'] == 'mostbet.eu.com'
    assert roles['child.mostbet.eu.com']['parent_type'] == 'newreg'
    assert default_domain_type('eu.com.unrelated.org') == 'drop'


def test_correction_is_scoped_preserves_amp_and_is_idempotent():
    site = SimpleNamespace(name='example.test', cache_canon='', cache_domains=['mostbet.gu.cc', 'www.mostbet.eu.com', 'amp.mex.com', 'other.org'], main_domain_history=[], alternate_domain_history=[], x_default_history=[], domain_types={'gu.cc':'drop', 'mostbet.gu.cc':'drop', 'www.mostbet.eu.com':'drop', 'amp.mex.com':'amp', 'other.org':'drop'})
    before = dict(site.domain_types)
    types, changes = corrected_types(site)
    assert site.domain_types == before
    assert types['mostbet.gu.cc'] == types['mostbet.eu.com'] == types['www.mostbet.eu.com'] == 'newreg'
    assert types['amp.mex.com'] == 'amp'
    assert types['other.org'] == types['gu.cc'] == 'drop'
    assert len(changes) == 3
    site.domain_types = types
    assert corrected_types(site) == (types, [])


def test_cn_com_registration_is_a_root_and_real_children_inherit_newreg_type():
    site=SimpleNamespace(cache_domains=['www.example.cn.com','mobile.example.cn.com'],domain_types={'cn.com':'drop'})
    assert registrable_root('example.cn.com')=='example.cn.com'
    assert registrable_root('mobile.example.cn.com')=='example.cn.com'
    assert default_domain_type('https://EXAMPLE.cn.com/')=='newreg'
    apply_default_domain_types(site)
    roles=classify_domains(site.cache_domains,site.domain_types)
    assert roles['www.example.cn.com']['is_subdomain'] is False
    assert roles['mobile.example.cn.com']['parent_domain']=='www.example.cn.com'
    assert roles['mobile.example.cn.com']['parent_type']=='newreg'
    assert default_domain_type('cn.com.unrelated.org')=='drop'
    assert default_domain_type('notcn.com')=='drop'


def test_cn_com_correction_updates_existing_types_only_in_the_requested_zone():
    site=SimpleNamespace(name='project.test',cache_canon='example.cn.com',cache_domains=['example.cn.com','www.saved.cn.com','mobile.cn.com','old.eu.com','other.org'],main_domain_history=['historic.cn.com'],alternate_domain_history=[],x_default_history=[],domain_types={'cn.com':'drop','example.cn.com':'drop','www.saved.cn.com':'drop','mobile.cn.com':'amp','old.eu.com':'drop','other.org':'drop'})
    before=dict(site.domain_types)
    types,changes=corrected_types(site,zones=('cn.com',))
    assert site.domain_types==before
    assert types['example.cn.com']==types['saved.cn.com']==types['www.saved.cn.com']==types['historic.cn.com']=='newreg'
    assert types['mobile.cn.com']=='amp'
    assert types['old.eu.com']==types['other.org']==types['cn.com']=='drop'
    assert all(c['domain'].endswith('.cn.com') for c in changes)
    site.domain_types=types
    assert corrected_types(site,zones=('cn.com',))==(types,[])
