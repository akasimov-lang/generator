import React from "react";
import { createRoot } from "react-dom/client";
import { ProjectNetworkPanel } from "../src/ProjectNetworkPanel";
window.calls=[];
window.fixture={canon:'main.test',reserve:'reserve.test',domains:['main.test','reserve.test','next.test','unused.reserve.test','mobile.test'],revision:'revision-1',main_history:['main.test','old.test','next.test'],x_default_history:['old.test'],alternate_history:['old.test'],alternateMarkup:'<link rel="alternate" hreflang="x-default" href="https://old.test/" />',enableAlternates:true,has_head:true,alternates:[],operations:[]};
window.fixture.amp='mobile.test'; window.fixture.amp_domains=['mobile.test'];
window.fixture.domain_classification={'unused.reserve.test':{is_subdomain:true,parent_domain:'reserve.test',parent_type:null,unused_as_main:true}};
async function api(path,options={}) {
 const payload=options.body?JSON.parse(options.body):null; window.calls.push({path,payload});
 if(path.endsWith('/domain-type')) {
  window.fixture.domain_types={...window.fixture.domain_types,[payload.domain]:payload.domain_type};
  for (const info of Object.values(window.fixture.domain_classification)) info.parent_type=window.fixture.domain_types[info.parent_domain] || null;
  return {domain_types:window.fixture.domain_types,domain_classification:window.fixture.domain_classification};
 }
 if(path.endsWith('/operations') && !payload)return structuredClone(window.fixture.operations);
 if(path.endsWith('/check-domain'))return {domain:payload.domain,reachable:true,reason:''};
 if(payload) {
  const sourceDomain = window.fixture.canon;
  const alternatesBefore = {markup:window.fixture.alternateMarkup,enabled:window.fixture.enableAlternates};
  if(payload.action==='select_fake_main'){window.fixture.fake_main_current=payload.fake_main_path;}
  if(payload.action==='create_fake_main'){window.fixture.fake_main_paths=['/cz/','/'+payload.fake_main_path.replace(/^\/+|\/+$/g,'')+'/'];window.fixture.fake_main_enabled=true;}
  if(payload.action==='delete_domain')window.fixture.domains=window.fixture.domains.filter(d=>d!==payload.domain);
  if(payload.action==='create_subdomains')window.fixture.domains.push(...payload.domains);
  if(payload.action==='reserve')window.fixture.reserve=payload.domain;
  if(payload.action==='reglue'){window.fixture.canon=payload.domain;window.fixture.operations.unshift({id:'index-task',action:'indexing',status:'index_submitted',task_id:'task-123',domains:['https://main.test/','https://next.test/'],message:'Задача создана',created_at:new Date().toISOString(),initiator:'test'});}
  if(payload.action==='alternates'){window.fixture.alternateMarkup=payload.alternate_markup;window.fixture.enableAlternates=payload.enable_alternates;}
  window.fixture.revision+='x';window.fixture.operations.unshift({id:payload.request_id,action:payload.action,source_domain:payload.action==='reglue'?sourceDomain:null,alternates_before:payload.action==='alternates'?alternatesBefore:null,alternates_after:payload.action==='alternates'?{markup:payload.alternate_markup,enabled:payload.enable_alternates}:null,status:'confirmed',message:'Подтверждено',domain:payload.domain,created_at:new Date().toISOString(),initiator:'test'});
 }
 return structuredClone(window.fixture);
}
function Harness(){const[mode,setMode]=React.useState('redirects');return React.createElement('main',{style:{padding:20}},React.createElement('button',{onClick:()=>setMode('network')},'Test network'),React.createElement('button',{onClick:()=>setMode('redirects')},'Test reglue'),React.createElement(ProjectNetworkPanel,{key:mode,site:{id:'test-site',name:'project.test'},username:'test',mode,api,onChanged:()=>{}}));}
createRoot(document.getElementById('root')).render(React.createElement(Harness));
