import copy
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app import models, project_network as network
from app.domain_placeholder_check import ensure_jobs
from app.cross_reglue import completed_domain_results
from test_project_network import env

WebdevRemote = network.Remote


def test_www_creation_wire_receipt_confirmation_and_delayed_check(env, monkeypatch):
    db, site, fake = env
    site.cache_server_ip = "dolphin"
    fake.data["settings"]["port"] = 1141
    before = network.read_network(db, site)
    monkeypatch.setattr(network, "get_settings", lambda: SimpleNamespace(
        project_cache_username="ai_seo_419", project_cache_url="https://webdev.test"))
    calls = []

    def respond(request):
        calls.append(json.loads(request.content))
        assert str(request.url) == "https://webdev.test/site-config/create"
        return httpx.Response(201, json={"jobId": "www-job", "skipped": []})

    remote = WebdevRemote(db, site)
    with httpx.Client(transport=httpx.MockTransport(respond)) as remote.client:
        fake.request = remote.request
        payload = network.NetworkChange(request_id=uuid4(), action="create_domains",
            revision=before["revision"], domains=["WWW.Textilbrno.CZ."])
        after = network.change_network(db, site, payload, "anton")
        assert calls[0]["domains"] == [{"id": f"{payload.request_id}-0",
            "domain": "textilbrno.cz", "wwwPrimary": True}]
        op = db.get(models.NetworkOperation, str(payload.request_id))
        assert op.request_payload["domains"][0]["domain"] == "www.textilbrno.cz"
        assert after["operations"][0]["domains"] == ["www.textilbrno.cz"]
        assert after["operations"][0]["status"] == "pending"
        job, = ensure_jobs(db, op)
        assert job.payload["url"] == "https://www.textilbrno.cz/"

        # Neither the bare domain nor the original erroneous double-www host
        # confirms the specific domain the user requested.
        fake.data["settings"]["domains"] += ["textilbrno.cz", "www.www.textilbrno.cz"]
        assert network.read_network(db, site)["operations"][0]["status"] == "pending"
        fake.data["settings"]["domains"].append("www.textilbrno.cz")
        confirmed = network.read_network(db, site)
        assert confirmed["operations"][0]["status"] == "confirmed"
        assert confirmed["canon"] == before["canon"]
        assert confirmed["alternateMarkup"] == before["alternateMarkup"]
        network.change_network(db, site, payload, "anton")
        assert len(calls) == 1


@pytest.mark.parametrize("domain,wire_domain,www", [
    ("example.test", "example.test", False),
    ("casino.example.test", "casino.example.test", False),
    ("casino.www.example.test", "casino.www.example.test", False),
    ("www.xn--bcher-kva.test", "xn--bcher-kva.test", True),
])
def test_wire_conversion_preserves_ordinary_subdomains_and_idn(domain, wire_domain, www):
    payload = {"domains": [{"id": "row", "domain": domain, "wwwPrimary": False}]}
    original = copy.deepcopy(payload)
    assert network.site_config_create_payload(payload)["domains"] == [
        {"id": "row", "domain": wire_domain, "wwwPrimary": www}]
    assert payload == original


def test_www_job_stream_matches_receipt_without_duplicating_prefix(monkeypatch):
    monkeypatch.setattr(network, "get_settings", lambda: SimpleNamespace(project_cache_url="https://webdev.test"))
    raw = {"state": "completed", "domains": [{"id": "row", "domain": "textilbrno.cz",
        "wwwPrimary": True, "status": "success"}], "result": {"successCount": 1, "errorCount": 0,
        "domains": [{"id": "row", "domain": "www.textilbrno.cz", "wwwPrimary": True, "status": "success"}]}}
    remote = WebdevRemote(None, None)
    with httpx.Client(headers={"Authorization": "Bearer test-only"}, transport=httpx.MockTransport(
        lambda _: httpx.Response(200, text="data: " + json.dumps(raw) + "\n\n"))) as remote.client:
        job = remote.job_state("www-job")
    op = models.NetworkOperation(action="create_domains", request_payload={"domains": [{"domain": "www.textilbrno.cz"}]})
    assert job["domains"][0]["domain"] == "www.textilbrno.cz"
    assert job["result"]["domains"][0]["domain"] == "www.textilbrno.cz"
    assert completed_domain_results(job, op)
    assert raw["domains"][0]["domain"] == "textilbrno.cz"


@pytest.mark.parametrize("action", ["create_domains", "create_subdomains"])
def test_double_www_rejected_before_remote(env, monkeypatch, action):
    db, site, _ = env
    network.read_network(db, site)
    monkeypatch.setattr(network, "Remote", lambda *_: pytest.fail("Invalid input must not reach Webdev"))
    with pytest.raises(ValueError, match="Повторный префикс www"):
        network.change_network(db, site, network.NetworkChange(request_id=uuid4(),
            action=action, revision="unused", domains=["www.www.main.test"]), "anton")


@pytest.mark.parametrize("known,requested", [
    (["example.test"], ["www.example.test"]),
    (["www.example.test"], ["example.test"]),
])
def test_www_alias_of_existing_network_domain_is_rejected(known, requested):
    with pytest.raises(ValueError, match="уже есть в сетке"):
        network.validate_subdomains(requested, known, require_parent=False)


@pytest.mark.parametrize("requested", [["example.test", "www.example.test"], ["www.example.test", "example.test"]])
def test_conflicting_www_variants_in_one_batch_are_rejected(requested):
    with pytest.raises(ValueError, match="один вариант домена"):
        network.validate_subdomains(requested, [], require_parent=False)


def test_duplicate_same_www_input_is_deduplicated():
    assert network.validate_subdomains(["WWW.Example.TEST", "www.example.test"], [],
        require_parent=False) == ["www.example.test"]


def test_domain_deletion_keeps_exact_www_host(monkeypatch):
    monkeypatch.setattr(network, "get_settings", lambda: SimpleNamespace(project_cache_url="https://webdev.test"))
    calls = []
    remote = WebdevRemote(None, None)
    def respond(request):
        calls.append(json.loads(request.content))
        return httpx.Response(201, json={"jobId": "delete-job"})
    with httpx.Client(transport=httpx.MockTransport(respond)) as remote.client:
        remote.request("POST", "/site-config/delete", {"domains": ["www.example.test"]})
    assert calls == [{"domains": ["www.example.test"]}]
