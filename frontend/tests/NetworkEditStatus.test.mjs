import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import {createServer} from 'vite';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {NetworkEditQueue} from '../src/networkEditQueue.ts';
const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {DomainRedirects}=await server.ssrLoadModule('/src/DomainRedirects.tsx');
const {PageRedirects}=await server.ssrLoadModule('/src/PageRedirects.tsx');

test('submitted domain row has status instead of buttons while next row is editable',()=>{
  const queue=new NetworkEditQueue('site',async()=>new Promise(()=>{}));
  queue.enqueue({action:'domain_redirect',revision:'r',expected:{rows:[]},redirect_source:'one.test',redirect_original_source:'one.test',redirect_target:'new.test'});
  const html=renderToStaticMarkup(React.createElement(DomainRedirects,{redirects:[{url:'one.test',value:'main.test'},{url:'two.test',value:'main.test'}],canon:'main.test',revision:'r',available:true,disabled:true,queue,onSave:async()=>true,onRetargetMain:async()=>true}));
  assert.match(html,/Отправляем на сервер/);
  assert.doesNotMatch(html,/aria-label="Редактировать редирект one.test"/);
  const button=html.match(/<button[^>]*aria-label="Редактировать редирект two.test"[^>]*>/)[0];
  assert.doesNotMatch(button,/disabled/);
  assert.match(html,/new.test/);
});

test('queued page redirect hides its actions and preserves editing of another path',()=>{
  const queue=new NetworkEditQueue('site',async()=>new Promise(()=>{}));
  queue.enqueue({action:'page_redirect',revision:'r',expected:{rows:[]},page_redirect_domain:'main.test',page_redirect_source:'/one/',page_redirect_target:'https://main.test/new/'});
  const html=renderToStaticMarkup(React.createElement(PageRedirects,{groups:[{domain:'main.test',redirects:[{url:'/one/',value:'https://main.test/'},{url:'/two/',value:'https://main.test/'}]}],domains:['main.test'],canon:'main.test',revision:'r',available:true,disabled:true,queue,onSave:async()=>true}));
  assert.doesNotMatch(html,/aria-label="Изменить постраничный редирект main.test\/one\/"/);
  const button=html.match(/<button[^>]*aria-label="Изменить постраничный редирект main.test\/two\/"[^>]*>/)[0];
  assert.doesNotMatch(button,/disabled/);
  assert.match(html,/Отправляем на сервер/);
});
