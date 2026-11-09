from copy import deepcopy
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest
from app import models, project_network as network
from app.reglue_journal import recent_for_site, latest_for_site
from test_project_network import env, change, MARKUP

AT = datetime(2026, 11, 9, 11, 48, tzinfo=timezone.utc)
AFTER = '<link rel="alternate" hreflang="pl" href="https://new.test/pl/" />'


def receipt(db, site, *, before=None, after=AFTER, enabled=True, status='confirmed', legacy=False):
    payload = {'alternateMarkup': after, 'enableAlternates': enabled}
    if not legacy:
        payload.update(confirmed_at=AT.isoformat(), alternates_before=before or {'markup': MARKUP, 'enabled': True})
    op = models.NetworkOperation(id=str(uuid4()), site_id=site.id, action='alternates', status=status,
                                 initiator='colleague', request_payload=payload, updated_at=AT)
    db.add(op); db.commit()
    return op


def test_confirmed_alternates_appear_from_historical_receipt_not_current_cache(env):
    db, site, _ = env
    op = receipt(db, site)
    original = deepcopy(op.request_payload)
    site.network_state = {'alternateMarkup': 'unrelated current markup', 'enableAlternates': False}
    item = recent_for_site(db, site)[0]
    assert item['id'] == op.id and item['kind'] == 'alternates'
    assert item['initiator'] == 'colleague' and item['at'] == AT.isoformat()
    assert item['alternates_before'] == {'markup': MARKUP, 'enabled': True}
    assert item['alternates_after'] == {'markup': AFTER, 'enabled': True}
    assert op.request_payload == original
    assert latest_for_site(db, site) is None


def test_legacy_alternates_keep_unknown_baseline_and_recorded_time(env):
    db, site, _ = env
    receipt(db, site, legacy=True)
    item = recent_for_site(db, site)[0]
    assert item['alternates_before'] is None
    assert item['at'] == AT.isoformat()
    assert item['alternates_after']['markup'] == AFTER


@pytest.mark.parametrize('status', ['pending', 'unknown', 'failed'])
def test_unconfirmed_alternates_do_not_become_completed_history(env, status):
    db, site, _ = env
    receipt(db, site, status=status)
    assert recent_for_site(db, site) == []


def test_canonical_only_save_and_markup_whitespace_are_not_alternate_changes(env):
    db, site, _ = env
    op = receipt(db, site, after=MARKUP.replace('\n', '\n  '))
    op.request_payload = {**op.request_payload, 'canonicalDefaultMarkup': '<link rel="canonical" href="https://new.test/" />'}
    db.commit()
    assert recent_for_site(db, site) == []


def test_disabling_alternates_is_recorded_even_when_markup_is_unchanged(env):
    db, site, _ = env
    receipt(db, site, after=MARKUP, enabled=False)
    item = recent_for_site(db, site)[0]
    assert item['alternates_before']['enabled'] is True
    assert item['alternates_after'] == {'markup': MARKUP, 'enabled': False}


def test_clearing_markup_is_a_real_historical_change(env):
    db, site, _ = env
    receipt(db, site, after='')
    assert recent_for_site(db, site)[0]['alternates_after']['markup'] == ''


def test_network_response_records_confirmation_once_without_counting_a_reglue(env):
    db, site, remote = env
    before = network.read_network(db, site)
    result = change(env, 'alternates', before['revision'], alternate_markup=AFTER, enable_alternates=True)
    item = next(item for item in result['recent_network_changes'] if item['kind'] == 'alternates')
    op = db.get(models.NetworkOperation, item['id'])
    stamp = op.request_payload['confirmed_at']
    assert item['at'] == stamp and site.last_reglue_at is None
    op.updated_at = AT + timedelta(days=10); db.commit()
    repeated = network.read_network(db, site)
    assert next(item for item in repeated['recent_network_changes'] if item['id'] == op.id)['at'] == stamp
    assert len(remote.calls) == 1


def test_delayed_alternate_confirmation_enters_history_only_after_readback(env):
    db, site, remote = env
    before = network.read_network(db, site); remote.delayed = True
    pending = change(env, 'alternates', before['revision'], alternate_markup=AFTER, enable_alternates=True)
    assert not pending['recent_network_changes']
    remote.data['head'].update(alternateMarkup=AFTER, enableAlternates=True)
    result = network.read_network(db, site)
    assert len(result['recent_network_changes']) == 1
    assert result['recent_network_changes'][0]['alternates_after']['markup'] == AFTER
    assert len(remote.calls) == 1
