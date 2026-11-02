import pytest
from app import models, project_network as network
from app.domain_transfer_policy import initialize_main_baseline, main_pin_owners, require_main_destination, require_transfer_allowed, set_ban, banned_domains
from app.network_state import observe_network
from test_project_network import env


def seed(db, source, domain):
    initialize_main_baseline(db, {'source': 'first-mass-snapshot', 'captured_at': '2026-09-23T14:02:33+00:00',
        'projects': [{'site_id': source.id, 'project': source.name, 'domain': domain}]})


def test_initial_main_stays_pinned_after_history_flags_are_cleared(env):
    db, source, remote = env
    source.project_status = 'mass_actions'
    seed(db, source, 'www.initial.test')
    source.main_domain_history = []
    source.network_state = {}
    source.cache_canon = 'new-main.test'
    db.commit()
    for variant in ['initial.test', 'www.initial.test', 'https://initial.test/']:
        with pytest.raises(ValueError, match='Main закреплён'):
            require_transfer_allowed(db, source, variant)
    assert main_pin_owners(db, ['initial.test'])['initial.test'] == {source.id}


def test_observed_mass_main_pin_survives_user_correction_and_new_main(env):
    db, source, remote = env
    source.project_status = 'mass_actions'
    network.read_network(db, source)
    network.update_domain_history(db, source, network.DomainHistoryUpdate(domain='main.test', field='main', checked=False), 'user')
    remote.data['settings']['canon'] = 'next.test'
    latest = network.read_network(db, source)
    assert 'main.test' not in latest['main_history']
    assert set(latest['protected_main_domains']) == {'main.test', 'next.test'}
    with pytest.raises(ValueError, match='Main закреплён'):
        require_transfer_allowed(db, source, 'main.test')


def test_pinned_main_cannot_be_added_to_another_network_but_can_return_to_owner(env):
    db, source, remote = env
    target = models.Site(name='other.test', base_url='https://other.test', publication_endpoint='/')
    db.add(target); db.commit()
    seed(db, source, 'initial.test')
    with pytest.raises(ValueError, match='Перенос в другую сетку запрещён'):
        require_main_destination(db, target, ['www.initial.test'])
    require_main_destination(db, source, ['initial.test'])
    require_main_destination(db, target, ['unused.test'])
    # Direct network API writes cannot bypass the transfer guard.
    current = network.read_network(db, target)
    with pytest.raises(ValueError, match='закреплён как Main'):
        network.change_network(db, target, network.NetworkChange(request_id=__import__('uuid').uuid4(),
            action='create_domains', revision=current['revision'], domains=['initial.test']), 'user')
    assert remote.calls == []


def test_ban_edits_and_reimport_cannot_erase_a_baseline_pin(env):
    db, source, remote = env
    source.cache_geo = 'PL'
    seed(db, source, 'initial.test')
    set_ban(db, source, 'initial.test', True, 'user')
    seed(db, source, 'initial.test')
    assert banned_domains(db, source, ['initial.test'])['initial.test']
    set_ban(db, source, 'initial.test', False, 'user')
    with pytest.raises(ValueError, match='Main закреплён'):
        require_transfer_allowed(db, source, 'initial.test')


def test_pin_applies_when_owner_is_outside_the_request_grants(env):
    db, source, remote = env
    source.project_status = 'mass_actions'
    observe_network(source, remote.data); db.commit()
    target = models.Site(name='other.test', base_url='https://other.test', publication_endpoint='/')
    db.add(target); db.commit()
    db.info['allowed_site_ids'] = [target.id]
    with pytest.raises(ValueError, match='закреплён как Main'):
        require_main_destination(db, target, ['main.test'])


def test_it_com_zone_is_banned_in_every_geo_and_cannot_be_unbanned(env):
    db, source, remote = env
    names = ['it.com', 'casinolemon.it.com', 'https://WWW.Casino.IT.com/', 'nested.casino.it.com']
    for geo in ['PL', 'CZ', 'AZ']:
        source.cache_geo = geo
        assert all(banned_domains(db, source, names).values())
        with pytest.raises(ValueError, match='БАН'):
            require_transfer_allowed(db, source, 'casinolemon.it.com')
    with pytest.raises(ValueError, match='общий БАН'):
        set_ban(db, source, 'casinolemon.it.com', False, 'user')
    assert not any(banned_domains(db, source, ['legit.com', 'it.com.example', 'casinoit.com', 'casino.jp.net']).values())
