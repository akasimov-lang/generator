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

const invalidSource='chimeraprime.com/careers/regular-hubspot-developer';
const failed=(id,source=invalidSource,created_at='2026-11-17T14:00:00Z')=>({id,request:{...request(source),redirect_original_source:'',expected:{rows:[]}},status:'failed',message:'Укажите домен без пути.',created_at});

test('discard local rejected draft and older failures without another API request',async()=>{
  let calls=0;
  const queue=new NetworkEditQueue('site',async()=>{calls++;throw Object.assign(new Error('Invalid source'),{statusCode:400});});
  queue.enqueue(failed('draft').request);await tick();
  const latest=queue.items[0];latest.created_at='2026-11-17T14:00:00Z';
  queue.pending.set('older',failed('older',invalidSource,'2026-11-17T13:00:00Z'));
  queue.pending.set('other',failed('other','other.test/path'));
  assert.equal(await queue.dismiss(latest.id),true);
  assert.equal(calls,1);
  assert.equal(queue.latest(`domain:${invalidSource}`),undefined);
  assert.equal(queue.items.length,1);
  assert.equal(queue.items[0].id,'other');
});

test('discard persisted failure keeps unrelated rows and remains gone after reload',async()=>{
  let stored=[failed('old',invalidSource,'2026-11-17T13:00:00Z'),failed('latest'),failed('other','other.test/path')];
  const calls=[];
  const api=async(path,options)=>{
    calls.push([path,options?.method]);
    if(options?.method==='DELETE')stored=stored.filter(item=>item.request.redirect_source!==invalidSource);
    return snapshot(stored);
  };
  const queue=new NetworkEditQueue('site',api);await queue.refresh();
  assert.equal(await queue.dismiss('latest'),true);
  assert.deepEqual(queue.items.map(item=>item.id),['other']);
  await queue.refresh();
  assert.deepEqual(queue.items.map(item=>item.id),['other']);
  const reloaded=new NetworkEditQueue('site',api);await reloaded.refresh();
  assert.deepEqual(reloaded.items.map(item=>item.id),['other']);
  assert.deepEqual(calls.find(([,method])=>method==='DELETE'),['/sites/site/network/edit-queue/latest','DELETE']);
});

test('local failure overlay also dismisses older persisted failure',async()=>{
  const calls=[];
  const queue=new NetworkEditQueue('site',async(path,options)=>{calls.push([path,options.method]);return snapshot();});
  queue.server=snapshot([failed('server',invalidSource,'2026-11-17T13:00:00Z')]);
  queue.pending.set('local',failed('local'));
  assert.equal(await queue.dismiss('local'),true);
  assert.deepEqual(calls,[['/sites/site/network/edit-queue/server','DELETE']]);
  assert.deepEqual(queue.items,[]);
});

test('failed discard leaves row and diagnostic visible',async()=>{
  const queue=new NetworkEditQueue('site',async()=>{throw new Error('Server unavailable');});
  queue.server=snapshot([failed('server')]);
  await assert.rejects(queue.dismiss('server'),/Server unavailable/);
  assert.equal(queue.latest(`domain:${invalidSource}`).id,'server');
  assert.equal(queue.error,'Server unavailable');
});

test('active request cannot be discarded',async()=>{
  let calls=0;
  const queue=new NetworkEditQueue('site',async()=>{calls++;return snapshot();});
  queue.server=snapshot([{...failed('active'),status:'processing'}]);
  assert.equal(await queue.dismiss('active'),false);
  assert.equal(calls,0);
  assert.equal(queue.items.length,1);
});

test('ambiguous submission cannot be discarded',async()=>{
  let calls=0;
  const queue=new NetworkEditQueue('site',async()=>{calls++;return snapshot();});
  queue.pending.set('ambiguous',{...failed('ambiguous'),status:'unconfirmed'});
  assert.equal(await queue.dismiss('ambiguous'),false);
  assert.equal(calls,0);
  assert.equal(queue.items.length,1);
});

test('refresh started before discard cannot restore failed row',async()=>{
  let release;
  const stale=snapshot([failed('server')]);
  const queue=new NetworkEditQueue('site',async(path,options)=>options?.method==='DELETE'?snapshot():new Promise(resolve=>release=()=>resolve(stale)));
  queue.server=stale;
  const reading=queue.refresh();
  assert.equal(await queue.dismiss('server'),true);
  release();await reading;
  assert.deepEqual(queue.items,[]);
});

test('late unrelated enqueue snapshot cannot resurrect discarded failure',async()=>{
  let release;
  const queue=new NetworkEditQueue('site',async(path,options)=>{
    if(options.method==='DELETE')return snapshot();
    const body=JSON.parse(options.body);
    return new Promise(resolve=>release=()=>resolve(snapshot([failed('server'),{id:body.request_id,request:body,status:'queued',message:'queued'}])));
  });
  queue.server=snapshot([failed('server')]);
  queue.enqueue(request('other.test'));
  assert.equal(await queue.dismiss('server'),true);
  release();await tick();
  assert.equal(queue.latest(`domain:${invalidSource}`),undefined);
  assert.equal(queue.latest('domain:other.test').status,'queued');
});

test('discard response cannot replace network after concurrent edit',async()=>{
  let release;
  const queue=new NetworkEditQueue('site',async(path,options)=>{
    if(options.method==='DELETE')return new Promise(resolve=>release=()=>resolve({...snapshot(),network:{revision:'stale'}}));
    return new Promise(()=>{});
  });
  queue.server=snapshot([failed('server')]);
  const deleting=queue.dismiss('server');
  queue.enqueue(request('other.test'));
  release();await deleting;
  assert.equal(queue.server.network,null);
  assert.equal(queue.latest('domain:other.test').status,'submitting');
});

test('hung edit submission times out and refresh confirms it without replay',async()=>{
 let accepted;let posts=0;
 const queue=new NetworkEditQueue('site',async(path,options)=>{
  if(options?.method==='POST') {posts++;const body=JSON.parse(options.body);accepted={id:body.request_id,request:body,status:'completed',message:'Сохранено'};return new Promise(()=>{});}
  return snapshot([accepted]);
 },10);
 queue.enqueue(request('existing.test'));
 await new Promise(resolve=>setTimeout(resolve,30));
 assert.equal(queue.latest('domain:existing.test').status,'unconfirmed');
 await queue.refresh();
 assert.equal(queue.latest('domain:existing.test').status,'completed');assert.equal(posts,1);
});

test('hung queue read releases refresh lock so next poll can recover',async()=>{
 let calls=0;
 const queue=new NetworkEditQueue('site',async()=>++calls===1?new Promise(()=>{}):snapshot(),10);
 const read=queue.refresh();
 await new Promise(resolve=>setTimeout(resolve,30));await read;
 assert.match(queue.error,/не ответил/);
 await queue.refresh();assert.equal(calls,2);assert.equal(queue.error,'');
});
