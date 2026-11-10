import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {PilotReportGroups,reportGroupFromSearch}=await server.ssrLoadModule('/src/PilotReportGroups.tsx');
const {pilotTaskListPath}=await server.ssrLoadModule('/src/PilotTaskSearch.tsx');
test('compact groups expose the selected state and totals accessibly',()=>{
 const html=renderToStaticMarkup(React.createElement(PilotReportGroups,{value:'brands',counts:{all:63,layout:12,showcases:40,reglues:5,brands:4,other:2},onChange(){}}));
 assert.match(html,/aria-label="Группы отчётов"/);assert.equal((html.match(/aria-pressed="true"/g)||[]).length,1);
 assert.match(html,/aria-pressed="true"[^>]*>Бренды/);assert.match(html,/63 отчётов/);assert.match(html,/Вёрстка/);assert.match(html,/Витрины/);assert.match(html,/Переклеи/);
});
test('group and search survive page navigation without sharing another cache key',()=>{
 assert.equal(pilotTaskListPath(50,' Lemon ','brands'),'/auto-reglue/pilot/tasks?offset=50&q=Lemon&group=brands');
 assert.equal(reportGroupFromSearch('?group=brands'),'brands');assert.equal(reportGroupFromSearch('?group=invalid'),'all');
 assert.notEqual(pilotTaskListPath(0,'','brands'),pilotTaskListPath(0,'','layout'));
});
