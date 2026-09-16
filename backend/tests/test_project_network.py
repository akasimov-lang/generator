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
            def request(self, method, path, payload):
                self.calls.append((method, path, copy.deepcopy(payload)))
                if path.endswith("check-domain"): return 200, {"reachable": self.reachable, "reason": "unavailable"}
                if self.fail: raise self.fail
                if self.delayed: return 200, {"message": "queued"}
                if path.endswith("update-value"):
                    self.data["settings"].update({key: payload[key] for key in ("reserve", "reserveOption")})
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
    assert remote.calls[-2] == ("POST", "/projects/check-domain", {"domain": "next.test"})
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
    with pytest.raises(ValueError, match="доступность"):
        change(env, "reglue", before["revision"], domain="reserve.test")
    assert len(env[2].calls) == 1
    assert env[2].calls[0][1].endswith("check-domain")


def test_timeout_persists_receipt_and_prevents_duplicate(env):
    db, site, remote = env
    before = network.read_network(db, site)
    remote.fail = httpx.ReadTimeout("timed out")
    payload = network.NetworkChange(request_id=uuid4(), action="reglue", revision=before["revision"], domain="reserve.test")
    after = network.change_network(db, site, payload, "anton")
    assert after["operations"][0]["status"] == "unknown"
    assert len(remote.calls) == 2
    network.change_network(db, site, payload, "anton")
    assert len(remote.calls) == 2
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
