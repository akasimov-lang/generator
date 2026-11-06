import assert from 'node:assert/strict';
import test from 'node:test';
import { NetworkEditQueue, editKey } from '../src/networkEditQueue.ts';
const tick = () => new Promise(resolve => setImmediate(resolve));
const request = source => ({action:'domain_redirect', revision:'cached', redirect_source:source, redirect_original_source:source, redirect_target:'new.test', expected:{rows:[{url:source,value:'old.test'}]}});
const snapshot = (items=[]) => ({items,limit:30,network:null});

test('two fields can be submitted immediately while first enqueue is in flight', async()=>{
  let release; const calls=[];
  const queue=new NetworkEditQueue('site',async(path,options)=>{
    calls.push(JSON.parse(options.body));
    if(calls.length===1)await new Promise(resolve=>release=resolve);
    return snapshot(calls.map(r=>({id:r.request_id,request:r,status:'queued',message:'queued'})));
  });
  assert.equal(queue.enqueue(request('one.test')),true);
  assert.equal(queue.enqueue(request('two.test')),true);
  assert.equal(queue.count,2); assert.equal(calls.length,1);
  assert.equal(queue.busy('domain:one.test'),true);
  assert.equal(queue.busy('domain:three.test'),false);
  release(); await tick();
  assert.equal(calls.length,2);
  assert.deepEqual(calls.map(r=>r.redirect_source),['one.test','two.test']);
});

test('duplicate click is ignored and the submitted snapshot is immutable', async()=>{
  const queue=new NetworkEditQueue('site',async()=>new Promise(()=>{}));
  const draft=request('one.test'); queue.enqueue(draft); draft.redirect_target='changed.test';
  assert.equal(queue.enqueue(request('one.test')),false);
  assert.equal(queue.items[0].request.redirect_target,'new.test');
});

test('ambiguous enqueue pauses later submissions until same receipt is checked',async()=>{
  const calls=[];
  const queue=new NetworkEditQueue('site',async(path,options)=>{
    const body=JSON.parse(options.body); calls.push(body);
    if(calls.length===1)throw new Error('lost connection');
    return snapshot([{id:body.request_id,request:body,status:'queued',message:'queued'}]);
  });
  queue.enqueue(request('one.test')); queue.enqueue(request('two.test')); await tick();
  assert.equal(calls.length,1);
  const first=queue.items.find(i=>i.status==='unconfirmed'); queue.retry(first.id); await tick();
  assert.equal(calls.length,3); assert.equal(calls[0].request_id,calls[1].request_id);
});

test('server rejection leaves its error visible and permits independent edits',async()=>{
  const queue=new NetworkEditQueue('site',async()=>{throw Object.assign(new Error('Invalid target'),{statusCode:400});});
  queue.enqueue(request('one.test')); await tick();
  assert.equal(queue.latest('domain:one.test').status,'failed');
  assert.equal(queue.busy('domain:one.test'),false);
  assert.equal(queue.latest('domain:one.test').request.redirect_target,'new.test');
  assert.equal(queue.enqueue(request('two.test')),true); await tick();
});

test('reload restores server queue and completion unlocks only completed row',async()=>{
  let items=[{id:'one',request:request('one.test'),status:'queued',message:'queued'}];
  const queue=new NetworkEditQueue('site',async()=>snapshot(items));
  await queue.refresh(); assert.equal(queue.busy('domain:one.test'),true);
  items=items.map(i=>({...i,status:'completed',message:'Saved'}));
  await queue.refresh(); assert.equal(queue.busy('domain:one.test'),false);
  assert.equal(queue.latest('domain:one.test').message,'Saved');
});

test('page redirect keys separate matching paths on different domains',()=>{
  assert.notEqual(editKey({action:'page_redirect',page_redirect_domain:'one.test',page_redirect_source:'/old/'}),editKey({action:'page_redirect',page_redirect_domain:'two.test',page_redirect_source:'/old/'}));
});
