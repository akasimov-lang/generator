import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import {createServer} from 'vite';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {SaveIndicator,QueueSaveIndicator}=await server.ssrLoadModule('/src/SaveIndicator.tsx');

test('error cause is visible text next to the icon and HTML is escaped',()=>{
 const html=renderToStaticMarkup(React.createElement(SaveIndicator,{state:'error',error:'Webdev: ENOTFOUND <old.test>'}));
 assert.match(html,/<span class="saveIndicatorText">Webdev: ENOTFOUND &lt;old.test&gt;<\/span>/);
});
test('queue indicator forwards exact failed operation message',()=>{
 const html=renderToStaticMarkup(React.createElement(QueueSaveIndicator,{label:'Резерв',items:[{id:'a',status:'failed',message:'Сетка занята',request:{action:'reserve'}}]}));
 assert.match(html,/<span class="saveIndicatorText">Сетка занята<\/span>/);
});
test('old successful receipt does not announce a new save on page load',()=>{
 const html=renderToStaticMarkup(React.createElement(SaveIndicator,{state:'saved',version:'old'}));
 assert.doesNotMatch(html,/Сохранено успешно!/);
 assert.match(html,/aria-hidden="true"/);
});
