import assert from 'node:assert/strict';
import test from 'node:test';
import { parseNetworkDomainInput, formatNetworkDomainInput } from '../src/networkDomainInput.ts';

test('a copied root URL becomes a domain', () => {
  assert.deepEqual(parseNetworkDomainInput('https://bogtrykmuseet.dk/'), ['bogtrykmuseet.dk']);
});

test('escaped protocols and redundant outer slashes are removed', () => {
  assert.equal(formatNetworkDomainInput(String.raw`https\://bogtrykmuseet.dk/ HTTPS:\/\/Other.DK/// ///third.dk///`), 'bogtrykmuseet.dk\nother.dk\nthird.dk');
});

test('mixed separators become one domain per line with stable deduplication', () => {
  assert.equal(formatNetworkDomainInput('https://ONE.dk/, two.dk;\r\nhttp://one.dk\tthree.dk.\n'), 'one.dk\ntwo.dk\nthree.dk');
});

test('subdomains and www keep their identity', () => {
  assert.deepEqual(parseNetworkDomainInput('https://www.example.dk/ http://blog.example.dk/ example.dk'), ['www.example.dk', 'blog.example.dk', 'example.dk']);
});

test('paths, queries, ports and credentials stay visible for domain validation', () => {
  assert.deepEqual(parseNetworkDomainInput('https://example.dk/page/ https://example.dk/?x=1 https://example.dk:443/ https://user@example.dk/'), ['example.dk/page', 'example.dk/?x=1', 'example.dk:443', 'user@example.dk']);
});

test('copied markdown and numbered lists preserve their URL targets', () => {
  assert.equal(formatNetworkDomainInput('1. [First site](https://one.dk/)\n2) <https://two.dk/>\n• http://three.dk/\n- four.dk'), 'one.dk\ntwo.dk\nthree.dk\nfour.dk');
});

test('formatting is idempotent and empty input stays empty', () => {
  const text = formatNetworkDomainInput('https://one.dk/, two.dk');
  assert.equal(formatNetworkDomainInput(text), text);
  assert.equal(formatNetworkDomainInput(' ,;\n\t'), '');
});

test('lists beyond the submission limit are not silently truncated', () => {
  const input = Array.from({ length: 101 }, (_, i) => `https://site${i}.dk/`).join(', ');
  assert.equal(parseNetworkDomainInput(input).length, 101);
  assert.equal(formatNetworkDomainInput(input).split('\n').length, 101);
});
