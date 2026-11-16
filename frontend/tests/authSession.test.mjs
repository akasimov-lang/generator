import assert from 'node:assert/strict';
import {test} from 'node:test';
import {withAuthDeadline} from '../src/authSession.ts';

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
