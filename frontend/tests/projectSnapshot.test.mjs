import assert from 'node:assert/strict';
import {afterEach,test} from 'node:test';
import {readProjectSnapshot,writeProjectSnapshot,removeLegacyProjectSnapshot} from '../src/projectSnapshot.ts';

afterEach(() => { delete globalThis.indexedDB; });

function storage({blocked=false, abort=false, hang=false, result} = {}) {
  let closed=0, aborted=0;
  const calls=[];
  const request={result};
  const tx={objectStore: () => ({get: key => {calls.push(['get',key]);return request;},put:(data,key) => {calls.push(['put',key,data]);return request;},delete:key=>{calls.push(['delete',key]);return request;}}),abort(){aborted++;}};
  const db={close(){closed++;},transaction(){
    if (!hang) setTimeout(() => abort ? tx.onabort() : tx.oncomplete(), 0);
    return tx;
  }};
  const opening={result:db};
  globalThis.indexedDB={open(){setTimeout(() => blocked ? opening.onblocked() : opening.onsuccess(), 0);return opening;}};
  return {opening,tx,calls,closed:()=>closed,aborted:()=>aborted};
}

test('snapshot is read only from the authenticated user key', async()=>{
  const saved={projects:[{id:'mine'}],updatedAt:'2026-11-16'};
  const state=storage({result:saved});
  assert.deepEqual(await readProjectSnapshot('webdev-projects-v2:editor'),saved);
  assert.deepEqual(state.calls,[['get','webdev-projects-v2:editor']]);
  assert.equal(state.closed(),1);
});

test('missing user snapshot returns an empty list',async()=>{
  storage();
  assert.deepEqual(await readProjectSnapshot('other-user'),{projects:[],updatedAt:null});
});

test('a blocked opening rejects and closes the database if it opens later',async()=>{
  const state=storage({blocked:true});
  await assert.rejects(readProjectSnapshot('editor'),/другой вкладкой/);
  state.opening.onsuccess();
  assert.equal(state.closed(),1);
  assert.equal(state.calls.length,0);
});

test('a browser that never completes opening cannot stall login forever',async()=>{
  globalThis.indexedDB={open:()=>({})};
  await assert.rejects(readProjectSnapshot('editor'),/не ответил вовремя/);
});

test('a stalled transaction is aborted and its connection closed',async()=>{
  const state=storage({hang:true});
  await assert.rejects(readProjectSnapshot('editor'),/не ответил вовремя/);
  assert.equal(state.aborted(),1);
  assert.equal(state.closed(),1);
});

test('transaction abort settles a read without hanging',async()=>{
  storage({abort:true});
  await assert.rejects(readProjectSnapshot('editor'),/прервана/);
});

test('write commits under its own user key',async()=>{
  const state=storage();
  const data={projects:[],updatedAt:null};
  await writeProjectSnapshot('editor',data);
  assert.deepEqual(state.calls,[['put','editor',data]]);
  assert.equal(state.closed(),1);
});

test('legacy cleanup deletes only the shared key and handles transaction abort',async()=>{
  const state=storage({abort:true});
  await assert.rejects(removeLegacyProjectSnapshot(),/прервана/);
  assert.deepEqual(state.calls,[['delete','shared-projects-v1']]);
});

test('unavailable IndexedDB rejects rather than preventing recovery',async()=>{
  await assert.rejects(readProjectSnapshot('editor'),ReferenceError);
});
