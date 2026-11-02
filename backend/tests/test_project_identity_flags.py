import pytest
from app import project_network as network
from app.domain_transfer_policy import banned_domains, set_ban
from app.network_state import HISTORY_FIELDS, mark_project_identity, observe_network
from test_project_network import env


def test_identity_flags_survive_sync_and_leave_current_main_and_markup_unchanged(env):
    db, site, remote = env
    site.name = 'Project.TEST'
    remote.data['settings']['domains'].append('www.project.test')
    site.network_state = {'history_overrides': {'www.project.test': dict(main=False, alternate=False, x_default=False)}}
    db.commit()
    result = network.read_network(db, site)
    assert result['canon'] == 'main.test'
    assert result['domain_bans']['www.project.test'] is True
    for key in ['main_history', 'alternate_history', 'x_default_history']:
        assert 'www.project.test' in result[key]
    assert 'reserve.test' not in result['main_history']
    assert result['domain_bans']['next.test'] is False
    assert not remote.calls
    observe_network(site, {'settings': {'canon': 'main.test'}})
    assert all('www.project.test' in getattr(site, field) for field in HISTORY_FIELDS.values())


@pytest.mark.parametrize('field', ['main', 'alternate', 'x_default', 'ban'])
def test_project_identity_protection_cannot_be_unchecked(env, field):
    db, site, remote = env
    remote.data['settings']['domains'].append(site.name)
    network.read_network(db, site)
    with pytest.raises(ValueError, match='именем проекта Webdev'):
        network.update_domain_history(db, site, network.DomainHistoryUpdate(domain=site.name, field=field, checked=False), 'anton')
    with pytest.raises(ValueError, match='именем проекта Webdev'):
        set_ban(db, site, site.name, False, 'anton')


def test_backfill_only_marks_existing_identity_members_and_is_idempotent(env):
    db, site, remote = env
    site.cache_domains = ['www.project.test', 'other.test']
    before = site.cache_canon
    mark_project_identity(site)
    mark_project_identity(site)
    assert all(getattr(site, field) == ['www.project.test'] for field in HISTORY_FIELDS.values())
    assert site.cache_canon == before
    assert banned_domains(db, site, site.cache_domains) == {'www.project.test': True, 'other.test': False}
    site.main_domain_history = site.alternate_domain_history = site.x_default_history = []
    site.cache_domains = ['other.test']
    mark_project_identity(site)
    assert all(getattr(site, field) == [] for field in HISTORY_FIELDS.values())
