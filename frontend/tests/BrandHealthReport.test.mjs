import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {healthRows}=await server.ssrLoadModule('/src/BrandHealthReport.tsx');
const {MaintenanceReportBody,normalizeMaintenanceReport}=await server.ssrLoadModule('/src/MaintenanceReport.tsx');
const row={site_id:'one',project:'example.test',brand:'Pelican',status:'completed',main_url:'https://main.test/',inner_url:'https://main.test/contacts',geo:'PL',fibery_name:'#230_Pelican_PL',fibery_url:'https://hzhz.fibery.io/favorites/Alfasearch_Config/SEO_Projects/230',health:{main:{outcome:'placeholder',chain:[{url:'https://main.test/',status:200}]},inner:{outcome:'healthy'}}};
test('audit renders exact project, Main, inner and Fibery links plus editable GSC instead of before/after tables',()=>{
  const report=normalizeMaintenanceReport({name:'Audit',task_type:'brand_health_audit',entries:[row]});
  const html=renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report,api:async()=>({value:''})}));
  assert.match(html,/href="\/project-network\/example.test\/"/);
  assert.match(html,/href="https:\/\/main.test\/"/);
  assert.match(html,/href="https:\/\/main.test\/contacts"/);
  assert.match(html,/SEO_Projects\/230/);
  assert.match(html,/Заглушка/); assert.match(html,/projectGscField/); assert.match(html,/type="text"/);
  assert.doesNotMatch(html,/В колонке «План»|maintenanceChanges|Повторить для этой группы/);
});
test('placeholder filter includes only Main placeholders, not healthy roots with broken inner pages',()=>{
  const innerProblem={...row,site_id:'two',health:{main:{outcome:'healthy'},inner:{outcome:'placeholder'}}};
  const healthy={...row,site_id:'three',brand:'Fontan',health:{main:{outcome:'healthy'},inner:{outcome:'healthy'}}};
  assert.deepEqual(healthRows([healthy,innerProblem,row],'','placeholder').map(r=>r.site_id),['one']);
  assert.deepEqual(healthRows([healthy,innerProblem,row],'','problems').map(r=>r.site_id),['one','two']);
  assert.deepEqual(healthRows([healthy,innerProblem,row]).map(r=>r.site_id),['one','two','three']);
  assert.deepEqual(healthRows([healthy,innerProblem,row],'Fontan').map(r=>r.site_id),['three']);
});
test('malicious stored links never become clickable',()=>{
  const report=normalizeMaintenanceReport({task_type:'brand_health_audit',entries:[{...row,main_url:'javascript:alert(1)',inner_url:'data:text/html,bad',fibery_url:'https://evil.test/230'}]});
  const html=renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report}));
  assert.doesNotMatch(html,/href="(?:javascript|data|https:\/\/evil)/);
});
