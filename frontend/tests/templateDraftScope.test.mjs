import assert from 'node:assert/strict';
import { after, test } from 'node:test';
import { createServer } from 'vite';

const server = await createServer({ configFile: false, root: new URL('..', import.meta.url).pathname,
  server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true, include: [] }, appType: 'custom' });
after(() => server.close());
const { normalizeDraftGeo, normalizeDraftLanguage, sourceLocaleHint, readDraftScope,
  hasStoredDraftScope, saveDraftScope, recoverDraftLocale } = await server.ssrLoadModule('/src/templateDraftScope.ts');
const source = (id, locale = {}) => ({ id, hasHtml: true, ...locale });
const memory = () => {
  const values = new Map();
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
};
const scope = { brand: 'Онлайн казино', geo: 'PL', language: 'pl', brandEdited: true };

test('legacy saved Polish internal page restores GEO and language from explicit HTML locale', () => {
  const hint = sourceLocaleHint('https://www.empatyczny-ai.pl/o-projekcie/', 'pl-PL');
  assert.deepEqual(recoverDraftLocale({ geo: '', language: '' }, [source('existing-draft', hint)], null), { geo: 'PL', language: 'pl' });
});

test('restored source without a regional locale uses matching country domain', () => {
  assert.deepEqual(sourceLocaleHint('https://www.empatyczny-ai.pl/o-projekcie/', 'pl'), { suggestedGeo: 'PL', suggestedLanguage: 'pl' });
});

test('language alone does not invent a country for a generic domain', () => {
  assert.deepEqual(sourceLocaleHint('https://example.com/about/', 'en'), { suggestedGeo: '', suggestedLanguage: 'en' });
});

test('generic use of a country suffix does not choose a GEO', () => {
  assert.deepEqual(sourceLocaleHint('https://example.ai/about/', 'en'), { suggestedGeo: '', suggestedLanguage: 'en' });
});

test('country suffix must agree with page language before becoming a GEO hint', () => {
  assert.deepEqual(sourceLocaleHint('https://example.pl/about/', 'en'), { suggestedGeo: '', suggestedLanguage: 'en' });
});

test('og locale supplies region only when it agrees with the HTML language', () => {
  assert.deepEqual(sourceLocaleHint('https://example.com/', 'pl', 'pl_PL'), { suggestedGeo: 'PL', suggestedLanguage: 'pl' });
  assert.deepEqual(sourceLocaleHint('https://example.com/', 'de', 'pl_PL'), { suggestedGeo: '', suggestedLanguage: 'de' });
});

test('query locale spellings normalize to supported combobox values', () => {
  assert.equal(normalizeDraftGeo('pl_PL'), 'PL');
  assert.equal(normalizeDraftGeo('en-GB'), 'GB');
  assert.equal(normalizeDraftGeo('UK'), 'GB');
  assert.equal(normalizeDraftLanguage('pl-PL'), 'pl');
  assert.equal(normalizeDraftGeo('unknown'), '');
  assert.equal(normalizeDraftLanguage('unknown'), '');
});

test('reload restores selected scope for exactly the persisted source IDs', () => {
  const storage = memory();
  saveDraftScope([source('saved')], { ...scope, language: 'en' }, storage);
  assert.deepEqual(readDraftScope([source('saved')], storage), { ...scope, language: 'en' });
  assert.equal(readDraftScope([source('different-user-or-draft')], storage), null);
});

test('saved manual language is kept even if HTML has a different language', () => {
  const saved = { ...scope, language: 'en' };
  assert.deepEqual(recoverDraftLocale({ geo: '', language: '' }, [source('saved', { suggestedGeo: 'PL', suggestedLanguage: 'pl' })], saved), { geo: 'PL', language: 'en' });
});

test('current manual selections win over an asynchronously restored scope', () => {
  assert.deepEqual(recoverDraftLocale({ geo: 'DE', language: 'en' }, [source('saved', { suggestedGeo: 'PL', suggestedLanguage: 'pl' })], scope), { geo: 'DE', language: 'en' });
});

test('explicitly cleared GEO and language remain empty after source refresh', () => {
  assert.deepEqual(recoverDraftLocale({ geo: '', language: '' }, [source('saved', { suggestedGeo: 'PL', suggestedLanguage: 'pl' })], scope, { geo: true, language: true }), { geo: '', language: '' });
});

test('source refresh with no locale evidence does not clear valid current fields', () => {
  assert.deepEqual(recoverDraftLocale({ geo: 'PL', language: 'en' }, [], null), { geo: 'PL', language: 'en' });
});

test('an explicit GEO without language uses its default rather than a conflicting source', () => {
  assert.deepEqual(recoverDraftLocale({ geo: 'DE', language: '' }, [source('saved', { suggestedGeo: 'PL', suggestedLanguage: 'pl' })], scope), { geo: 'DE', language: 'de' });
});

test('mixed source GEOs do not silently select the first competitor scope', () => {
  assert.deepEqual(recoverDraftLocale({ geo: '', language: '' }, [source('one', { suggestedGeo: 'PL', suggestedLanguage: 'pl' }), source('two', { suggestedGeo: 'DE', suggestedLanguage: 'de' })], null), { geo: '', language: '' });
});

test('unrelated saved source scopes are not combined', () => {
  const storage = memory();
  saveDraftScope([source('one')], scope, storage);
  saveDraftScope([source('two')], { ...scope, geo: 'DE', language: 'de' }, storage);
  assert.equal(readDraftScope([source('one'), source('two')], storage), null);
  assert.equal(hasStoredDraftScope([source('one'), source('two')], storage), true);
});

test('uninitialized fields cannot overwrite an existing source scope', () => {
  const storage = memory();
  saveDraftScope([source('saved')], scope, storage);
  saveDraftScope([source('saved')], { ...scope, geo: '', language: '' }, storage);
  assert.deepEqual(readDraftScope([source('saved')], storage), scope);
});

test('empty HTML rows do not influence restored context', () => {
  const storage = memory();
  saveDraftScope([source('saved')], scope, storage);
  assert.deepEqual(readDraftScope([source('saved'), { id: 'blank', hasHtml: false }], storage), scope);
});

test('unavailable local storage leaves HTML-based recovery usable', () => {
  const storage = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('quota'); } };
  assert.doesNotThrow(() => saveDraftScope([source('saved')], scope, storage));
  assert.equal(readDraftScope([source('saved')], storage), null);
  assert.equal(hasStoredDraftScope([source('saved')], storage), false);
});
