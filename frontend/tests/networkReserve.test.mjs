import assert from 'node:assert/strict';
import test from 'node:test';
import { validateReserveSave } from '../src/networkReserve.ts';

const cached = { canon: 'main.test', reserve: '', domains: ['main.test', 'next.test', 'other.test'], revision: 'cached' };

test('saving an initially empty reserve accepts a fresh revision and unrelated settings changes', () => {
  validateReserveSave(cached, { ...cached, revision: 'fresh', alternateMarkup: 'updated', content_page_paths: ['/new/'] }, 'next.test');
});

test('does not overwrite a concurrent reserve or use a changed Main', () => {
  assert.throws(() => validateReserveSave(cached, { ...cached, reserve: 'other.test' }, 'next.test'), /изменился/);
  assert.throws(() => validateReserveSave(cached, { ...cached, canon: 'other.test' }, 'next.test'), /изменился/);
});

test('accepts the same reserve already saved by another request', () => {
  validateReserveSave(cached, { ...cached, reserve: 'next.test' }, 'next.test');
});

test('rejects removed domains, Main, empty selection and every AMP representation', () => {
  for (const fresh of [
    { ...cached, domains: ['main.test'] },
    { ...cached, amp: 'next.test' },
    { ...cached, amp_domains: ['next.test'] },
    { ...cached, domain_types: { 'next.test': 'amp' } },
  ]) assert.throws(() => validateReserveSave(cached, fresh, 'next.test'), /недоступен/);
  for (const domain of ['', 'main.test']) assert.throws(() => validateReserveSave(cached, cached, domain), /недоступен/);
});
