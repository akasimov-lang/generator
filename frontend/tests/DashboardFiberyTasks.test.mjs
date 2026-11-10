import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';

const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {FiberyTaskRow}=await server.ssrLoadModule('/src/DashboardFiberyTasks.tsx');
const task={id:'33313',number:'33313',title:'Переклей: old.test → new.test',url:'https://hzhz.fibery.io/favorites/Alfasearch_Config/SEO_Tasks/33313',at:'2026-11-10T09:43:00Z',kind:'reglue',projects:[{id:'project',name:'project.test',fibery_name:'#626_BetOnRed_CZ',main:'new.test',url:'/project-network/project.test/'}]};
const render=value=>renderToStaticMarkup(React.createElement(FiberyTaskRow,{task:value}));

test('task row includes task and project links with Moscow time',()=>{
 const html=render(task);
 assert.match(html,/Переклей: old.test → new.test/);
 assert.match(html,/12:43/);assert.match(html,/Создана · #33313/);
 assert.match(html,/href="\/project-network\/project.test\/"/);
 assert.match(html,/href="https:\/\/hzhz.fibery.io\/favorites\/Alfasearch_Config\/SEO_Tasks\/33313"/);
 assert.match(html,/rel="noopener noreferrer"/);
});

test('deleted local project keeps the known Fibery project link',()=>{
 const html=render({...task,projects:[],project_number:'626',fibery_project_url:'https://hzhz.fibery.io/favorites/Alfasearch_Config/SEO_Projects/626'});
 assert.match(html,/Проект Fibery #626/);
 assert.doesNotMatch(html,/project-network/);
});

test('arbitrary external task links are never rendered',()=>{
 assert.doesNotMatch(render({...task,url:'javascript:alert(1)'}),/javascript:/);
 assert.doesNotMatch(render({...task,url:'https://untrusted.test/task'}),/untrusted/);
});
