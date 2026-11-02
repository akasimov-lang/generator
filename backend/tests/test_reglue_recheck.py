from copy import deepcopy
from uuid import uuid4
import httpx
import pytest
from app import auto_reglue as auto, models, cross_reglue as cross, reglue_recheck as recheck
from test_project_network import env
from test_cross_reglue import setup, launch


def completed(setup, monkeypatch):
    db, source, target, sr, tr = setup
    run = launch(setup); auto.execute(db, run.id)
    assert run.status == 'completed'
    run.plan = {**run.plan, 'list_launch_id': str(uuid4())}
    run.status = 'partial'; db.commit()
    monkeypatch.setattr(recheck, 'fresh_project', lambda db, site: deepcopy(tr.data if site.id == target.id else sr.data))
    return db, run, tr, sr


def test_fresh_cache_confirms_http_error_without_repeating_write(setup, monkeypatch):
    db, run, tr, sr = completed(setup, monkeypatch)
    db.autoflush = False  # Production SessionLocal uses explicit flushes.
    op = db.get(models.NetworkOperation, cross.receipt_id(run, 'alternates'))
    op.status = 'failed'; op.response_status = 400; op.message = 'HTTP 400'; db.commit()
    calls = (deepcopy(tr.calls), deepcopy(sr.calls))
    result = recheck.check_run(db, run.id)
    assert result['status'] == 'confirmed' and all(c['ok'] for c in result['checks'])
    assert run.status == 'completed' and op.status == 'confirmed'
    assert 'HTTP 400' in run.plan['dns_warnings'][0]['message']
    assert (tr.calls, sr.calls) == calls


@pytest.mark.parametrize('mismatch', ['main', 'alternates', 'title_h1'])
def test_mismatch_never_becomes_success(setup, monkeypatch, mismatch):
    db, run, tr, sr = completed(setup, monkeypatch)
    if mismatch == 'main': tr.data['settings']['canon'] = 'other.test'
    if mismatch == 'alternates': tr.data['head']['alternateMarkup'] = ''
    if mismatch == 'title_h1': run.plan = {**run.plan, 'rewrite_title_h1': True}; db.commit()
    calls = deepcopy(tr.calls)
    assert recheck.check_run(db, run.id)['status'] == 'mismatch'
    assert run.status == 'partial' and tr.calls == calls


def test_read_error_preserves_status_and_exact_code(setup, monkeypatch):
    db, run, tr, sr = completed(setup, monkeypatch)
    def fail(*args):
        response = httpx.Response(502, request=httpx.Request('GET', 'https://test.test/project'))
        response.raise_for_status()
    monkeypatch.setattr(recheck, 'fresh_project', fail)
    result = recheck.check_run(db, run.id)
    assert result['code'] == 'HTTP_502' and run.status == 'partial'


def test_schedule_once_one_minute_after_finish(setup):
    db, source, target, sr, tr = setup
    run = launch(setup); run.plan = {**run.plan, 'list_launch_id': str(uuid4())}; db.commit()
    sent = []
    assert not recheck.schedule_after_finish(db, run, lambda *args: sent.append(args))
    run.status = 'partial'
    assert recheck.schedule_after_finish(db, run, lambda *args: sent.append(args))
    assert not recheck.schedule_after_finish(db, run, lambda *args: sent.append(args))
    assert sent == [(run.id, 60)]


def test_cancelled_run_never_checked(setup, monkeypatch):
    db, run, tr, sr = completed(setup, monkeypatch)
    run.status = 'cancelled'; db.commit()
    monkeypatch.setattr(recheck, 'fresh_project', lambda *_: pytest.fail('Cancelled run must stay untouched'))
    assert recheck.check_run(db, run.id) is None


def test_only_manual_refresh_retries_planned_headings_once_per_request(setup, monkeypatch):
    db, run, tr, sr = completed(setup, monkeypatch)
    run.plan = {**run.plan, 'rewrite_title_h1': True}; db.commit()
    sent = []
    monkeypatch.setattr('app.reglue_title_h1.retry_saved', lambda db, r: sent.append(r.id))
    recheck.check_run(db, run.id)
    assert not sent
    recheck.check_run(db, run.id, retry_title_h1=True, request_id='click1')
    recheck.check_run(db, run.id, retry_title_h1=True, request_id='click1')
    assert sent == [run.id]
    tr.data['settings']['canon'] = 'unexpected.test'
    recheck.check_run(db, run.id, retry_title_h1=True, request_id='click2')
    assert sent == [run.id]  # Do not edit the wrong Main.


def test_maxa_name_from_fresh_webdev_preserves_brand_boundary():
    from app.mass_action_scope import brand_key
    assert brand_key('Maxa Casino') == brand_key('Maxa')
    assert brand_key('Maxa') != brand_key('Fair Go')
