import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {MaintenanceReportBody,normalizeMaintenanceReport}=await server.ssrLoadModule('/src/MaintenanceReport.tsx');
const {ShowcasePortfolioTable,portfolioGeoCounts,portfolioRows}=await server.ssrLoadModule('/src/ShowcasePortfolioTable.tsx');
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

const row=(project,geo,portfolio={},fibery_name='')=>({site_id:project,project,geo,fibery_name,status:'completed',portfolio});
test('GEO counts combine normalized countries and keep unknown GEO visible last',()=>{
 const entries=[row('polish.test','pl-PL'),row('czech.test','cs_CZ'),row('czech2.test','CS'),row('british.test','UK'),row('unknown.test','ZZ')];
 assert.deepEqual(portfolioGeoCounts(entries),[{geo:'CZ',count:2},{geo:'GB',count:1},{geo:'PL',count:1},{geo:'',count:1}]);
 assert.equal(portfolioGeoCounts(entries).reduce((sum,item)=>sum+item.count,0),entries.length);
});
test('default order groups countries; filtering leaves original entries unchanged',()=>{
 const entries=Object.freeze([row('z.test','PL'),row('unknown.test','ZZ'),row('czech.test','CZ'),row('a.test','PL')]);
 assert.deepEqual(portfolioRows(entries).map(item=>item.project),['czech.test','a.test','z.test','unknown.test']);
 assert.deepEqual(portfolioRows(entries,'PL').map(item=>item.project),['a.test','z.test']);
 assert.deepEqual(portfolioRows(entries,'').map(item=>item.project),['unknown.test']);
 assert.deepEqual(portfolioRows(entries,'FR'),[]);
 assert.deepEqual(entries.map(item=>item.project),['z.test','unknown.test','czech.test','a.test']);
});
test('count columns sort numerically and keep unchecked values last in both directions',()=>{
 const entries=[row('ten.test','CZ',{brands_count:10}),row('unchecked.test','PL'),row('two.test','PL',{brands_count:2}),row('zero.test','CZ',{brands_count:0})];
 assert.deepEqual(portfolioRows(entries,null,{key:'brands',direction:'asc'}).map(item=>item.project),['zero.test','two.test','ten.test','unchecked.test']);
 assert.deepEqual(portfolioRows(entries,null,{key:'brands',direction:'desc'}).map(item=>item.project),['ten.test','two.test','zero.test','unchecked.test']);
 assert.deepEqual(portfolioRows(entries,'PL',{key:'brands',direction:'desc'}).map(item=>item.project),['two.test','unchecked.test']);
});
test('interlinking sort distinguishes unknown from confirmed absence',()=>{
 const entries=[row('unknown.test','CZ'),row('yes.test','CZ',{interlinking:{present:true}}),row('no.test','CZ',{interlinking:{present:false}})];
 assert.deepEqual(portfolioRows(entries,null,{key:'links',direction:'asc'}).map(item=>item.project),['no.test','yes.test','unknown.test']);
 assert.deepEqual(portfolioRows(entries,null,{key:'links',direction:'desc'}).map(item=>item.project),['yes.test','no.test','unknown.test']);
});
test('project column sorts by visible project name and main column ignores protocol',()=>{
 const entries=[row('z.test','CZ',{},'A Fibery'),row('a.test','CZ',{},'Z Fibery')].map((item,i)=>({...item,main:i?'https://b.test/':'a.test'}));
 assert.deepEqual(portfolioRows(entries,null,{key:'project',direction:'asc'}).map(item=>item.project),['a.test','z.test']);
 assert.deepEqual(portfolioRows(entries,null,{key:'main',direction:'asc'}).map(item=>item.project),['z.test','a.test']);
});
test('initial report renders country tiles with counts, GEO groups and sortable headers',()=>{
 const html=renderToStaticMarkup(React.createElement(ShowcasePortfolioTable,{entries:[row('polish.test','PL'),row('czech.test','CZ'),row('czech2.test','cs-CZ')]}));
 assert.match(html,/<span>Все GEO<\/span><span class="showcaseGeoCount">3<\/span>/);
 assert.match(html,/aria-label="Чехия \(CZ\): 2 проектов"/);
 assert.match(html,/aria-label="Польша \(PL\): 1 проектов"/);
 assert.equal((html.match(/scope="rowgroup"/g)||[]).length,2);
 assert.equal((html.match(/class="showcaseColumnSort"/g)||[]).length,7);
 assert.ok(html.indexOf('data-project="czech2.test"')<html.indexOf('data-project="polish.test"'));
 assert.match(html,/Показано 3 из 3 проектов/);
});
