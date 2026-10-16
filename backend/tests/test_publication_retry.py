import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from app import publication_retry as retry


@pytest.mark.parametrize('status', [408, 429, 500, 502, 503, 504, 520])
def test_six_total_attempts_five_ten_second_waits(monkeypatch, status):
    client = AsyncMock()
    client.post.return_value = httpx.Response(status)
    sleep = AsyncMock()
    monkeypatch.setattr(retry.asyncio, 'sleep', sleep)
    payload = {'page': {'id': 'stable-page-id'}}
    headers = {'Idempotency-Key': 'stable-key'}
    records = []
    result = asyncio.run(retry.post_publication(client, 'https://example.test', json=payload,
                                              headers=headers, on_retry=lambda *args: records.append(args)))
    assert result.status_code == status
    assert client.post.await_count == 6
    assert [call.args for call in sleep.await_args_list] == [(10,)] * 5
    assert [row[0] for row in records] == [1, 2, 3, 4, 5]
    assert all(call.kwargs == {'json': payload, 'headers': headers} for call in client.post.await_args_list)


@pytest.mark.parametrize('status', [200, 201, 400, 401, 403, 404, 409, 422])
def test_stops_on_success_or_permanent_error(monkeypatch, status):
    client = AsyncMock()
    client.post.side_effect = [httpx.Response(502), httpx.Response(status)]
    sleep = AsyncMock()
    monkeypatch.setattr(retry.asyncio, 'sleep', sleep)
    result = asyncio.run(retry.post_publication(client, 'https://example.test', json={}, headers={}))
    assert result.status_code == status
    assert client.post.await_count == 2
    sleep.assert_awaited_once_with(10)


def test_transport_failure_is_bounded(monkeypatch):
    client = AsyncMock()
    client.post.side_effect = httpx.ReadTimeout('timeout')
    sleep = AsyncMock()
    monkeypatch.setattr(retry.asyncio, 'sleep', sleep)
    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(retry.post_publication(client, 'https://example.test', json={}, headers={}))
    assert client.post.await_count == 6
    assert sleep.await_count == 5


def test_existing_page_before_manual_retry_prevents_any_post():
    client = AsyncMock()
    check = AsyncMock(return_value=httpx.Response(200, json={'confirmed_existing_page': True}))
    result = asyncio.run(retry.post_publication(client, 'https://example.test', json={}, headers={},
                                              before_retry=check, verify_first=True))
    assert result.status_code == 200
    client.post.assert_not_awaited()
    check.assert_awaited_once()


def test_unavailable_preflight_prevents_any_post():
    client = AsyncMock()
    check = AsyncMock(side_effect=httpx.ConnectError('unavailable'))
    with pytest.raises(httpx.ConnectError):
        asyncio.run(retry.post_publication(client, 'https://example.test', json={}, headers={},
                                           before_retry=check, verify_first=True))
    client.post.assert_not_awaited()
