import {test} from 'node:test';
import assert from 'node:assert/strict';
import {redirectSaveProgress,schemeRequest,serialDraftWriter,shouldRestoreServerDraft} from '../src/redirectSaveProgress.ts';
const item=(id,status,action='domain_redirect')=>({id,status,request:{action},message:''});
test('batch progress counts its own confirmations and shows queue activity',()=>{
 const result=redirectSaveProgress([item('a','completed'),item('b','processing'),item('old','completed'),item('other','processing','reserve')],{ids:['a','b'],sent:2,total:2},false,null);
 assert.equal(result.busy,true);assert.equal(result.value,1);assert.equal(result.max,2);assert.match(result.detail,/Подтверждено: 1 из 2/);
});
test('a restored unknown queue uses indeterminate progress',()=>{const result=redirectSaveProgress([item('a','unconfirmed')],null,false,null);assert.equal(result.busy,true);assert.equal(result.value,undefined);assert.match(result.label,/статус/);});
test('failed routes are reported separately from confirmations',()=>{const result=redirectSaveProgress([item('a','completed'),item('b','failed')],{ids:['a','b'],sent:2,total:2},false,null);assert.equal(result.busy,false);assert.equal(result.failed,1);assert.match(result.label,/ошибками/);assert.match(result.detail,/Подтверждено: 1 из 2/);});
test('posting a batch shows accepted count without claiming live confirmation',()=>{const result=redirectSaveProgress([],{ids:[],sent:1,total:3},true,null);assert.equal(result.busy,true);assert.equal(result.value,1);assert.match(result.label,/Отправляем/);});
test('manual draft save blocks with indeterminate server confirmation',()=>{const result=redirectSaveProgress([],null,false,'Сохраняем черновик');assert.equal(result.busy,true);assert.equal(result.value,undefined);assert.match(result.detail,/сервера/);});
test('request deadline aborts a hung request and releases its caller',async()=>{let signal;await assert.rejects(schemeRequest(async(_,options)=>{signal=options.signal;return new Promise(()=>{});},'/draft',undefined,10),/не подтверждено/);assert.equal(signal.aborted,true);});
test('a confirmed server response is returned intact',async()=>{assert.deepEqual(await schemeRequest(async()=>({id:'draft',saved_at:'confirmed'}),'/draft',undefined,20),{id:'draft',saved_at:'confirmed'});});
test('draft writes preserve order while an earlier server save is in flight',async()=>{const calls=[];let release;const write=serialDraftWriter(async payload=>{calls.push(payload);if(payload===1)await new Promise(resolve=>release=resolve);return payload;});const first=write(1),second=write(2);await new Promise(resolve=>setImmediate(resolve));assert.deepEqual(calls,[1]);release();assert.deepEqual(await Promise.all([first,second]),[1,2]);assert.deepEqual(calls,[1,2]);});
test('a failed draft request does not stop the next server save',async()=>{const write=serialDraftWriter(async payload=>{if(payload===1)throw Error('offline');return payload;});await assert.rejects(write(1),/offline/);assert.equal(await write(2),2);});
test('a newer server draft restores across devices',()=>assert.equal(shouldRestoreServerDraft('2026-11-25T11:00:00Z','2026-11-25T10:00:00Z',false),true));
test('an older cloud draft cannot replace a newer local draft',()=>assert.equal(shouldRestoreServerDraft('2026-11-25T10:00:00Z','2026-11-25T11:00:00Z',false),false));
test('editing during server load prevents replacement of the current board',()=>assert.equal(shouldRestoreServerDraft('2026-11-25T11:00:00Z',undefined,true),false));
