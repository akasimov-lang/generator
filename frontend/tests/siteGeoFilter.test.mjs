import assert from 'node:assert/strict';
import test from 'node:test';
import { siteGeoFilterCode } from '../src/siteGeoFilter.ts';

test('Czech Webdev GEO variants belong to one country', () => {
  for (const value of ['cs', 'CS', ' cs ', 'cz', 'CZ', 'cs-CZ', 'cz_CZ']) {
    assert.equal(siteGeoFilterCode(value), 'CZ', value);
  }
});

test('BetOnRed inventory counts all ten Czech projects, including three stored as cs', () => {
  const geos = ['cz', 'cs-CZ', 'cz', 'cz_CZ', 'cs', 'cs', 'cs-CZ', 'cz_CZ', 'cs-CZ', 'cs'];
  assert.equal(geos.filter(geo => siteGeoFilterCode(geo) === 'CZ').length, 10);
  assert.deepEqual([...new Set(geos.map(siteGeoFilterCode))], ['CZ']);
});

test('other countries and region-bearing locales retain their GEO', () => {
  for (const [value, expected] of [['pl', 'PL'], ['cs-SK', 'SK'], ['pt-BR', 'BR'], ['az_AZ', 'AZ'], ['de', 'DE']]) {
    assert.equal(siteGeoFilterCode(value), expected);
  }
});

test('empty and special filters remain unchanged', () => {
  for (const value of [null, undefined, '', ' ']) assert.equal(siteGeoFilterCode(value), '');
  assert.equal(siteGeoFilterCode('ALL'), 'ALL');
  assert.equal(siteGeoFilterCode('UNKNOWN'), 'UNKNOWN');
});
