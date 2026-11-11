import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const previousWindow=globalThis.window;
globalThis.window={location:{origin:'https://pagepilot.test'}};
after(()=>{if(previousWindow===undefined)delete globalThis.window;else globalThis.window=previousWindow;});
const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {MaintenanceReportBody,normalizeMaintenanceReport}=await server.ssrLoadModule('/src/MaintenanceReport.tsx');
test('work report exposes separate per-text progress and escapes generated topics',()=>{
 const report=normalizeMaintenanceReport({presentation:'work_list',entries:[{site_id:'x',project:'x.test',status:'running',work_summary:{done:['Меню готово']},generations:[{id:'a',topic:'<script>bad</script>',slug:'/a/',status:'generating',percent:15,research_percent:100,ready:false},{id:'b',topic:'Ошибка',slug:'/b/',status:'generation_failed',percent:100,ready:false}]}]});
 const html=renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report}));
 assert.match(html,/Генерации текстов · готово 0 \/ 2/);
 assert.match(html,/15%/);assert.match(html,/99%/);assert.match(html,/Ошибка генерации/);
 assert.match(html,/Меню готово/);assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);
});
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
 assert.match(html,/Страниц: 2/);assert.match(html,/Витрина подтверждена: 1/);assert.match(html,/HTTP 503/);assert.match(html,/Нет внутренних страниц/);
 assert.match(html,/Не обнаружена/);assert.match(html,/Не подтверждено/);assert.match(html,/excluded.test/);
 assert.doesNotMatch(html,/Words|Подготовка проекта|Новый переклей/);
});
test('standardization report separates baseline from confirmed counts and page errors',()=>{
 const report=normalizeMaintenanceReport({task_type:'showcase_standardization',entries:[{site_id:'x',project:'x.test',status:'partial',inventory:{home:{public:{presence:'present',count:3,brands:['A','B','C']}},internal_total:0},migration:{status:'partial',before_count:3,after_count:3,added:0,removed:0,public_checks:[{slug:'/',verified:true,http:200,url:'https://x.test/'},{slug:'/review/',verified:false,http:503,url:'https://x.test/review/'}]}}]});
 const html=renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report}));
 assert.match(html,/Витрина до замены/);assert.match(html,/Было: 3 → Стало: 3/);assert.match(html,/Добавлено: 0 · Удалено: 0/);
 assert.match(html,/Проверка публикации · 1\/2/);assert.match(html,/HTTP 503/);assert.match(html,/Не подтверждено/);
});
test('planning report shows prepared status, exclusion and no execution progress',()=>{
 const report=normalizeMaintenanceReport({name:'Plan',status:'partial',planning_only:true,display_status:'План готов',can_exclude:true,entries:[{site_id:'x',project:'example.com',status:'waiting',progress:{done:1,total:6,percent:17,label:'Waiting'}}]});
 const html=renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report,onExclude:()=>{}}));
 assert.match(html,/План готов/);
 assert.match(html,/Исключить из отчёта/);
 assert.doesNotMatch(html,/maintenanceEntryProgress|maintenanceTimes/);
});
test('plan hides internal execution checklist and shows dated current observation separately',()=>{
 const report=normalizeMaintenanceReport({name:'Plan',planning_only:true,entries:[{site_id:'x',project:'example.com',status:'waiting',message:'План подготовлен. Переклей не запускался.',pending_reason:'Ожидает отдельного запуска.',notes:['Этап 1: Проверить резерв'],before:{main:'old.test'},current_observation:{values:{main:'current.test'},source:'cache',observed_at:'2026-11-06T10:00:00Z'}}]});
 const html=renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report}));
 assert.doesNotMatch(html,/Этап 1:|Ожидает отдельного запуска|План подготовлен\. Переклей/);
 assert.match(html,/Текущее состояние · кеш/);
 assert.match(html,/old.test/);
 assert.match(html,/current.test/);
});
