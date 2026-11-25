import assert from 'node:assert/strict';
import {test} from 'node:test';
import {redirectTableColumns} from '../src/redirectTableColumns.ts';

test('46 redirects fill three columns of fifteen and continue in a fourth column',()=>{
  const rows=Array.from({length:46},(_,index)=>({id:index}));
  const columns=redirectTableColumns(rows);
  assert.deepEqual(columns.map(column=>column.length),[15,15,15,1]);
  assert.deepEqual(columns.flat(),rows);
  assert.equal(columns[1][0],rows[15]);
});
test('exactly fifteen redirects need only one column',()=>{
  assert.deepEqual(redirectTableColumns(Array.from({length:15},(_,i)=>i)).map(c=>c.length),[15]);
});
test('an empty table has no placeholder columns',()=>{
  assert.deepEqual(redirectTableColumns([]),[]);
});
