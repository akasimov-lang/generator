import assert from 'node:assert/strict';
import {test} from 'node:test';
import {projectGscState} from '../src/projectGscState.ts';

const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => {resolve = a; reject = b;}); return {promise, resolve, reject}; };

test('autosave debounces typing and only sends the final text to its own project', async () => {
  const writes = [], done = deferred();
  const state = projectGscState('first', async (path, options) => {
    if (!options) return {value: ''};
    writes.push([path, JSON.parse(options.body)]); done.resolve(); return {value: 'abc'};
  }, 5);
  await state.load(); state.edit('a'); state.edit('ab'); state.edit('abc');
  await done.promise; await state.flush();
  assert.deepEqual(writes, [['/sites/first/gsc', {value: 'abc'}]]);
  assert.equal(state.snapshot().status, 'saved');
});

test('an edit during an in-flight save is serialized and never overwritten by the first response', async () => {
  const pending = deferred(), writes = [];
  const state = projectGscState('first', async (path, options) => {
    if (!options) return {value: 'old'};
    writes.push(JSON.parse(options.body).value);
    if (writes.length === 1) await pending.promise;
    return {value: writes.at(-1)};
  });
  await state.load(); state.edit('one'); const saving = state.flush();
  state.edit('two'); const again = state.flush();
  assert.deepEqual(writes, ['one']); pending.resolve(); await Promise.all([saving, again]);
  assert.deepEqual(writes, ['one', 'two']);
  assert.equal(state.snapshot().value, 'two'); assert.equal(state.snapshot().status, 'saved');
});

test('a failed save retains the draft and Enter/blur can retry without another edit', async () => {
  let fail = true;
  const state = projectGscState('first', async (path, options) => {
    if (!options) return {value: 'old'};
    if (fail) throw Error('offline');
    return {value: 'draft'};
  });
  await state.load(); state.edit('draft'); await state.flush();
  assert.deepEqual(state.snapshot(), {value: 'draft', loaded: true, status: 'error'});
  fail = false; await state.flush(); assert.equal(state.snapshot().status, 'saved');
});

test('leaving one project flushes its pending change without leaking into the next project', async () => {
  const firstWrite = deferred(), calls = [];
  const api = async (path, options) => {
    if (!options) return {value: path.includes('second') ? 'second saved' : ''};
    calls.push([path, JSON.parse(options.body).value]); await firstWrite.promise; return {value: 'first draft'};
  };
  const first = projectGscState('first', api); await first.load(); first.edit('first draft');
  const leaving = first.flush();
  const second = projectGscState('second', api); await second.load();
  firstWrite.resolve(); await leaving;
  assert.deepEqual(calls, [['/sites/first/gsc', 'first draft']]);
  assert.equal(second.snapshot().value, 'second saved');
});

test('clearing is saved and unchanged blur performs no write', async () => {
  const writes = [];
  const state = projectGscState('first', async (path, options) => {
    if (!options) return {value: 'old'};
    writes.push(JSON.parse(options.body)); return {value: ''};
  });
  await state.load(); await state.flush(); assert.equal(writes.length, 0);
  state.edit(''); await state.flush(); await state.flush();
  assert.deepEqual(writes, [{value: ''}]);
});

test('failed initial load cannot overwrite existing data with an empty value', async () => {
  let fail = true, writes = 0;
  const state = projectGscState('first', async (path, options) => {
    if (options) writes++;
    if (fail) throw Error('offline'); return {value: 'saved'};
  });
  await state.load(); state.edit(''); await state.flush(); assert.equal(writes, 0);
  fail = false; await state.load(); assert.equal(state.snapshot().value, 'saved');
});
