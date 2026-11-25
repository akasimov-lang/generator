import assert from 'node:assert/strict';
import {after, test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const server = await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(() => server.close());
const {RedirectSchemeHeader} = await server.ssrLoadModule('/src/RedirectSchemeHeader.tsx');
const render = props => renderToStaticMarkup(React.createElement(RedirectSchemeHeader, props));
const base = {backHref:'/project-network/project.test/',canon:'main.test',domains:[],types:{},redirectCount:0};

test('scheme header identifies the project, current Main and current redirect count beside Back', () => {
  const html = render({...base,fiberyName:'#329_Mostbet_AZ',canon:'www.main.test',redirectCount:12});
  assert.match(html,/<a[^>]+href="\/project-network\/project.test\/">Назад<\/a>/);
  assert.match(html,/<dt>Fibery<\/dt><dd[^>]*>#329_Mostbet_AZ<\/dd>/);
  assert.match(html,/<dt>Main<\/dt><dd>www.main.test<\/dd>/);
  assert.match(html,/<dt>Редиректы<\/dt><dd>12<\/dd>/);
  assert.match(render({...base,redirectCount:13}), /<dt>Редиректы<\/dt><dd>13<\/dd>/);
});

test('network totals include unused members and a Main drop, deduplicate www aliases and exclude AMP and unknown types', () => {
  const html = render({...base,domains:['main.test','www.main.test','unused-drop.test','unused-new.test','amp.test','unknown.test'],types:{'main.test':'drop','www.main.test':'drop','unused-drop.test':'drop','unused-new.test':'newreg','amp.test':'amp'}});
  assert.match(html, /<dt>Дропы<\/dt><dd>2<\/dd>/);
  assert.match(html, /<dt>Новореги<\/dt><dd>1<\/dd>/);
  assert.match(html, /<dt>Редиректы<\/dt><dd>0<\/dd>/);
});

test('missing project metadata is explicit and empty networks display zero counts', () => {
  const html = render({...base,canon:''});
  assert.match(html, /<dt>Fibery<\/dt><dd[^>]*>Не задано<\/dd>/);
  assert.match(html, /<dt>Main<\/dt><dd>—<\/dd>/);
  assert.match(html, /<dt>Новореги<\/dt><dd>0<\/dd>/);
  assert.match(html, /<dt>Дропы<\/dt><dd>0<\/dd>/);
});
