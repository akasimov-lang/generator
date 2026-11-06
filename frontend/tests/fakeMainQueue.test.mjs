import assert from 'node:assert/strict';
import {test} from 'node:test';
import {FakeMainQueue} from '../src/fakeMainQueue.ts';
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const snapshot=(items=[])=>({items,limit:10,active_count:items.length,network:null});
const queued=(id,path,action='delete')=>({id,path,action,status:'queued',message:'В очереди',operation_ids:[id]});

test('ten rapid clicks are accepted without waiting for remote deletion; eleventh is refused',async()=>{
 let unblock;const calls=[],items=[];
 const queue=new FakeMainQueue('site',async(path,options)=>{
  const body=JSON.parse(options.body);calls.push(body);
  if(calls.length===1)await new Promise(resolve=>{unblock=resolve;});
  items.push(queued(body.request_id,body.path));return snapshot([...items]);
 });
 for(let i=0;i<10;i++)assert.equal(queue.enqueue('delete',`/path-${i}/`),true);
 assert.equal(queue.count,10);assert.equal(queue.enqueue('delete','/eleven/'),false);
 assert.equal(calls.length,1);unblock();await settle();
 assert.equal(calls.length,10);assert.equal(queue.count,10);
 assert.equal(queue.enqueue('delete','/path-0/'),false);
});

test('create first click enqueues even while a deletion is waiting for Webdev',async()=>{
 const items=[queued('old','/old/')],calls=[];
 const queue=new FakeMainQueue('site',async(path,options)=>{
  if(!options)return snapshot(items);
  const body=JSON.parse(options.body);calls.push(body);items.push(queued(body.request_id,body.path,body.action));return snapshot(items);
 });
 await queue.refresh();assert.equal(queue.enqueue('create','resources'),true);await settle();
 assert.equal(calls.length,1);assert.equal(calls[0].action,'create');assert.equal(calls[0].path,'/resources');
 assert.equal(queue.busyPath('/resources'),true);
});

test('lost enqueue response is reconciled by polling without sending a second operation',async()=>{
 const items=[];let posts=0;
 const queue=new FakeMainQueue('site',async(path,options)=>{
  if(!options)return snapshot(items);
  posts++;const body=JSON.parse(options.body);items.push(queued(body.request_id,body.path));throw Error('timeout');
 });
 queue.enqueue('delete','/old/');await settle();assert.equal(queue.items[0].status,'unconfirmed');
 await queue.refresh();assert.equal(queue.items[0].status,'queued');assert.equal(posts,1);assert.equal(queue.count,1);
});

test('retry preserves request id after uncertain enqueue and cannot duplicate queued work',async()=>{
 const calls=[];
 const queue=new FakeMainQueue('site',async(path,options)=>{
  const body=JSON.parse(options.body);calls.push(body);if(calls.length===1)throw Error('timeout');
  return snapshot([queued(body.request_id,body.path)]);
 });
 queue.enqueue('delete','/old/');await settle();queue.retry(queue.items[0].id);await settle();
 assert.equal(calls.length,2);assert.equal(calls[0].request_id,calls[1].request_id);
 assert.equal(queue.count,1);
});

test('stale polling response cannot discard a just-enqueued path',async()=>{
 let resolveRead;
 const queue=new FakeMainQueue('site',async(path,options)=>{
  if(!options)return new Promise(resolve=>{resolveRead=resolve;});
  const body=JSON.parse(options.body);return snapshot([queued(body.request_id,body.path)]);
 });
 const reading=queue.refresh();queue.enqueue('delete','/old/');await settle();resolveRead(snapshot());await reading;
 assert.equal(queue.busyPath('/old/'),true);assert.equal(queue.count,1);
});

test('other field loading does not block enqueue and its stale network snapshot is discarded',async()=>{
 let unblock;let posts=0;
 const queue=new FakeMainQueue('site',async(path,options)=>{
  if(!options)return snapshot();
  posts++;const body=JSON.parse(options.body);await new Promise(resolve=>{unblock=resolve;});
  return {...snapshot([queued(body.request_id,body.path,'create')]),network:{revision:'stale'}};
 });
 queue.setNetworkBusy(true);
 assert.equal(queue.enqueue('create','resources'),true);assert.equal(posts,1);
 unblock();await settle();assert.equal(queue.server.network,null);assert.equal(queue.count,1);
});


test('enqueue response arriving after another field finished saving cannot restore stale network data',async()=>{
 let unblock;
 const queue=new FakeMainQueue('site',async(path,options)=>{
  const body=JSON.parse(options.body);await new Promise(resolve=>{unblock=resolve;});
  return {...snapshot([queued(body.request_id,body.path)]),network:{revision:'stale'}};
 });
 queue.enqueue('delete','old');
 queue.setNetworkBusy(true);queue.setNetworkBusy(false);
 unblock();await settle();
 assert.equal(queue.server.network,null);assert.equal(queue.count,1);
});

test('creation queue preserves a path without a trailing slash',async()=>{
 const calls=[];
 const queue=new FakeMainQueue('site',async(path,options)=>{const body=JSON.parse(options.body);calls.push(body);return snapshot([queued(body.request_id,body.path,'create')]);});
 assert.equal(queue.enqueue('create',' /index.php '),true);
 await settle();
 assert.equal(calls[0].path,'/index.php');
 assert.equal(queue.items[0].path,'/index.php');
});

test('uncertain submission can be cancelled without repeating creation',async()=>{
 const calls=[];
 const queue=new FakeMainQueue('site',async(path,options)=>{
  calls.push(path);const body=JSON.parse(options.body);
  if(!path.endsWith('/cancel'))throw Error('timeout');
  return snapshot([{...queued(body.request_id,body.path,'create'),status:'cancelled',message:'Отправка удалена.'}]);
 });
 queue.enqueue('create','/new/');await settle();const id=queue.items[0].id;
 await queue.cancel(id);queue.retry(id);
 assert.equal(queue.count,0);assert.equal(queue.items[0].status,'cancelled');assert.equal(calls.length,2);
});

test('late enqueue response cannot resurrect a confirmed cancellation',async()=>{
 let reply;
 const queue=new FakeMainQueue('site',async(path,options)=>{
  const body=JSON.parse(options.body),item=queued(body.request_id,body.path,'create');
  if(path.endsWith('/cancel'))return snapshot([{...item,status:'cancelled'}]);
  return new Promise(resolve=>{reply=()=>resolve(snapshot([item]));});
 });
 queue.enqueue('create','/late/');const id=queue.items[0].id;
 await queue.cancel(id);reply();await settle();
 assert.equal(queue.items[0].status,'cancelled');assert.equal(queue.count,0);
});

test('existing fake page selection uses durable queue',async()=>{
 let action;
 const queue=new FakeMainQueue('site',async(path,options)=>{
  const body=JSON.parse(options.body);action=body.action;
  return snapshot([queued(body.request_id,body.path,body.action)]);
 });
 queue.enqueue('select','/existing/');await settle();assert.equal(action,'select');
});
