from app.pilot_domain_filters import domain_projects


def test_reserve_is_also_a_drop_and_subdomains_use_parent_kind():
    plans = {'a': {'reserve_pool_id': 'reserve'}, 'b': {'domain_type': 'sub_newreg'},
             'c': {'required_domain_type': 'drop_subdomain'}, 'd': {'main_target_kind': 'other'}}
    result = domain_projects(plans, [{'site_id': key} for key in plans])
    assert result == {'reserve_drops': ['a'], 'drops': ['a', 'c'], 'newregs': ['b'], 'other': ['d'], 'internal_pages': []}


def test_execution_requires_confirmed_main_even_when_later_steps_fail():
    plans = {'a': {'domain_type': 'drop'}, 'b': {'domain_type': 'drop'}}
    items = [{'site_id': 'a', 'status': 'partial', 'performed_at': '2026-11-05'},
             {'site_id': 'b', 'status': 'waiting'}]
    assert domain_projects(plans, items, confirmed=True)['drops'] == ['a']


def test_plan_includes_unexecuted_projects_but_not_excluded_rows():
    plans = {'a': {'domain_type': 'newreg'}, 'excluded': {'domain_type': 'newreg'}}
    assert domain_projects(plans, [{'site_id': 'a', 'status': 'ready'}])['newregs'] == ['a']


def test_added_pages_requires_publication_even_if_main_is_not_confirmed():
    items = [
        {'site_id': 'done', 'internal_pages': {'published': 3, 'status': 'completed'}},
        {'site_id': 'partial', 'internal_pages': {'published': 1, 'status': 'partial'}},
        {'site_id': 'planned', 'internal_pages': {'enabled': True, 'count': 4}},
        {'site_id': 'generated', 'internal_pages': {'generated': 4, 'published': 0}},
        {'site_id': 'none'},
    ]
    assert domain_projects({}, items, confirmed=True)['internal_pages'] == ['done', 'partial']


def test_preview_includes_planned_internal_pages():
    assert domain_projects({}, [{'site_id': 'a', 'internal_pages': {'enabled': True, 'count': 3}}])['internal_pages'] == ['a']
