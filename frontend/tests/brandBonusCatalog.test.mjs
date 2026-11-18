import assert from 'node:assert/strict';
import test from 'node:test';
import { bonusPath, bonusRoute, filterBonusBrands } from '../src/brandBonusCatalog.ts';

const brands = [
  { id: 'sample', name: 'Łódź', geo: 'PL', offers: [{ title: '100 PLN + 20 FS', facts: [{label:'Промокод',value:'WELCOME'}] }] },
  { id: 'sample', name: 'Český bonus', geo: 'CZ', offers: [{ title: '500 Kč', facts: [] }] },
];
test('country and brand URLs survive direct loading and trailing slashes', () => {
  assert.deepEqual(bonusRoute('/brand-bonuses/'), {geo:'',id:'',valid:true});
  assert.deepEqual(bonusRoute(bonusPath('PL', 'lemon-casino')), {geo:'PL',id:'lemon-casino',valid:true});
  assert.deepEqual(bonusRoute('/brand-bonuses/cz/sample/'), {geo:'CZ',id:'sample',valid:true});
  assert.equal(bonusRoute('/brand-bonuses/de').valid, false);
  assert.equal(bonusRoute('/brand-bonuses/pl/sample/missing').valid, false);
});
test('search supports Polish and Czech letters, amounts and promo codes', () => {
  assert.equal(filterBonusBrands(brands, '', 'lodz WELCOME')[0].geo, 'PL');
  assert.equal(filterBonusBrands(brands, '', 'CESKY 500')[0].geo, 'CZ');
  assert.equal(filterBonusBrands(brands, '', '20 FS').length, 1);
});
test('country selection never leaks another GEO and clearing restores full list', () => {
  assert.deepEqual(filterBonusBrands(brands, 'CZ', '100 PLN'), []);
  assert.equal(filterBonusBrands(brands, '', '').length, 2);
  assert.equal(filterBonusBrands(brands, 'PL', '').length, 1);
  assert.deepEqual(filterBonusBrands(brands, '', 'unknown'), []);
});
