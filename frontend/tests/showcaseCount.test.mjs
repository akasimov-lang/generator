import assert from 'node:assert/strict';
import {test} from 'node:test';
import {showcaseBrandCount} from '../src/showcaseCount.ts';

test('counts unique brands across showcase sources, excluding repeated cards', () => {
  assert.equal(showcaseBrandCount({management:{complete:true},rows:[{brand:'BetonRed'},{brand:'BetonRed Casino'},{brand:'BETON RED'},{brand:'Chance Casino'}]}),2);
});
test('confirmed empty showcase has zero brands', () => {
  assert.equal(showcaseBrandCount({management:{complete:true},rows:[]}),0);
});
test('missing templates do not produce a misleading count', () => {
  assert.equal(showcaseBrandCount({management:{complete:false},rows:[{brand:'Chance'}]}),null);
});
test('external showcase has an unknown number of brands', () => {
  assert.equal(showcaseBrandCount({management:{complete:true,sources:[{kind:'external'}]},rows:[]}),null);
});
