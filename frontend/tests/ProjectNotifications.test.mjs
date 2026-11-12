import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';

const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {LogEntry}=await server.ssrLoadModule('/src/ProjectNotifications.tsx');
const item={id:'fibery:test',source:'fibery',status:'completed',code:'FIBERY_REGLUE',message:'Создана SEO-задача Fibery #33303',context:'Main: old.test → new.test',severity:'info',active:true,created_at:'2026-11-10T09:42:33Z',occurrences:1,task_url:'https://hzhz.fibery.io/favorites/Alfasearch_Config/SEO_Tasks/33303',task_title:'Переклей: old.test → new.test'};
const render=value=>renderToStaticMarkup(React.createElement(LogEntry,{item:value}));

test('notes show the Fibery task and open its link safely in a new tab',()=>{
 const html=render(item);
 assert.match(html,/SEO_Tasks\/33303/);assert.match(html,/Переклей: old.test → new.test/);
 assert.match(html,/target="_blank"/);assert.match(html,/rel="noopener noreferrer"/);
 assert.match(html,/Примечание/);assert.doesNotMatch(html,/Требует внимания/);
});

test('collecting notes expose the delay before a task exists',()=>{
 const html=render({...item,status:'collecting',task_url:undefined,context:'Создание задачи не ранее 12:42:33 МСК'});
 assert.match(html,/Собираем работы · 3 минуты/);assert.match(html,/12:42:33/);
 assert.doesNotMatch(html,/<a /);
});

test('notes never turn an arbitrary stored URL into an external task link',()=>{
 assert.doesNotMatch(render({...item,task_url:'https://other.example/SEO_Tasks/33303'}),/<a /);
 assert.doesNotMatch(render({...item,task_url:'javascript:alert(1)'}),/<a /);
});

test('notes link to the exact Webdev redirect request',()=>{
 const html=render({...item,code:'FIBERY_WEBDEV_REDIRECT',task_url:'https://hzhz.fibery.io/favorites/Alfasearch_Config/Webdev_Tasks/20274',task_title:'project.test — исправить /contacts'});
 assert.match(html,/href="https:\/\/hzhz.fibery.io\/favorites\/Alfasearch_Config\/Webdev_Tasks\/20274"/);
 assert.match(html,/project.test — исправить \/contacts/);
});
