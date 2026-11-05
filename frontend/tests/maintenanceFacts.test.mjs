import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {MaintenanceReportBody,normalizeMaintenanceReport}=await server.ssrLoadModule('/src/MaintenanceReport.tsx');
test('specialized report renders factual evidence without generic rewrite stages',()=>{
 const report=normalizeMaintenanceReport({task_type:'showcase_audit',entries:[{site_id:'x',project:'example.com',status:'completed',facts:[{label:'Брендов после',value:'10'},{label:'План — статус',value:'Подготовлен; не опубликован'}]}]});
 const html=renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report}));
 assert.match(html,/Брендов после/);assert.match(html,/Подготовлен; не опубликован/);
 assert.doesNotMatch(html,/Words|Подготовка проекта|Изменение контента|этапов/);
});
test('inventory lists every project compactly and distinguishes missing pages from failed checks',()=>{
 const report=normalizeMaintenanceReport({task_type:'showcase_inventory',inventory_excluded:[{project:'excluded.test',reason:'Сегодня изменяли витрину'}],entries:[{site_id:'a',project:'a.test',status:'partial',inventory:{home:{public:{presence:'present',count:3,brands:['A','B','C']}},internal_total:2,internal_present:1,internal_missing:0,internal_unknown:1,internal:[{slug:'/failed',public:{presence:'unknown',http:503}}]}},{site_id:'b',project:'b.test',status:'completed',inventory:{home:{public:{presence:'none'}},internal_total:0}}]});
 const html=renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report}));
 assert.match(html,/project-network\/a.test/);assert.match(html,/project-network\/b.test/);
 assert.match(html,/Есть: 1 \/ 2/);assert.match(html,/HTTP 503/);assert.match(html,/Нет внутренних страниц/);
 assert.match(html,/Не обнаружена/);assert.match(html,/Не подтверждено/);assert.match(html,/excluded.test/);
 assert.doesNotMatch(html,/Words|Подготовка проекта|Новый переклей/);
});
