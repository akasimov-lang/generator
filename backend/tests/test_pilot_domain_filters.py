from app.pilot_domain_filters import domain_projects


def test_reserve_is_also_a_drop_and_subdomains_use_parent_kind():
    plans = {'a': {'reserve_pool_id': 'reserve'}, 'b': {'domain_type': 'sub_newreg'},
             'c': {'required_domain_type': 'drop_subdomain'}, 'd': {'main_target_kind': 'other'}}
    result = domain_projects(plans, [{'site_id': key} for key in plans])
    assert result == {'reserve_drops': ['a'], 'drops': ['a', 'c'], 'newregs': ['b'], 'other': ['d']}


def test_execution_requires_confirmed_main_even_when_later_steps_fail():
    plans = {'a': {'domain_type': 'drop'}, 'b': {'domain_type': 'drop'}}
    items = [{'site_id': 'a', 'status': 'partial', 'performed_at': '2026-11-05'},
             {'site_id': 'b', 'status': 'waiting'}]
    assert domain_projects(plans, items, confirmed=True)['drops'] == ['a']


def test_plan_includes_unexecuted_projects_but_not_excluded_rows():
    plans = {'a': {'domain_type': 'newreg'}, 'excluded': {'domain_type': 'newreg'}}
    assert domain_projects(plans, [{'site_id': 'a', 'status': 'ready'}])['newregs'] == ['a']
