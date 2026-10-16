import assert from 'node:assert/strict';
import test from 'node:test';
import { buildStandardAlternates } from '../src/standardAlternates.ts';

test('both random assignments use project locale and current fake path', () => {
  for (const [random, rootLanguage] of [[0, 'pl-PL'], [0.9, 'pl']]) {
    const markup = buildStandardAlternates('', 'pl-PL', 'PL', '/events/', () => random);
    assert.ok(markup.includes(`hreflang="${rootLanguage}" href="https://{{settings.canon}}/"`));
    assert.equal((markup.match(/<link /g) || []).length, 2);
    assert.ok(markup.includes('https://{{settings.canon}}/events/'));
  }
});
test('repeated generation replaces the pair and preserves other languages', () => {
  const extra = '<link rel="alternate" hreflang="x-default" href="https://other.test/" />';
  const first = buildStandardAlternates(extra, 'pl', 'PL', '/pl-pl/', () => 0);
  const next = buildStandardAlternates(first, 'pl', 'PL', '/events/', () => 1);
  assert.ok(next.includes(extra));
  assert.equal((next.match(/<link /g) || []).length, 3);
  assert.ok(!next.includes('/pl-pl/'));
});
test('missing project settings and invalid fake paths do not generate links', () => {
  for (const args of [[null, 'PL', '/pl/'], ['pl', null, '/pl/'], ['pl', 'PL', ''], ['pl', 'PL', '/'], ['pl', 'PL', '//other/']]) {
    assert.throws(() => buildStandardAlternates('', ...args));
  }
});
