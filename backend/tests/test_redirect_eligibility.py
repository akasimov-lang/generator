import pytest
from app.redirect_eligibility import require_non_amp
from app.domain_redirects import all_to_main


def test_amp_role_excludes_source_even_with_www_alias():
    with pytest.raises(ValueError,match='AMP'):
        require_non_amp({}, {'amp.test':'amp'}, 'www.amp.test','main.test')


def test_amp_destination_excluded_by_network_membership():
    with pytest.raises(ValueError,match='AMP'):
        require_non_amp({'amp_domains':['amp.test']},{},'old.test','https://amp.test/path/')


def test_word_amp_in_a_name_does_not_determine_role():
    require_non_amp({}, {'online-brand-amp.test':'newreg'},'drop.test','online-brand-amp.test')


def test_retarget_main_keeps_existing_amp_rules_unchanged():
    state={'canon':'main.test','has_domain_redirects':True,'amp_domains':['amp.test'],'domain_redirects':[{'url':'amp.test','value':'other.test'},{'url':'drop.test','value':'older.test'}]}
    assert all_to_main(state)==[{'url':'amp.test','value':'other.test'},{'url':'drop.test','value':'main.test'}]


def test_pasted_slashes_cannot_bypass_amp_role():
    with pytest.raises(ValueError,match='AMP'):
        require_non_amp({'amp_domains':['amp.test']},{},'old.test','//https://amp.test/path/')


def test_child_of_an_amp_domain_is_not_an_eligible_destination():
    with pytest.raises(ValueError,match='AMP'):
        require_non_amp({'amp_domains':['amp.test']},{},'old.test','child.amp.test')


def test_retarget_main_preserves_typed_amp_and_children():
    rows=[{'url':'amp.test','value':'other.test'},{'url':'child.amp.test','value':'other.test'}]
    state={'canon':'main.test','has_domain_redirects':True,'domain_redirects':rows}
    assert all_to_main(state,{'amp.test':'amp'})==rows
