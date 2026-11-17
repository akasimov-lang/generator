import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';

const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {MassReglueParticipationControl,saveReglueParticipation}=await server.ssrLoadModule('/src/ProjectNetworkPanel.tsx');
const defaults={enabled:true,saving:false,saved:false,error:'',onChange:()=>{}};
const render=props=>renderToStaticMarkup(React.createElement(MassReglueParticipationControl,{...defaults,...props}));
const input=props=>MassReglueParticipationControl({...defaults,...props}).props.children[0].props.children[0];

test('project excluded from mass reglue has checked exclusion checkbox',()=>{
 const html=render({enabled:false});
 assert.match(html,/Не участвует в массовом переклее/);
 assert.match(html,/<input[^>]*type="checkbox"[^>]*checked=""/);
});

test('participating project has unchecked exclusion checkbox',()=>{
 assert.doesNotMatch(render({enabled:true}),/<input[^>]*checked=/);
});

test('checking exclusion requests enabled false',()=>{
 let requested;
 input({onChange:value=>{requested=value;}}).props.onChange({currentTarget:{checked:true}});
 assert.equal(requested,false);
});

test('unchecking exclusion requests enabled true',()=>{
 let requested;
 input({enabled:false,onChange:value=>{requested=value;}}).props.onChange({currentTarget:{checked:false}});
 assert.equal(requested,true);
});

test('saving exclusion uses existing participation endpoint and confirmed false response',async()=>{
 const calls=[];
 const api=async(path,options)=>{calls.push({path,method:options.method,body:JSON.parse(options.body)});return{id:'project-id',reglue_participation:false};};
 assert.equal(await saveReglueParticipation(api,'project-id',false),false);
 assert.deepEqual(calls,[{path:'/auto-reglue/projects/project-id/participation',method:'PATCH',body:{enabled:false}}]);
});

test('restoring participation saves enabled true',async()=>{
 const api=async(path,options)=>{
  assert.equal(path,'/auto-reglue/projects/project-id/participation');
  assert.equal(options.method,'PATCH');
  assert.deepEqual(JSON.parse(options.body),{enabled:true});
  return{id:'project-id',reglue_participation:true};
 };
 assert.equal(await saveReglueParticipation(api,'project-id',true),true);
});

test('failed request is propagated and does not report success',async()=>{
 await assert.rejects(saveReglueParticipation(async()=>{throw new Error('Нет соединения');},'project-id',false),/Нет соединения/);
});

test('mismatched persisted value is not treated as successful save',async()=>{
 await assert.rejects(saveReglueParticipation(async()=>({id:'project-id',reglue_participation:true}),'project-id',false),/Сервер не подтвердил/);
});

test('response for a different project is not accepted',async()=>{
 await assert.rejects(saveReglueParticipation(async()=>({id:'other-project',reglue_participation:false}),'project-id',false),/Сервер не подтвердил/);
});

test('checkbox is disabled while save is in progress and progress is announced',()=>{
 const html=render({saving:true});
 assert.match(html,/<input[^>]*disabled=""/);
 assert.match(html,/aria-busy="true"/);
 assert.match(html,/Участие в массовом переклее: Сохраняем/);
});

test('save error is visible beside the unchanged confirmed value',()=>{
 const html=render({enabled:true,error:'Нет соединения'});
 assert.doesNotMatch(html,/<input[^>]*checked=/);
 assert.match(html,/Нет соединения/);
 assert.doesNotMatch(html,/<input[^>]*disabled=/);
});
