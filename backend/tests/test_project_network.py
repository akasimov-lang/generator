import copy
from contextlib import nullcontext
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models, project_network as network
from app.db import Base
from app.network_state import observe_network, validate_markup, project_network_state

MARKUP = '<link rel="alternate" hreflang="x-default" href="https://old.test/" />\n<link rel="alternate" hreflang="cz" href="https://main.test/" />'


def test_malformed_optional_cache_fields_do_not_break_sync():
    assert project_network_state({"settings": ["invalid"], "head": "invalid"})["domains"] == []
    assert project_network_state({"settings": {"domains": [None, 123, {"domain": "https://valid.test"}]}, "head": {"alternateMarkup": []}})["domains"] == ["valid.test"]


@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        site = models.Site(name="project.test", base_url="https://main.test", publication_endpoint="https://main.test/api/content", cache_canon="main.test")
        db.add(site); db.commit()
        class FakeRemote:
            def __init__(self):
                self.calls, self.fail, self.delayed, self.reachable = [], None, False, True
                self.data = {
                    "settings": {"canon": "main.test", "prev": "old.test", "reserve": "reserve.test", "reserveOption": "reserve.test", "domains": ["main.test", "reserve.test", "next.test"], "alternate": {"fakeMain": ["/cz/"], "currentFakeMain": "/cz/"}},
                    "head": {"alternateMarkup": MARKUP, "enableAlternates": True, "canonicalDefaultMarkup": "untouched", "customHeaders": [{"key": "X-Test", "value": "keep"}]},
                }
            def project(self): return copy.deepcopy(self.data)
            def job_state(self, job_id): return None
            def request(self, method, path, payload):
                self.calls.append((method, path, copy.deepcopy(payload)))
                if path.endswith("check-domain"): return 200, {"reachable": self.reachable, "reason": "unavailable"}
                if self.fail: raise self.fail
                if self.delayed: return 200, {"message": "queued"}
                if path.endswith("update-value"):
                    self.data["settings"].update({key: value for key, value in payload.items() if key != "folder"})
                elif path.endswith("update-reglue"):
                    self.data["settings"]["prev"] = self.data["settings"]["canon"]
                    self.data["settings"]["canon"] = payload["reserve"]
                else:
                    self.data["head"].update({key: payload[key] for key in ("alternateMarkup", "enableAlternates")})
                return 200, {"message": "ok"}
        remote = FakeRemote()
        monkeypatch.setattr(network, "Remote", lambda *_: nullcontext(remote))
        yield db, site, remote


def change(env, action, revision, **kwargs):
    return network.change_network(env[0], env[1], network.NetworkChange(request_id=uuid4(), action=action, revision=revision, **kwargs), "anton")


def test_history_survives_changes_and_ignores_fake_main(env):
    db, site, remote = env
    first = network.read_network(db, site)
    assert first["main_history"] == ["main.test", "old.test"]
    assert first["x_default_history"] == ["old.test"]
    remote.data["head"]["alternateMarkup"] = '<link href="https://new.test/" hreflang="X-DEFAULT" rel="alternate" />'
    remote.data["settings"]["canon"] = "next.test"
    second = network.read_network(db, site)
    assert second["x_default_history"] == ["old.test", "new.test"]
    assert second["main_history"] == ["main.test", "old.test", "next.test"]
    observe_network(site, {"settings": remote.data["settings"]})
    assert site.network_state["alternateMarkup"] == remote.data["head"]["alternateMarkup"]


def test_templated_x_default_tracks_actual_canonical_domain(env):
    db, site, remote = env
    remote.data["head"]["alternateMarkup"] = '<link rel="alternate" hreflang="x-default" href="https://{{settings.canon}}{{reqPath}}" />'
    assert network.read_network(db, site)["x_default_history"] == ["main.test"]
    remote.data["settings"]["canon"] = "next.test"
    assert network.read_network(db, site)["x_default_history"] == ["main.test", "next.test"]


def test_reserve_then_reglue_exact_contract(env):
    db, site, remote = env
    before = network.read_network(db, site)
    with pytest.raises(network.NetworkConflict, match="Сначала сохраните"):
        change(env, "reglue", before["revision"], domain="next.test")
    assert not remote.calls
    saved = change(env, "reserve", before["revision"], domain="next.test")
    assert remote.calls[-1] == ("POST", "/projects/update-value", {"folder": "project.test", "reserve": "next.test", "reserveOption": "next.test"})
    assert saved["operations"][0]["status"] == "confirmed"
    after = change(env, "reglue", saved["revision"], domain="next.test")
    assert not any(path.endswith("check-domain") for _, path, _ in remote.calls)
    assert remote.calls[-1] == ("POST", "/projects/update-reglue", {"folder": "project.test", "reserve": "next.test", "trigger": "webdev:settings", "initiator": "anton"})
    assert after["canon"] == "next.test"
    assert "main.test" in after["main_history"]
    assert after["alternateMarkup"] == MARKUP


def test_alternates_preserve_settings_and_other_head_fields(env):
    db, site, remote = env
    before = network.read_network(db, site)
    old_settings = copy.deepcopy(remote.data["settings"])
    markup = MARKUP.replace("old.test", "next.test")
    after = change(env, "alternates", before["revision"], alternate_markup=markup, enable_alternates=False)
    assert remote.calls == [("PATCH", "/projects/update-head", {"folder": "project.test", "alternateMarkup": markup, "enableAlternates": False})]
    assert remote.data["settings"] == old_settings
    assert remote.data["head"]["canonicalDefaultMarkup"] == "untouched"
    assert remote.data["head"]["customHeaders"] == [{"key": "X-Test", "value": "keep"}]
    assert after["x_default_history"] == ["old.test", "next.test"]


def test_stale_revision_blocks_writes(env):
    db, site, remote = env
    before = network.read_network(db, site)
    remote.data["head"]["alternateMarkup"] = ""
    with pytest.raises(network.NetworkConflict, match="изменились"):
        change(env, "reserve", before["revision"], domain="next.test")
    assert not remote.calls


@pytest.mark.parametrize("domain", ["main.test", "outside.test", ""])
def test_invalid_reserve_blocked(env, domain):
    before = network.read_network(env[0], env[1])
    with pytest.raises(ValueError): change(env, "reserve", before["revision"], domain=domain)
    assert not env[2].calls


def test_unreachable_reserve_blocks_reglue(env):
    before = network.read_network(env[0], env[1])
    env[2].reachable = False
    payload = network.NetworkChange(request_id=uuid4(), action="reglue", revision=before["revision"], domain="reserve.test")
    with pytest.raises(ValueError, match="доступность"):
        network.change_network(env[0], env[1], payload, "scheduler", auto_run_id=str(uuid4()))
    assert len(env[2].calls) == 1
    assert env[2].calls[0][1].endswith("check-domain")


def test_timeout_persists_receipt_and_prevents_duplicate(env):
    db, site, remote = env
    before = network.read_network(db, site)
    remote.fail = httpx.ReadTimeout("timed out")
    payload = network.NetworkChange(request_id=uuid4(), action="reglue", revision=before["revision"], domain="reserve.test")
    after = network.change_network(db, site, payload, "anton")
    assert after["operations"][0]["status"] == "unknown"
    assert len(remote.calls) == 1
    network.change_network(db, site, payload, "anton")
    assert len(remote.calls) == 1
    with pytest.raises(network.NetworkConflict, match="не подтверждена"):
        change(env, "reglue", after["revision"], domain="reserve.test")
    remote.data["settings"]["canon"] = "reserve.test"
    assert network.read_network(db, site)["operations"][0]["status"] == "confirmed"


def test_delayed_operation_confirmed_only_by_readback(env):
    before = network.read_network(env[0], env[1])
    env[2].delayed = True
    after = change(env, "reserve", before["revision"], domain="next.test")
    assert after["operations"][0]["status"] == "pending"
    env[2].data["settings"].update(reserve="next.test", reserveOption="next.test")
    assert network.read_network(env[0], env[1])["operations"][0]["status"] == "confirmed"


def test_errors_in_http_200_are_not_success(env):
    before = network.read_network(env[0], env[1])
    env[2].request = lambda *args: (200, {"errors": ["failed"], "message": "Could not save"})
    after = change(env, "alternates", before["revision"], alternate_markup=MARKUP)
    assert after["operations"][0]["status"] == "failed"


@pytest.mark.parametrize("markup", [MARKUP, "", '<link rel="alternate" hreflang="cz" href="https://{{settings.canon}}{{reqPath}}" />'])
def test_supported_markup(markup): validate_markup(markup)


@pytest.mark.parametrize("markup", ['<script>alert(1)</script>', '<link rel="alternate" hreflang="x-default" href="javascript:alert(1)" />', '<link rel="alternate" hreflang="cz" href="https://" />', '<link rel="alternate" hreflang="cz" href="https://a.test/" onload="alert(1)" />', MARKUP + MARKUP])
def test_invalid_markup(markup):
    with pytest.raises(ValueError): validate_markup(markup)


def test_subdomain_rejected_locally_before_remote(env, monkeypatch):
    db, site, remote = env
    network.read_network(db, site)
    def forbidden(*args):
        raise AssertionError("Remote must not be entered for invalid cached domains")
    monkeypatch.setattr(network, "Remote", forbidden)
    for domains in (["test.outside.test"], ["main.test"], ["https://test.main.test"], ["www.main.test"]):
        with pytest.raises(ValueError):
            change(env, "create_subdomains", "unused", domains=domains)


def test_subdomain_creation_contract_confirmation_and_retry(env):
    db, site, remote = env
    site.cache_server_ip = "dolphin"
    remote.data["settings"]["port"] = 1141
    state = network.read_network(db, site)
    original = remote.request
    def request(method, path, payload):
        if path == "/site-config/create":
            remote.calls.append((method, path, copy.deepcopy(payload)))
            return 201, {"jobId": "1504", "skipped": []}
        return original(method, path, payload)
    remote.request = request
    payload = network.NetworkChange(request_id=uuid4(), action="create_subdomains", revision=state["revision"], domains=["test1.main.test", "test2.main.test", "test1.main.test"])
    result = network.change_network(db, site, payload, "anton")
    assert result["operations"][0]["status"] == "pending"
    method, path, body = remote.calls[0]
    assert (method, path) == ("POST", "/site-config/create")
    assert body["server"] == "dolphin.slf-hostesting.com"
    assert body["project"] == "project.test" and body["port"] == "1141"
    assert [item["domain"] for item in body["domains"]] == ["test1.main.test", "test2.main.test"]
    assert all(item["wwwPrimary"] is False for item in body["domains"])
    network.change_network(db, site, payload, "anton")
    assert len(remote.calls) == 1
    remote.data["settings"]["domains"] += ["test1.main.test", "test2.main.test"]
    confirmed = network.read_network(db, site)
    assert confirmed["operations"][0]["status"] == "confirmed"
    assert "test1.main.test" in site.cache_domains
    assert confirmed["canon"] == state["canon"]
    assert confirmed["alternateMarkup"] == state["alternateMarkup"]


def test_subdomain_parent_removed_remotely_blocks_creation(env):
    db, site, remote = env
    state = network.read_network(db, site)
    remote.data["settings"]["domains"].remove("next.test")
    with pytest.raises(network.NetworkConflict):
        change(env, "create_subdomains", state["revision"], domains=["test.next.test"])
    assert not remote.calls


def test_domain_types_persist_across_network_refresh_without_remote_write(env):
    db, site, remote = env
    network.read_network(db, site)
    saved = network.update_domain_type(db, site, network.DomainTypeUpdate(domain="main.test", domain_type="drop"))
    assert saved["domain_types"] == {"main.test": "drop", "reserve.test": "drop", "next.test": "drop"}
    network.update_domain_type(db, site, network.DomainTypeUpdate(domain="reserve.test", domain_type="newreg"))
    remote.data["settings"]["domains"].remove("main.test")
    result = network.read_network(db, site)
    assert result["domain_types"] == {"main.test": "drop", "reserve.test": "newreg", "next.test": "drop"}
    db.expire_all()
    assert db.get(models.Site, site.id).domain_types == result["domain_types"]
    assert not remote.calls
    with pytest.raises(ValueError, match="отсутствует"):
        network.update_domain_type(db, site, network.DomainTypeUpdate(domain="other.test", domain_type="drop"))
    with pytest.raises(ValueError):
        network.DomainTypeUpdate(domain="main.test", domain_type="unknown")


def test_subdomain_classification_tracks_parent_type_and_main_history(env):
    db, site, remote = env
    remote.data['settings']['domains'] += ['unused.main.test', 'old.main.test', 'deep.unused.main.test', 'unused.reserve.test', 'www.main.test', 'unrelated.co.uk']
    site.main_domain_history = ['old.main.test']
    db.commit()
    network.read_network(db, site)
    network.update_domain_type(db, site, network.DomainTypeUpdate(domain='main.test', domain_type='drop'))
    network.update_domain_type(db, site, network.DomainTypeUpdate(domain='reserve.test', domain_type='newreg'))
    result = network.read_network(db, site)['domain_classification']
    assert result['unused.main.test'] == dict(is_subdomain=True, parent_domain='main.test', parent_type='drop', unused_as_main=True)
    assert result['old.main.test']['unused_as_main'] is False
    assert result['deep.unused.main.test']['parent_domain'] == 'main.test'
    assert result['unused.reserve.test']['parent_type'] == 'newreg'
    assert result['www.main.test']['is_subdomain'] is False
    assert result['unrelated.co.uk']['is_subdomain'] is False
    changed = network.update_domain_type(db, site, network.DomainTypeUpdate(domain='main.test', domain_type='newreg'))
    assert changed['domain_classification']['unused.main.test']['parent_type'] == 'newreg'
    db.expire_all()
    assert network.read_network(db, site)['domain_classification']['unused.main.test']['parent_type'] == 'newreg'
    assert not remote.calls


def test_delete_domain_job_contract_confirmation_and_no_resend(env):
    db, site, remote = env
    site.cache_server_ip = 'dolphin'
    remote.data['settings']['domains'].append('test1.main.test')
    site.main_domain_history = ['test1.main.test']
    db.commit()
    state = network.read_network(db, site)
    def request(method, path, payload):
        remote.calls.append((method, path, copy.deepcopy(payload)))
        return 201, {'jobId': 'delete-job'}
    remote.request = request
    payload = network.NetworkChange(request_id=uuid4(), action='delete_domain', revision=state['revision'], domain='test1.main.test')
    result = network.change_network(db, site, payload, 'tester')
    assert result['operations'][0]['status'] == 'pending'
    assert result['operations'][0]['domain'] == 'test1.main.test'
    assert remote.calls[0][0:2] == ('POST','/site-config/delete')
    body = remote.calls[0][2]
    assert body['domains'] == ['test1.main.test']
    assert body['project'] == 'project.test'
    assert body['server'] == 'dolphin.slf-hostesting.com'
    assert 'port' not in body
    network.change_network(db, site, payload, 'tester')
    assert len(remote.calls) == 1
    remote.data['settings']['domains'].remove('test1.main.test')
    result = network.read_network(db, site)
    assert result['operations'][0]['status'] == 'confirmed'
    assert 'test1.main.test' not in result['domains']
    assert 'test1.main.test' in result['main_history']
    assert result['canon'] == state['canon'] and result['alternateMarkup'] == state['alternateMarkup']


def test_delete_domain_guards_and_terminal_job_failure(env, monkeypatch):
    db, site, remote = env
    site.cache_server_ip = 'dolphin'
    remote.data['settings']['domains'] += ['project.test','old.test']
    state = network.read_network(db, site)
    for domain in ['main.test', 'reserve.test', 'project.test', 'old.test', 'outside.test']:
        with pytest.raises(ValueError):
            change(env, 'delete_domain', state['revision'], domain=domain)
    assert not remote.calls
    remote.request = lambda *_: (201, {'jobId': 'failed-job'})
    result = change(env, 'delete_domain', state['revision'], domain='next.test')
    remote.job_state = lambda _: {'state': 'failed', 'error': 'permission denied'}
    result = network.read_network(db, site)
    assert result['operations'][0]['status'] == 'failed'
    assert result['operations'][0]['message'] == 'permission denied'
    assert 'next.test' in result['domains']


def test_amp_cache_and_partial_events(env):
    db, site, remote = env
    remote.data["settings"].update(amp="mobile.test", prevAmp="previous.test", ampDomains=["mobile.test", "previous.test"], ampList=["mobile.test"])
    state = network.read_network(db, site)
    assert state["amp_domains"] == ["mobile.test", "previous.test"]
    assert site.domain_types["mobile.test"] == "amp"
    observe_network(site, {"settings": {"canon": "main.test", "domains": ["main.test"]}})
    assert site.network_state["amp_domains"] == ["mobile.test", "previous.test"]
    observe_network(site, {"settings": {"ampDomains": [], "amp": "", "prevAmp": ""}})
    assert site.network_state["amp_domains"] == []


def test_amp_cannot_be_reserve_or_reglue(env):
    db, site, remote = env
    remote.data["settings"].update(amp="next.test", ampDomains=["next.test"])
    for action in ["reserve", "reglue"]:
        state = network.read_network(db, site)
        with pytest.raises(ValueError, match="AMP"):
            network.change_network(db, site, network.NetworkChange(request_id=uuid4(), action=action, revision=state["revision"], domain="next.test"), "admin")
    assert not remote.calls


def test_fake_main_creation_preserves_settings_and_receipt(env):
    db,site,remote=env
    remote.data['settings']['alternate']['custom']='keep'
    state=network.read_network(db,site)
    payload=network.NetworkChange(request_id=uuid4(),action='create_fake_main',revision=state['revision'],fake_main_path='test1')
    result=network.change_network(db,site,payload,'admin')
    assert result['operations'][0]['status']=='confirmed'
    assert result['fake_main_paths']==['/cz/','/test1/']
    assert result['fake_main_current']=='/cz/' and result['fake_main_enabled']
    assert remote.calls[0][0:2]==('POST','/projects/update-value')
    assert remote.calls[0][2]['alternate']['custom']=='keep'
    assert remote.data['head']['alternateMarkup']==MARKUP
    network.change_network(db,site,payload,'admin')
    assert len(remote.calls)==1


def test_fake_main_rejects_existing_content_and_unsafe_paths(env):
    db,site,remote=env
    remote.data['data']={'pages':[{'slug':'/test1/'}]}
    state=network.read_network(db,site)
    with pytest.raises(ValueError,match='обычная страница'):
        change(env,'create_fake_main',state['revision'],fake_main_path='test1')
    for path in ['/', '../test1', 'https://example.com/a', 'test?x=1', 'api/test']:
        with pytest.raises(ValueError):change(env,'create_fake_main',state['revision'],fake_main_path=path)
    assert not remote.calls


def test_manual_reglue_does_not_require_check_or_create_auto_run(env):
    from sqlalchemy import select
    db, site, remote = env
    before = network.read_network(db, site)
    remote.reachable = False
    result = change(env, 'reglue', before['revision'], domain='reserve.test')
    assert result['canon'] == 'reserve.test'
    assert not any(path.endswith('check-domain') for _, path, _ in remote.calls)
    assert not db.scalars(select(models.AutoReglueRun)).all()
