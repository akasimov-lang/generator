import test from 'node:test';
import assert from 'node:assert/strict';
import {notesFirst} from '../src/projectNoteOrder.ts';
test('notes stay above unnoted rows in ascending and descending sorts, before pagination',()=>{
 const noted=new Set(['b','d']);
 const rows=['a','b','c','d','e'];
 assert.deepEqual([...rows].sort((a,b)=>notesFirst(a,b,noted)||a.localeCompare(b)).slice(0,3),['b','d','a']);
 assert.deepEqual([...rows].sort((a,b)=>notesFirst(a,b,noted)||b.localeCompare(a)),['d','b','e','c','a']);
});
test('no notes preserves existing sort, clearing removes priority',()=>{
 const rows=['c','b','a'];
 assert.deepEqual([...rows].sort((a,b)=>notesFirst(a,b,new Set())),rows);
 assert.deepEqual([...rows].sort((a,b)=>notesFirst(a,b,new Set(['a']))),['a','c','b']);
});
