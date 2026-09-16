import React from "react";
import { createRoot } from "react-dom/client";
import { ProjectNetworkPanel } from "../src/ProjectNetworkPanel";
window.calls=[];
window.fixture={canon:'main.test',reserve:'reserve.test',domains:['main.test','reserve.test','next.test'],revision:'revision-1',main_history:['main.test','old.test','next.test'],x_default_history:['old.test'],alternate_history:['old.test'],alternateMarkup:'<link rel="alternate" hreflang="x-default" href="https://old.test/" />',enableAlternates:true,has_head:true,alternates:[],operations:[]};
async function api(path,options={}) {
 const payload=options.body?JSON.parse(options.body):null; window.calls.push({path,payload});
 if(path.endsWith('/domain-type')) {
  window.fixture.domain_types={...window.fixture.domain_types,[payload.domain]:payload.domain_type};
  return {domain_types:window.fixture.domain_types};
 }
 if(path.endsWith('/check-domain'))return {domain:payload.domain,reachable:true,reason:''};
 if(payload) {
  if(payload.action==='create_subdomains')window.fixture.domains.push(...payload.domains);
  if(payload.action==='reserve')window.fixture.reserve=payload.domain;
  if(payload.action==='reglue')window.fixture.canon=payload.domain;
  if(payload.action==='alternates'){window.fixture.alternateMarkup=payload.alternate_markup;window.fixture.enableAlternates=payload.enable_alternates;}
  window.fixture.revision+='x';window.fixture.operations.unshift({id:payload.request_id,action:payload.action,status:'confirmed',message:'Подтверждено',domain:payload.domain,created_at:new Date().toISOString(),initiator:'test'});
 }
 return structuredClone(window.fixture);
}
function Harness(){const[mode,setMode]=React.useState('redirects');return React.createElement('main',{style:{padding:20}},React.createElement('button',{onClick:()=>setMode('network')},'Test network'),React.createElement('button',{onClick:()=>setMode('redirects')},'Test reglue'),React.createElement(ProjectNetworkPanel,{key:mode,site:{id:'test-site',name:'project.test'},username:'test',mode,api,onChanged:()=>{}}));}
createRoot(document.getElementById('root')).render(React.createElement(Harness));
