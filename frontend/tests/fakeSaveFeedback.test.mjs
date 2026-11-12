import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import {createServer} from 'vite';

const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {fakeSaveFeedback}=await server.ssrLoadModule('/src/fakeSaveFeedback.ts');

const failed={id:'attempt',action:'create',path:'/aaz/',status:'failed',message:'Health-check old.test: ENOTFOUND',operation_ids:[],created_at:'2026-11-12T12:37:00Z',finished_at:'2026-11-12T12:37:10Z'};
const snapshot={fake_main_enabled:true,fake_main_current:'/aaz/',fake_main_paths:['/aaz/'],operations:[]};
const corrected={...snapshot,operations:[{action:'alternates',status:'confirmed',created_at:'2026-11-12T12:40:00Z'}]};

test('shows original failure even if part of the settings was written',()=>{
 assert.equal(fakeSaveFeedback([failed],snapshot).state,'error');
 assert.equal(fakeSaveFeedback([failed],snapshot).error,failed.message);
});
test('manual correction confirmed later clears current warning without rewriting history',()=>{
 assert.equal(fakeSaveFeedback([failed],corrected).state,'idle');
 assert.equal(failed.status,'failed');
});
test('a different selected path does not resolve the requested change',()=>{
 assert.equal(fakeSaveFeedback([failed],{...corrected,fake_main_current:'/old/'}).state,'error');
});
test('an unrelated later operation cannot clear a failed fake-page edit',()=>{
 assert.equal(fakeSaveFeedback([failed],{...snapshot,operations:[{action:'reserve',status:'confirmed',created_at:'2026-11-12T12:40:00Z'}]}).state,'error');
});
test('new active edit supersedes a historical failure and then confirms success',()=>{
 const current={...failed,id:'new',status:'processing',created_at:'2026-11-12T12:41:00Z'};
 assert.equal(fakeSaveFeedback([failed,current],snapshot).state,'saving');
 assert.equal(fakeSaveFeedback([failed,{...current,status:'completed'}],snapshot).state,'saved');
});
