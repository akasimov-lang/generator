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
