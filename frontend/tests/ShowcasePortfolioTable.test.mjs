import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {MaintenanceReportBody,normalizeMaintenanceReport}=await server.ssrLoadModule('/src/MaintenanceReport.tsx');
const render=entry=>renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report:normalizeMaintenanceReport({task_type:'showcase_inventory',inventory_view:'project_summary',entries:[entry]})}));
test('portfolio audit shows requested columns, Fibery name and flag beside main domain',()=>{
 const html=render({site_id:'1',project:'project.test',fibery_name:'#10_Project_PL',main:'main.test',geo:'pl-PL',status:'completed',portfolio:{domains_count:12,brands_count:5,brands:['Brand A','Brand B'],internal_pages_count:22,interlinking:{present:true,complete:false,internal_count:22,linked_from_home:10,linked_to_home:20,between_internal:8},checked_at:'2026-11-11T12:00:00Z'}});
 for(const label of ['Имя проекта','Главный домен','Доменов в сетке','Брендов на витрине','Внутренних страниц','Перелинковка','#10_Project_PL','Webdev','Готово'])assert.ok(html.includes(label),label);
 assert.match(html,/<td><span[^>]+GEO PL[^>]*>🇵🇱 <\/span><a href="https:\/\/main.test\//);
 assert.match(html,/<summary>Да<\/summary>/);assert.match(html,/Из главной: 10\/22/);assert.match(html,/Между внутренними: 8/);
 assert.doesNotMatch(html,/Бренды до замены|Витрина до замены|>Words< /);
});
test('unverified values remain unknown instead of zero or no links',()=>{
 const html=render({site_id:'1',project:'unavailable.test',status:'failed',error:'Webdev HTTP 503',portfolio:{domains_count:null,brands_count:null,internal_pages_count:null,interlinking:null}});
 assert.match(html,/Ошибка проверки/);assert.match(html,/Webdev HTTP 503/);assert.match(html,/Не проверено/);assert.equal((html.match(/<td>—<\/td>/g)||[]).length,3);assert.doesNotMatch(html,/<summary>Нет<\/summary>/);
});
test('confirmed empty inventory displays zero counts and no interlinking',()=>{
 const html=render({site_id:'1',project:'empty.test',status:'completed',portfolio:{domains_count:1,brands_count:0,internal_pages_count:0,interlinking:{present:false,complete:false,internal_count:0,linked_from_home:0,linked_to_home:0,between_internal:0}}});
 assert.equal((html.match(/<td>0<\/td>/g)||[]).length,2);assert.match(html,/<summary>Нет<\/summary>/);
});

test('system recovery report shows factual outcomes and keeps blocked rows visible',()=>{
 const html=renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report:normalizeMaintenanceReport({task_type:'system_recovery',total:1,entries:[{site_id:'1',project:'blocked.test',status:'partial',facts:[{label:'Проверка',value:'Webdev HTTP 502'},{label:'Выполнено',value:'Сохранены исходные данные'}],error:'Нужен доступ к серверу'}]})}));
 assert.match(html,/Webdev HTTP 502/);assert.match(html,/Сохранены исходные данные/);assert.match(html,/Частично/);assert.match(html,/Нужен доступ к серверу/);assert.doesNotMatch(html,/<th>До<\/th>|<th>После<\/th>/);
});
