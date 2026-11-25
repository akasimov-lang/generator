import assert from 'node:assert/strict';
import {test} from 'node:test';
import {AuthTimeoutError, isTemporaryAuthError, recoverAuthSession, withAuthDeadline} from '../src/authSession.ts';

test('pending authentication terminates and cancels its network request', async () => {
  let signal;
  await assert.rejects(withAuthDeadline(s => { signal = s; return new Promise(() => {}); }, undefined, 15), /не ответил вовремя/);
  assert.equal(signal.aborted, true);
});

test('authentication success cancels the deadline without aborting a completed request', async () => {
  let signal;
  assert.deepEqual(await withAuthDeadline(async s => { signal = s; return {id:'editor'}; }, undefined, 15), {id:'editor'});
  await new Promise(resolve => setTimeout(resolve, 25));
  assert.equal(signal.aborted, false);
});

test('unmount cancels an in-flight session check', async () => {
  const controller = new AbortController();
  const pending = withAuthDeadline(() => new Promise(() => {}), controller.signal, 1000);
  controller.abort();
  await assert.rejects(pending, {name:'AbortError'});
});

test('an already cancelled check never makes a request', async () => {
  const controller = new AbortController();
  controller.abort();
  let calls = 0;
  await assert.rejects(withAuthDeadline(async () => { calls++; }, controller.signal), {name:'AbortError'});
  assert.equal(calls, 0);
});

test('upstream failure is preserved and a later retry can succeed', async () => {
  await assert.rejects(withAuthDeadline(async () => { throw new Error('Сервис авторизации временно недоступен.'); }), /временно недоступен/);
  assert.equal(await withAuthDeadline(async () => 'verified'), 'verified');
});

test('response body stalled after headers remains subject to the deadline', async () => {
  const response = new Response(new ReadableStream({start() {}}));
  await assert.rejects(withAuthDeadline(async () => response.json(), undefined, 15), /не ответил вовремя/);
});

test('session recovers automatically across deployment failures without a new token', async () => {
  const token = 'saved-session';
  const sentTokens = [];
  const retries = [];
  const user = await recoverAuthSession(async signal => {
    assert.equal(signal.aborted, false);
    sentTokens.push(token);
    if (sentTokens.length < 3) throw Object.assign(new Error('Unavailable'), {statusCode: 502});
    return {id: 'editor'};
  }, new AbortController().signal, error => retries.push(error.statusCode), 1);
  assert.deepEqual(user, {id: 'editor'});
  assert.deepEqual(sentTokens, [token, token, token]);
  assert.deepEqual(retries, [502, 502]);
});

test('network failure and authentication timeout are recoverable', async () => {
  const failures = [new TypeError('Failed to fetch'), new AuthTimeoutError('Timed out')];
  let calls = 0;
  const result = await recoverAuthSession(async () => {
    if (calls < failures.length) throw failures[calls++];
    return 'verified';
  }, new AbortController().signal, () => {}, 1);
  assert.equal(result, 'verified');
  assert.equal(calls, 2);
});

test('expired token and denied permissions stop session recovery immediately', async () => {
  for (const statusCode of [401, 403]) {
    const error = Object.assign(new Error('Rejected'), {statusCode});
    let calls = 0;
    let retries = 0;
    await assert.rejects(recoverAuthSession(async () => { calls++; throw error; },
      new AbortController().signal, () => { retries++; }, 1), failure => failure === error);
    assert.equal(calls, 1);
    assert.equal(retries, 0);
  }
});

test('leaving the recovery screen cancels scheduled retries', async () => {
  const controller = new AbortController();
  let calls = 0;
  const pending = recoverAuthSession(async () => {
    calls++;
    throw Object.assign(new Error('Unavailable'), {statusCode: 503});
  }, controller.signal, () => { queueMicrotask(() => controller.abort()); }, 10);
  await assert.rejects(pending, {name: 'AbortError'});
  await new Promise(resolve => setTimeout(resolve, 20));
  assert.equal(calls, 1);
});

test('cancelled checks do not start requests or accept late identity responses', async () => {
  const controller = new AbortController();
  controller.abort();
  let calls = 0;
  await assert.rejects(recoverAuthSession(async () => { calls++; }, controller.signal, () => {}), {name: 'AbortError'});
  assert.equal(calls, 0);
  const lateController = new AbortController();
  await assert.rejects(recoverAuthSession(async () => {
    lateController.abort();
    return {id: 'old-user'};
  }, lateController.signal, () => {}), {name: 'AbortError'});
});

test('only temporary failures qualify for automatic recovery', () => {
  assert.equal(isTemporaryAuthError({statusCode: 429}), true);
  assert.equal(isTemporaryAuthError({statusCode: 504}), true);
  assert.equal(isTemporaryAuthError({statusCode: 400}), false);
  assert.equal(isTemporaryAuthError(new Error('Unexpected application error')), false);
});
