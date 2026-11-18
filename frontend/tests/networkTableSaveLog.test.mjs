import test from 'node:test';
import assert from 'node:assert/strict';
import { NetworkTableSaveLog } from '../src/networkTableSaveLog.ts';

function storage() {
  const values = new Map();
  return {getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value)};
}
test('concurrent requests retain their own results and previous attempts after reload', () => {
  const saved = storage();
  const log = new NetworkTableSaveLog('anton', 'one', saved);
  const main = log.start('a.test', 'Main', 'Включено');
  const alternate = log.start('b.test', 'Alternate', 'Выключено');
  log.finish(alternate, 'Сервер временно недоступен.');
  assert.equal(log.getSnapshot().find(row => row.id === main).status, 'saving');
  log.finish(main);
  const retry = log.start('b.test', 'Alternate', 'Выключено');
  log.finish(retry);
  const restored = new NetworkTableSaveLog('anton', 'one', saved).getSnapshot();
  assert.equal(restored.length, 3);
  assert.equal(restored.find(row => row.id === alternate).message, 'Сервер временно недоступен.');
  assert.equal(restored.find(row => row.id === main).status, 'saved');
  assert.equal(restored.find(row => row.id === retry).status, 'saved');
});
test('reload cannot claim a pending request saved and histories do not cross projects or users', () => {
  const saved = storage();
  const log = new NetworkTableSaveLog('anton', 'one', saved);
  const id = log.start('a.test', 'БАН', 'Включено');
  const restored = new NetworkTableSaveLog('anton', 'one', saved).getSnapshot();
  assert.equal(restored[0].id, id);
  assert.equal(restored[0].status, 'unknown');
  assert.equal(new NetworkTableSaveLog('anton', 'two', saved).getSnapshot().length, 0);
  assert.equal(new NetworkTableSaveLog('nina', 'one', saved).getSnapshot().length, 0);
});
