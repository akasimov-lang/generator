import {test} from 'node:test';
import assert from 'node:assert/strict';
import {pilotTaskView,pilotTaskCollectionPath} from '../src/pilotTaskView.ts';
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
