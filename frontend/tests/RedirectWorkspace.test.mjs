import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {RedirectWorkspace}=await server.ssrLoadModule('/src/RedirectWorkspace.tsx');
const {PageRedirectWorkspace}=await server.ssrLoadModule('/src/PageRedirectWorkspace.tsx');
const base={canon:'main.test',revision:'one',available:true,disabled:false,onSave:async()=>true};
const locationDescriptor=Object.getOwnPropertyDescriptor(globalThis,'location');
Object.defineProperty(globalThis,'location',{value:{pathname:'/project-network/main.test/'},configurable:true});
after(()=>{if(locationDescriptor)Object.defineProperty(globalThis,'location',locationDescriptor);else delete globalThis.location;});
const counts=html=>[...html.matchAll(/<tbody>(.*?)<\/tbody>/g)].map(match=>(match[1].match(/<tr/g)||[]).length);
test('compact domain redirects show one header save status, remove obsolete actions and cap columns at fifteen rows',()=>{
  const redirects=Array.from({length:31},(_,i)=>({url:`source-${i}.test`,value:'main.test'}));
  const html=renderToStaticMarkup(React.createElement(RedirectWorkspace,{...base,redirects,domains:redirects.map(r=>r.url),onRetargetMain:async()=>true}));
  assert.deepEqual(counts(html),[15,15,1]);
  assert.match(html,/networkRedirectsHeading.*redirectSectionSaveStatus saved/);
  assert.doesNotMatch(html,/Подготовить подклей|Сохранить черновик|Схемы и копии|Подтверждённые настройки Webdev/);
  assert.equal((html.match(/redirectSectionSaveStatus/g)||[]).length,1);
});
test('page redirects use the same table layout and trash controls with exact paths',()=>{
  const groups=[{domain:'main.test',redirects:Array.from({length:16},(_,i)=>({url:i===0?'/page':'/page/'+i+'/',value:'https://main.test/new/'}))}];
  const html=renderToStaticMarkup(React.createElement(PageRedirectWorkspace,{...base,groups,domains:['main.test']}));
  assert.deepEqual(counts(html),[15,1]);
  assert.match(html,/redirectSectionSaveStatus saved/);
  assert.match(html,/value="\/page"/);
  assert.equal((html.match(/class="redirectTrashButton"/g)||[]).length,16);
  assert.equal((html.match(/role="combobox"/g)||[]).length,48);
  assert.doesNotMatch(html,/redirectPageRow|Подготовьте все строки/);
});
test('a failed Webdev receipt remains an error in the domain header after reload',()=>{
  const item={id:'failed-edit',status:'failed',message:'Webdev не подтвердил изменение',request:{action:'domain_redirect',revision:'one',expected:{rows:[]},redirect_source:'old.test',redirect_target:'main.test'}};
  const html=renderToStaticMarkup(React.createElement(RedirectWorkspace,{...base,redirects:[{url:'old.test',value:'main.test'}],domains:['old.test','main.test'],onRetargetMain:async()=>true,queue:{items:[item],latest:()=>item}}));
  assert.match(html,/networkRedirectsHeading.*redirectSectionSaveStatus error/);
  assert.doesNotMatch(html,/redirectSectionSaveStatus saved/);
});
