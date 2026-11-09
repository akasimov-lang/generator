import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
globalThis.window={location:{pathname:'/auto-reglue/pilot/report',search:'?maintenance=sample'}};
const {MaintenanceReportBody,normalizeMaintenanceReport}=await server.ssrLoadModule('/src/MaintenanceReport.tsx');
test('completeness audit keeps a table and distinguishes monobrands from prior exclusions',()=>{
 const report=normalizeMaintenanceReport({task_type:'showcase_inventory',inventory_monobrands:[{project:'mono.test',brand:'Brand',reason:'Монобренд'}],entries:[{site_id:'a',project:'a.test',status:'partial',inventory:{home:{public:{presence:'present',count:2,brands:['A','B']}},internal_total:0},completeness:{status:'needs_attention',cards_count:2,filled_cards:1,fields:[{key:'logo',label:'Логотип',present:1,total:2,missing_brands:['B']}],issues:['B: отсутствует логотип'],notes:['Рейтинг не выводится.']}}]});
 const html=renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report}));
 assert.match(html,/<table/);assert.match(html,/Заполнение витрины/);assert.match(html,/Основные поля: 1\/2/);assert.match(html,/Логотип: 1\/2/);assert.match(html,/B: отсутствует логотип/);assert.match(html,/Исключены монобренды · 1/);assert.match(html,/mono.test/);assert.doesNotMatch(html,/Words|В колонке «План»|Исключены сегодняшние/);
});
test('old inventory does not claim a completeness audit',()=>{
 const report=normalizeMaintenanceReport({task_type:'showcase_inventory',entries:[{site_id:'a',project:'a.test',status:'completed',inventory:{home:{public:{presence:'none'}},internal_total:0}}]});
 const html=renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report}));
 assert.match(html,/<table/);assert.doesNotMatch(html,/Заполнение витрины|Загрузка логотипов проверена/);
});
