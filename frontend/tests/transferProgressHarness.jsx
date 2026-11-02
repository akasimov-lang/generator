import React from 'react';
import {createRoot} from 'react-dom/client';
import {NetworkMoveButtons} from '../src/NetworkMoveButtons';
import {MassReglueReports} from '../src/MassReglueReports';
import '../src/styles/global.css';
const filter={brand:'Fontan',geo:'PL',include_general:false,site_type:null};
const runs=[0,1].map(n=>({id:`run-${n}`,site_id:`small-${n}`,status:'queued',phase:'prepared',plan:{batch_id:'batch',source_project:`large-${n}.test`,project:`small-${n}.test`,domains:[0,1].map(i=>({domain:`domain-${n}-${i}.test`,domain_type:n===0&&i===0?'drop':'newreg'}))}}));
window.fixture={runs:[],moves:[],checks:[],queue:[],check:null};
function progress(stage){return runs.flatMap((r,n)=>{r.domain_progress=r.plan.domains.map(d=>({...d,stage,source_project:r.plan.source_project,target_project:r.plan.project}));return r.domain_progress;});}
progress('planned');
window.advanceMove=(stage)=>{
 for(const r of runs){r.status=stage==='delivered'?'completed':'waiting';r.phase=stage==='adding'?'transfer_create':'transfer_delete';}
 progress(stage);
 if(stage==='delivered'){
  runs[1].plan.domain_errors=[{domain:'domain-1-1.test',code:'DNS',message:'Webdev не смог настроить DNS.',system_response:{logs:['native detailed response']}}];
  runs[1].domain_progress[1].stage='failed';runs[1].domain_progress[1].error=runs[1].plan.domain_errors[0];
 }
};
function reports(){return [{id:'report',created_at:'2026-10-20T09:00:00Z',actor:'anton',filter,skipped:[],entries:[{run_id:'report-run',site_id:'small-0',status:window.fixture.check?.status==='completed'&&!window.fixture.failReport?'completed':'partial',source_project:'large-0.test',target_project:'small-0.test',domains:['first.test','second.test'],drop_domains:['first.test'],old_main:'small-0.test',new_main:'small-0.test',message:'Проверка переноса',domain_errors:window.fixture.failReport?[{domain:'second.test',code:'DOMAIN_NOT_ADDED',message:'Target missing',system_response:{message:'Target missing'}}]:[],verification:window.fixture.check?.status==='completed'?{checked_at:'2026-10-20T09:01:00Z',domains:[{domain:'first.test',status:'confirmed',code:'OK',message:'Добавлен'},{domain:'second.test',status:window.fixture.failReport?'failed':'confirmed',code:window.fixture.failReport?'DOMAIN_NOT_ADDED':'OK',message:window.fixture.failReport?'Target missing':'Добавлен'}]}:null}]}];}
async function api(path,options={}){
 if(path==='/auto-reglue/move-plus2'){window.fixture.moves.push(JSON.parse(options.body));window.fixture.runs=runs;return {...runs[0],runs};}
 if(path.startsWith('/auto-reglue/reports/check')){
  if(options.method==='POST'){window.fixture.checks.push(JSON.parse(options.body));window.fixture.check={id:'check',status:'running'};window.fixture.queue=[{domain:'first.test',source_project:'large-0.test',target_project:'small-0.test',status:'adding'},{domain:'second.test',source_project:'large-0.test',target_project:'small-0.test',status:'extracted'}];}
  return window.fixture.check;
 }
 if(path.startsWith('/auto-reglue/reports?'))return {reports:reports()};
 if(path.startsWith('/auto-reglue/transfer-queue'))return {limit:5,entries:window.fixture.queue};
 return {runs:window.fixture.runs};
}
createRoot(document.getElementById('root')).render(<main style={{padding:24}}><NetworkMoveButtons api={api} filter={filter} siteIds={['large-0','large-1','small-0','small-1']} onChanged={()=>{}}/><MassReglueReports api={api} filter={filter} revision="initial"/></main>);
