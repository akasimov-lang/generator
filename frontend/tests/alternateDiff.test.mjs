import {test} from 'node:test';
import assert from 'node:assert/strict';
import {alternateDiff} from '../src/alternateDiff.mjs';
const link=(host,path='/',lang='hu')=>`<link rel="alternate" hreflang="${lang}" href="https://${host}${path}" />`;
test('identical markup has no green characters',()=>{
 const text=link('a.test');const diff=alternateDiff(text,text);
 assert.equal(diff.map(x=>x.text).join(''),text);assert.ok(diff.every(x=>!x.changed));
});
test('only added path characters change',()=>{
 const after=link('a.test','/hu2/'),diff=alternateDiff(link('a.test','/hu/'),after);
 assert.equal(diff.map(x=>x.text).join(''),after);assert.equal(diff.filter(x=>x.changed).map(x=>x.text).join(''),'2');
});
test('hreflang reordering is not a text change',()=>{
 const a=link('a.test','/','hu'),b=link('b.test','/hu/','hu-HU');
 assert.ok(alternateDiff(a+'\n'+b,b+'\n'+a).every(x=>!x.changed));
});
test('new link is green and removed content never appears in future markup',()=>{
 const after=link('new.test','/','en'),diff=alternateDiff(link('old.test'),after);
 assert.equal(diff.map(x=>x.text).join(''),after);assert.ok(diff.every(x=>x.changed));
});
test('deletion preserves future markup exactly',()=>{
 const after=link('a.test','/hu/');assert.equal(alternateDiff(link('a.test','/hu22/'),after).map(x=>x.text).join(''),after);
});
