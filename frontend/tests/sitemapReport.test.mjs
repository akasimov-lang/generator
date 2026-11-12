import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {sitemapRows}=await server.ssrLoadModule('/src/SitemapReport.tsx');
const {MaintenanceReportBody,normalizeMaintenanceReport}=await server.ssrLoadModule('/src/MaintenanceReport.tsx');
const row={site_id:'one',project:'example.test',main:'main.test',status:'completed',geo:'PL',sitemap:{before:{count:1},after:{count:3,valid:true,status:200},internal_pages:2,expected_count:3,action:'updated',sitemap_url:'https://main.test/sitemap.xml'}};
test('sitemap report displays exact links, actual page counts and confirmed outcomes',()=>{
 const html=renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report:normalizeMaintenanceReport({task_type:'sitemap_repair',entries:[row]})}));
 assert.match(html,/href="https:\/\/main.test\/sitemap.xml"/);assert.match(html,/Обновлён и проверен/);assert.match(html,/1 → 3 \/ 3/);assert.match(html,/🇵🇱/);assert.doesNotMatch(html,/maintenanceChanges|Words|Повторить для этой группы/);
});
test('problems appear first and filters preserve input data',()=>{
 const failed={...row,site_id:'two',status:'failed',project:'zzz.test'};
 const input=[row,failed];assert.deepEqual(sitemapRows(input).map(r=>r.site_id),['two','one']);assert.equal(input[0],row);assert.deepEqual(sitemapRows(input,'errors'),[failed]);
});
test('untrusted URL values are not rendered as links',()=>{
 const report=normalizeMaintenanceReport({task_type:'sitemap_repair',entries:[{...row,fibery_url:'https://evil.test/task',sitemap:{...row.sitemap,sitemap_url:'javascript:bad()'}}]});
 const html=renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report}));assert.doesNotMatch(html,/href="(?:javascript|https:\/\/evil)/);
});
test('refresh controls only appear for problem rows, running rows stay visible and disabled',()=>{
 const report=normalizeMaintenanceReport({id:'report',task_type:'sitemap_repair',entries:[row,{...row,site_id:'two',status:'partial'},{...row,site_id:'three',status:'running',recheck:{id:'job'}}]});
 const html=renderToStaticMarkup(React.createElement(MaintenanceReportBody,{report,api:async()=>({})}));
 assert.equal((html.match(/class="sitemapRecheck"/g)||[]).length,2);
 assert.match(html,/disabled="" aria-label="Обновить sitemap/);
 assert.equal(sitemapRows(report.sitemaps.entries,'errors').length,2);
});
test('recheck sends only the selected row and reuses request ID after an ambiguous response',async()=>{
 const {createSitemapRecheck}=await server.ssrLoadModule('/src/SitemapReport.tsx');
 const calls=[];let attempt=0;
 const submit=createSitemapRecheck(async(path,options)=>{calls.push({path,...JSON.parse(options.body)});if(!attempt++)throw Error('lost');return {id:'report'};},'report',()=> 'fixed-id');
 await assert.rejects(submit('two'),/lost/);
 assert.deepEqual(await submit('two'),{id:'report'});
 assert.deepEqual(calls,[{path:'/auto-reglue/maintenance-reports/report/projects/two/sitemap-recheck',request_id:'fixed-id'},{path:'/auto-reglue/maintenance-reports/report/projects/two/sitemap-recheck',request_id:'fixed-id'}]);
});
test('fast double click is deduplicated while another row can run independently',async()=>{
 const {createSitemapRecheck}=await server.ssrLoadModule('/src/SitemapReport.tsx');
 let resolve;const calls=[];
 const submit=createSitemapRecheck(async(path)=>{calls.push(path);return new Promise(r=>{resolve=r;});},'report',()=> 'request');
 const first=submit('one');assert.equal(await submit('one'),undefined);const finishFirst=resolve;
 const second=submit('two');assert.equal(calls.length,2);resolve({id:'two'});finishFirst({id:'one'});
 await Promise.all([first,second]);
});
