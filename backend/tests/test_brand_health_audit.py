import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
import httpx
import pytest
from app import brand_health_audit as audit, maintenance_reports, maintenance_repeat


def test_welcome_placeholder_with_http_200_is_not_a_working_site():
    result = audit.classify('<title>Welcome</title><h1>Welcome to My Website</h1>', 200, 'Lemon Casino')
    assert result['outcome'] == 'placeholder'
    assert 'welcome to my website' in result['reason']


def test_placeholder_phrase_inside_a_full_article_is_not_enough():
    html = '<title>Pelican casino</title><p>' + 'Artykuł o grze. ' * 150 + ' welcome to my website</p>'
    assert audit.classify(html, 200, 'Pelican')['outcome'] == 'healthy'


def test_fresh_website_coming_soon_is_a_placeholder():
    html = '<title>A fresh website is coming soon</title><h1>A fresh website is coming soon</h1>'
    assert audit.classify(html, 200, 'Lemon Casino')['outcome'] == 'placeholder'


def test_http_500_is_never_reported_healthy_even_with_brand_content():
    assert audit.classify('<title>BetOnRed</title>' + 'casino ' * 200, 500, 'BetOnRed')['outcome'] == 'http_error'


def test_cloudflare_challenge_is_not_a_placeholder_or_working_site():
    assert audit.classify('<title>Just a moment...</title>Verify you are human', 403, 'Fontan')['outcome'] == 'blocked'


def test_an_unrelated_restored_site_is_flagged_for_content_review():
    assert audit.classify('<title>Yoga studio</title>' + 'Yoga studio classes ' * 100, 200, 'Fontan')['outcome'] == 'review'


def test_current_webdev_title_and_article_sample_confirm_the_page():
    html = '<title>Aktuální přehled</title><p>Podrobný článek se skutečným obsahem projektu.</p>'
    assert audit.classify(html, 200, 'BetOnRed', 'Aktuální přehled', ['Podrobný článek se skutečným obsahem projektu.'])['outcome'] == 'healthy'


async def public(_):
    pass


def test_redirect_chain_preserves_exact_selected_path_and_detects_loop():
    def response(request):
        target = '/contacts/' if request.url.path == '/contacts' else '/contacts'
        return httpx.Response(301, headers={'Location': target})
    result = asyncio.run(audit.probe('https://example.test/contacts', 'Lemon Casino',
        transport=httpx.MockTransport(response), validate=public))
    assert result['outcome'] == 'redirect_loop'
    assert [hop['url'] for hop in result['chain']] == ['https://example.test/contacts', 'https://example.test/contacts/']


def test_redirect_to_private_address_is_not_followed():
    calls = []
    async def validate(url):
        if '127.0.0.1' in url:
            raise ValueError('Non-public source address')
    def response(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={'Location': 'http://127.0.0.1/private'})
    result = asyncio.run(audit.probe('https://example.test/', 'Pelican',
        transport=httpx.MockTransport(response), validate=validate))
    assert result['outcome'] == 'unreachable'
    assert calls == ['https://example.test/']


def test_working_page_behind_redirect_is_distinguished_from_direct_200():
    def response(request):
        if request.url.path == '/old':
            return httpx.Response(301, headers={'Location': '/new'})
        return httpx.Response(200, text='<title>Pelican Casino</title>' + 'gra ' * 180)
    result = asyncio.run(audit.probe('https://example.test/old', 'Pelican',
        transport=httpx.MockTransport(response), validate=public))
    assert result['outcome'] == 'redirect'
    assert [hop['status'] for hop in result['chain']] == [301, 200]


def test_failures_are_rechecked_and_first_evidence_is_preserved(monkeypatch):
    calls = []
    async def probe(*args):
        calls.append(args)
        return {'outcome': 'placeholder', 'checked_at': str(len(calls))}
    monkeypatch.setattr(audit, 'probe', probe)
    result = asyncio.run(audit.checked_probe('https://example.test/', 'Fontan'))
    assert len(calls) == 2
    assert result['attempts'] == 2 and result['previous_attempt']['checked_at'] == '1'


def test_audit_view_is_compact_and_never_copies_private_gsc_values():
    at = datetime.now(timezone.utc)
    row = {'site_id': 'site', 'project': 'example.test', 'status': 'completed', 'brand': 'Pelican',
           'health': {'main': {'outcome': 'placeholder'}}, 'gsc': 'PRIVATE', 'before': {'large': 'archive'}}
    job = SimpleNamespace(id='report', kind='maintenance_report', status='completed', created_at=at, started_at=at,
        finished_at=at, updated_at=at, payload={'actor':'anton','name':'Audit','task_type':audit.TASK}, result={'entries':[row]})
    result = maintenance_reports.view(job)
    assert result['entries'][0]['health']['main']['outcome'] == 'placeholder'
    assert 'gsc' not in result['entries'][0] and 'before' not in result['entries'][0]
    assert result['progress']['percent'] == 100 and result['progress']['total'] == 1
    assert result['audit_only'] and not result['can_exclude']


def test_audit_cannot_launch_rewrite_or_reglue(monkeypatch):
    monkeypatch.setattr(maintenance_reports, 'get', lambda *args: SimpleNamespace(payload={'task_type': audit.TASK}))
    with pytest.raises(ValueError, match='отчёт проверки'):
        maintenance_repeat.create(None, 'report', 'request', {'username': 'anton'})
