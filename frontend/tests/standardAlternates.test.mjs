import assert from 'node:assert/strict';
import test from 'node:test';
import { buildBaseAlternates, buildStandardAlternates } from '../src/standardAlternates.ts';

test('base scheme replaces all markup with the project language, GEO and canonical root', () => {
  for (const [language, geo] of [['pl', 'PL'], ['cs', 'CZ'], ['az', 'AZ'], ['de', 'DE'], ['pt-BR', 'BR']]) {
    const markup = buildBaseAlternates(language, geo, '/new/');
    const lang = language.split('-')[0];
    assert.equal((markup.match(/<link /g) || []).length, 3);
    assert.ok(markup.includes(`href="https://{{settings.canon}}/" hreflang="${lang}"`));
    assert.ok(markup.includes(`href="https://{{settings.canon}}/new/" hreflang="${lang}-${geo}"`));
    assert.ok(markup.includes('href="https://{{settings.canon}}/" hreflang="x-default"'));
  }
  for (const args of [[null, 'PL', '/new/'], ['pl', null, '/new/'], ['pl', 'PL', ''], ['pl', 'PL', '/'], ['pl', 'PL', '//other/'], ['pl', 'PL', '/new/?q=1']]) {
    assert.throws(() => buildBaseAlternates(...args));
  }
});

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

test('successive clicks alternate the fake route between language and language-GEO, including after reload', () => {
  for (const [lang, geo] of [['pl', 'PL'], ['az', 'AZ'], ['cs', 'CZ']]) {
    const first = buildBaseAlternates(lang, geo, '/polska/');
    const second = buildBaseAlternates(lang, geo, '/polska/', first);
    assert.ok(second.includes(`href="https://{{settings.canon}}/polska/" hreflang="${lang}"`));
    assert.ok(second.includes(`href="https://{{settings.canon}}/" hreflang="${lang}-${geo}"`));
    assert.ok(second.includes('href="https://{{settings.canon}}/" hreflang="x-default"'));
    assert.equal(buildBaseAlternates(lang, geo, '/polska/', second), first);
  }
  const stored = "<link hreflang='pl-PL' rel='alternate' href='https://site.test/polska/'/>";
  assert.ok(buildBaseAlternates('pl', 'PL', '/polska/', stored).includes('/polska/" hreflang="pl"'));
});
