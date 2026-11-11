import {test} from 'node:test';
import assert from 'node:assert/strict';
import {pilotTaskView,pilotTaskCollectionPath,pilotTaskDays,pilotTaskTime} from '../src/pilotTaskView.ts';
test('all tabs and pages derive from one snapshot without losing rows beyond first page',()=>{
 const items=Array.from({length:125},(_,i)=>({id:String(i),group:i<50?'layout':'brands'}));
 assert.equal(pilotTaskView(items,'all').total,125);
 assert.deepEqual(pilotTaskView(items,'brands',50).items,items.slice(100));
 assert.equal(pilotTaskView(items,'brands').total,75);
 assert.equal(pilotTaskView(items,'layout',100).offset,0);
 assert.equal(pilotTaskView(items,'showcases').total,0);
 assert.equal(items.length,125);
});
test('query is encoded independently from selected group and pagination',()=>{
 assert.equal(pilotTaskCollectionPath('  Brand & PL  '),'/auto-reglue/pilot/task-collection?q=Brand+%26+PL');
 assert.equal(pilotTaskCollectionPath(' '),'/auto-reglue/pilot/task-collection?');
});
test('reports are sorted newest first before pagination regardless of status',()=>{
 const items=Object.freeze([
  {id:'old',status:'running',group:'layout',launched_at:'2026-11-09T12:00:00Z'},
  {id:'new',status:'completed',group:'layout',launched_at:'2026-11-11T12:00:00Z'},
  {id:'middle',status:'failed',group:'brands',launched_at:'2026-11-10T12:00:00Z'},
  {id:'missing',status:'running',group:'layout'},
 ]);
 assert.deepEqual(pilotTaskView(items,'all',0,2).items.map(row=>row.id),['new','middle']);
 assert.deepEqual(pilotTaskView(items,'all',2,2).items.map(row=>row.id),['old','missing']);
 assert.deepEqual(pilotTaskView(items,'layout').items.map(row=>row.id),['new','old','missing']);
 assert.deepEqual(items.map(row=>row.id),['old','new','middle','missing']);
});
test('day boundaries follow Moscow time including timestamps without timezone',()=>{
 const items=[{id:'late',launched_at:'2026-11-10T21:10:00'},
  {id:'midnight',launched_at:'2026-11-11T00:00:00+03:00'},
  {id:'previous',launched_at:'2026-11-10T20:59:59Z'}];
 const groups=pilotTaskDays(pilotTaskView(items,'all').items);
 assert.deepEqual(groups.map(day=>[day.date,day.items.map(row=>row.id)]),[
  ['11.11.2026',['late','midnight']],['10.11.2026',['previous']]]);
 assert.equal(pilotTaskTime({id:'fallback',created_at:'2026-11-10T21:10:00Z'}),pilotTaskTime(items[0]));
});
test('invalid or absent dates form the last group and empty results have no date header',()=>{
 const items=[{id:'invalid',launched_at:'invalid'},{id:'valid',launched_at:'2026-11-11T12:00:00Z'},{id:'missing'}];
 assert.deepEqual(pilotTaskDays(pilotTaskView(items,'all').items).map(day=>[day.date,day.items.map(row=>row.id)]),[
  ['11.11.2026',['valid']],['Дата не указана',['invalid','missing']]]);
 assert.deepEqual(pilotTaskDays([]),[]);
});
