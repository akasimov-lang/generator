import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {MaintenanceReportBody,normalizeMaintenanceReport}=await server.ssrLoadModule('/src/MaintenanceReport.tsx');
test('image audit is a table with requested metadata, counts and precise status',()=>{
 const report=normalizeMaintenanceReport({task_type:'article_image_localization',entries:[{site_id:'a',project:'site.test',main:'main.test',fibery_name:'Fibery name',brand:'Brand',geo:'pl-PL',status:'completed',image_localization:{pages_count:7,images_count:6,fixed_links:5}},{site_id:'b',project:'failed.test',status:'partial',image_localization:{issues:['Page HTTP 404']}}]});
 const html=renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report}));
 assert.match(html,/<table/);assert.match(html,/webdev-alfasearch.ru\/projects\/site.test/);assert.match(html,/Fibery name/);assert.match(html,/🇵🇱/);assert.match(html,/Brand/);assert.match(html,/Готово/);assert.match(html,/Ошибка/);assert.match(html,/Page HTTP 404/);assert.doesNotMatch(html,/Words|Подготовка проекта|Новый переклей/);
});
test('small work list renders actual actions as bullets and keeps plan separate',()=>{
 const report=normalizeMaintenanceReport({presentation:'work_list',entries:[{site_id:'a',project:'site.test',status:'completed',work_summary:{done:['Добавлено меню'],checks:['Проверен телефон'],issues:[],plan:['Создать меню']}}]});
 const html=renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report}));
 assert.match(html,/<ul><li>Добавлено меню/);assert.match(html,/Исходный план/);assert.doesNotMatch(html,/<table|Words|После|этапов/);
});
