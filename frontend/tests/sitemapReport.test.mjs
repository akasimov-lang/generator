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
