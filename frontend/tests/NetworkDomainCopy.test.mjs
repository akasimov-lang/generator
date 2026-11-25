import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {copyNetworkDomain,NetworkDomainCopy}=await server.ssrLoadModule('/src/NetworkDomainCopy.tsx');

test('copy writes the complete domain with no row number, URL prefix or feedback text',async()=>{
  const descriptor=Object.getOwnPropertyDescriptor(globalThis,'navigator');
  const copied=[];
  Object.defineProperty(globalThis,'navigator',{value:{clipboard:{writeText:async text=>{copied.push(text);}}},configurable:true});
  try{await copyNetworkDomain('www.fivearrowsphotography.com');assert.deepEqual(copied,['www.fivearrowsphotography.com']);}
  finally{if(descriptor)Object.defineProperty(globalThis,'navigator',descriptor);else delete globalThis.navigator;}
});
test('clipboard failure is propagated so the UI cannot claim success',async()=>{
  const descriptor=Object.getOwnPropertyDescriptor(globalThis,'navigator');
  Object.defineProperty(globalThis,'navigator',{value:{clipboard:{writeText:async()=>{throw new Error('denied');}}},configurable:true});
  try{await assert.rejects(copyNetworkDomain('domain.test'),/denied/);}
  finally{if(descriptor)Object.defineProperty(globalThis,'navigator',descriptor);else delete globalThis.navigator;}
});
test('domain copying is a keyboard accessible button and preserves Main emphasis',()=>{
  const html=renderToStaticMarkup(React.createElement(NetworkDomainCopy,{domain:'www.main.test',emphasized:true}));
  assert.match(html,/<button[^>]*type="button"[^>]*class="networkDomainCopy emphasized"/);
  assert.match(html,/aria-label="Скопировать домен www.main.test"/);
  assert.match(html,/>www.main.test<\/button>/);
});
