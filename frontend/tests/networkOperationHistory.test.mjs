import assert from 'node:assert/strict';
import {test} from 'node:test';
import {networkOperationHistory} from '../src/networkOperationHistory.ts';
const op=(id,status,date)=>({id,status,created_at:date});
const item=(id,status,date)=>({...op(id,status,date),path:'/new/',action:'create',message:'test',operation_ids:[id,id+'-head']});
test('local submission appears before a server receipt exists',()=>{
 const rows=networkOperationHistory([], [item('new','submitting','2026-11-05')]);
 assert.equal(rows[0].kind,'queue');assert.equal(rows[0].item.path,'/new/');
});
test('active jobs and operations precede newer completed history',()=>{
 const rows=networkOperationHistory([op('done','confirmed','2026-11-06'),op('old','pending','2026-11-01')],[item('queued','queued','2026-11-05')]);
 assert.deepEqual(rows.map(r=>r.item.id),['queued','old','done']);
});
test('queue receipts are not duplicated and completed queue rows stay in history',()=>{
 const rows=networkOperationHistory([op('job','confirmed','2026-11-05'),op('job-head','confirmed','2026-11-05')],[item('job','completed','2026-11-05')]);
 assert.equal(rows.length,1);assert.equal(rows[0].item.status,'completed');
});
test('failed operations return below active items in date order',()=>{
 const rows=networkOperationHistory([op('error','failed','2026-11-06'),op('done','confirmed','2026-11-03')],[item('waiting','unconfirmed','2026-11-01')]);
 assert.deepEqual(rows.map(r=>r.item.id),['waiting','error','done']);
});
