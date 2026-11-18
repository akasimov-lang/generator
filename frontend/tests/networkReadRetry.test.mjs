import assert from 'node:assert/strict';
import test from 'node:test';
import {readNetworkWithRetry} from '../src/networkReadRetry.ts';
const busy=()=>Object.assign(new Error('Ожидает освобождения сетки. Продолжение выполняется автоматически.'),{statusCode:409});
test('network refresh retries the current lock response',async()=>{
 let attempts=0,waits=0;
 const result=await readNetworkWithRetry(async()=>{if(++attempts<3)throw busy();return 'fresh';},new AbortController().signal,()=>waits++,async()=>{});
 assert.equal(result,'fresh');assert.equal(attempts,3);assert.equal(waits,2);
});
test('read retry never treats an unrelated conflict as a temporary lock',async()=>{
 let attempts=0;
 await assert.rejects(readNetworkWithRetry(async()=>{attempts++;throw Object.assign(new Error('Предыдущая операция ещё не подтверждена.'),{statusCode:409});},new AbortController().signal,()=>{},async()=>{}));
 assert.equal(attempts,1);
});
test('closing the page cancels a waiting read without another request',async()=>{
 const controller=new AbortController();let attempts=0;
 await assert.rejects(readNetworkWithRetry(async()=>{attempts++;throw busy();},controller.signal,()=>{},async()=>controller.abort()),{name:'AbortError'});
 assert.equal(attempts,1);
});
