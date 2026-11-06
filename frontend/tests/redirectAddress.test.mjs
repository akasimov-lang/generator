import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizeRedirectAddress } from '../src/redirectAddress.ts';

test('pasted protocol and leading slashes are removed without changing the path',()=>{
 assert.equal(normalizeRedirectAddress(' /HTTPS://example.test/Dragonia-Casino/?x=A#Top '),'example.test/Dragonia-Casino/?x=A#Top');
 assert.equal(normalizeRedirectAddress('///example.test/offer/'),'example.test/offer/');
 assert.equal(normalizeRedirectAddress('http://example.test'),'example.test');
});
