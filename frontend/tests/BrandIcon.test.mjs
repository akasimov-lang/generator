import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {after,test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const root=new URL('..',import.meta.url);
const icons=JSON.parse(readFileSync(new URL('src/brandIcons.json',root)));
const catalog=JSON.parse(readFileSync(new URL('public/brand-icons/catalog.json',root)));
const sources=JSON.parse(readFileSync(new URL('public/brand-icons/sources.json',root)));
const server=await createServer({configFile:false,root:root.pathname,server:{middlewareMode:true,hmr:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {BrandIcon}=await server.ssrLoadModule('/src/BrandIcon.tsx');
const render=brand=>renderToStaticMarkup(React.createElement(BrandIcon,{brand}));
test('every current catalog brand has a local logo with a recorded source and matching hash',()=>{
 for(const brand of catalog.brands){
  const key=brand.normalize('NFKC').toLowerCase().replace(/[^a-z0-9]/g,'');const path=icons[key];
  assert.ok(path?.startsWith('/brand-icons/'),brand);
  const file=new URL('public'+path,root);assert.ok(existsSync(file),brand);
  const evidence=sources.find(s=>'/brand-icons/'+s.file===path);assert.ok(evidence?.source,brand);
  assert.equal(createHash('sha256').update(readFileSync(file)).digest('hex'),evidence.sha256,brand);
  assert.match(render(brand),/<img /,brand);
 }
});
test('brand spelling variants use the same logo and a uniform image box',()=>{
 assert.match(render('Maxa Casino'),/\/brand-icons\/maxa.png/);
 assert.match(render('Vinder Casino'),/\/brand-icons\/vinder.png/);
 assert.match(render('NV Casino'),/width="26" height="22"/);
 assert.match(render('Joe Fortune'),/brandCatalogIcon/);
 assert.doesNotMatch(render('Общие ключи'),/<img /);
});
test('local SVG catalog assets have no scripts, event handlers or external resources',()=>{
 for(const path of new Set(Object.values(icons).filter(p=>p.endsWith('.svg')))){
  const svg=readFileSync(new URL('public'+path,root),'utf8');
  assert.doesNotMatch(svg,/<(?:script|foreignObject|iframe)\b|\son\w+\s*=|(?:xlink:)?href\s*=\s*["'](?:https?:|\/\/|data:|javascript:)/i,path);
 }
});
