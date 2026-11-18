import assert from 'node:assert/strict';
import {test} from 'node:test';
import {projectHistoryChanged,subscribeProjectHistory} from '../src/projectHistoryEvents.ts';

test('history updates are scoped to the project, superseded requests and unmounted subscribers cannot replace it',async()=>{
 const previous=globalThis.window;
 globalThis.window=new EventTarget();
 const requests=[],received=[];
 const unsubscribe=subscribeProjectHistory('current', (path,options)=>new Promise(resolve=>requests.push({path,options,resolve})),value=>received.push(value));
 try {
  projectHistoryChanged('other');assert.equal(requests.length,0);
  projectHistoryChanged('current');projectHistoryChanged('current');
  assert.equal(requests.length,2);assert.equal(requests[0].options.signal.aborted,true);
  assert.equal(requests[1].path,'/sites/current/network/history');assert.equal(requests[1].options.cache,'no-store');
  requests[1].resolve({operations:['new']});requests[0].resolve({operations:['old']});
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(received,[{operations:['new']}]);
  projectHistoryChanged('current');unsubscribe();
  assert.equal(requests[2].options.signal.aborted,true);
  requests[2].resolve({operations:['late']});projectHistoryChanged('current');
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(requests.length,3);assert.equal(received.length,1);
 } finally {unsubscribe();globalThis.window=previous;}
});
