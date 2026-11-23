import assert from 'node:assert/strict';
import test from 'node:test';
import { domainRedirectSource, normalizeRedirectAddress } from '../src/redirectAddress.ts';

test('pasted protocol and leading slashes are removed without changing the path',()=>{
 assert.equal(normalizeRedirectAddress(' /HTTPS://example.test/Dragonia-Casino/?x=A#Top '),'example.test/Dragonia-Casino/?x=A#Top');
 assert.equal(normalizeRedirectAddress('///example.test/offer/'),'example.test/offer/');
 assert.equal(normalizeRedirectAddress('http://example.test'),'example.test');
});

test('source normalizes pasted hostname for duplicate detection',()=>{
 assert.equal(domainRedirectSource(' /HTTPS://NAUKAPROGRAMOWANIA.PL/ '),'naukaprogramowania.pl');
});
test('page source is rejected with guidance before enqueue',()=>{
 assert.throws(()=>domainRedirectSource('naukaprogramowania.pl/courses/kurs-programowania/'),/Постраничные редиректы/);
});
test('URL path normalization cannot hide a page source',()=>{
 assert.throws(()=>domainRedirectSource('example.test/folder/..'),/Постраничные редиректы/);
});
test('source query and fragment are not silently discarded',()=>{
 assert.throws(()=>domainRedirectSource('example.test/?q=test#here'),/Постраничные редиректы/);
});
test('source credentials and default port are rejected',()=>{
 assert.throws(()=>domainRedirectSource('https://user:pass@example.test/'),/логина/);
 assert.throws(()=>domainRedirectSource('https://example.test:443/'),/порта/);
});
