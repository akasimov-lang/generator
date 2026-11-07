import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readPilotTasks,savePilotTasks,clearPilotTasks} from '../src/pilotTaskCache.ts';
function store(){const m=new Map();return {get length(){return m.size},key:i=>[...m.keys()][i],getItem:k=>m.get(k)||null,setItem:(k,v)=>m.set(k,v),removeItem:k=>m.delete(k)};}
test('cached task pages appear immediately only for the same permission scope',()=>{const s=store();savePilotTasks('anton:all','page1',{total:12},s);assert.deepEqual(readPilotTasks('anton:all','page1',s),{total:12});assert.equal(readPilotTasks('anton:restricted','page1',s),null);assert.equal(readPilotTasks('other:all','page1',s),null);assert.equal(readPilotTasks('anton:all','page2',s),null);});
test('mutations and logout discard old task pages without touching other storage',()=>{const s=store();s.setItem('unrelated','keep');savePilotTasks('anton','page1',{total:12},s);clearPilotTasks(s);assert.equal(readPilotTasks('anton','page1',s),null);assert.equal(s.getItem('unrelated'),'keep');});
test('unavailable storage does not prevent loading from the server',()=>{const s={getItem(){throw Error('disabled')},setItem(){throw Error('disabled')},get length(){throw Error('disabled')}};assert.equal(readPilotTasks('a','p',s),null);assert.doesNotThrow(()=>savePilotTasks('a','p',{},s));assert.doesNotThrow(()=>clearPilotTasks(s));});
