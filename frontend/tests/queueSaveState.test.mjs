import assert from 'node:assert/strict';
import test from 'node:test';
import { queueSaveState } from '../src/queueSaveState.ts';
const item=(status,message='Статус сервера')=>({id:status,status,message,request:{action:'domain_redirect'},created_at:'2026-11-23T09:45:00Z'});
test('waiting for other project operations is not displayed as saving',()=>{
 assert.equal(queueSaveState([item('waiting','Ожидает предыдущее изменение…')]).state,'waiting');
 assert.equal(queueSaveState([item('queued')]).state,'waiting');
});
test('uncertain submission shows actionable error even with later queued work',()=>{
 const result=queueSaveState([item('queued'),item('unconfirmed','Отправка не подтверждена.')]);
 assert.equal(result.state,'error');assert.equal(result.message,'Отправка не подтверждена.');
});
test('terminal failure releases saving indicator and preserves server reason',()=>{
 const result=queueSaveState([item('failed','Редактируемое значение изменилось.')]);
 assert.equal(result.state,'error');assert.equal(result.message,'Редактируемое значение изменилось.');
});
test('confirmed completion reports success and processing reports server progress',()=>{
 assert.equal(queueSaveState([item('completed')]).state,'saved');
 assert.equal(queueSaveState([item('processing')]).state,'saving');
 assert.equal(queueSaveState([]).state,'idle');
});
