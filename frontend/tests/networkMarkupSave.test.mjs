import assert from 'node:assert/strict';
import test from 'node:test';
import {saveMarkupWithRetry} from '../src/networkMarkupSave.ts';
import {mergeMarkupDraft,mergeCanonicalDraft} from '../src/networkDrafts.ts';
const conflict=message=>Object.assign(new Error(message),{statusCode:409});

test('revision race re-reads settings and keeps only the edited PagePilot fields',async()=>{
 const draft={standard:'pp root',originalStandard:'old root',fake:'old fake',originalFake:'old fake'};
 let calls=0;const writes=[];
 const result=await saveMarkupWithRetry(async()=>{
  calls++;
  const merged=mergeCanonicalDraft(draft,'remote root',`fresh fake ${calls}`);
  writes.push(merged);
  if(calls===1)throw conflict('Настройки сетки изменились.');
  return merged;
 },()=>{},async()=>{});
 assert.equal(calls,2);assert.equal(result.standard,'pp root');assert.equal(result.fake,'fresh fake 2');
 assert.equal(result.originalStandard,'remote root');
});
test('a lost write response is not resent',async()=>{
 let writes=0;
 await assert.rejects(saveMarkupWithRetry(async()=>{writes++;throw new Error('timeout');},()=>{},async()=>{}),/timeout/);
 assert.equal(writes,1);
});
test('unconfirmed earlier operations do not trigger automatic writes',async()=>{
 let calls=0;
 await assert.rejects(saveMarkupWithRetry(async()=>{calls++;throw conflict('Предыдущая операция ещё не подтверждена.');},()=>{},async()=>{}));
 assert.equal(calls,1);
});
test('temporary locks are bounded and report waiting',async()=>{
 let calls=0,notices=0;
 await assert.rejects(saveMarkupWithRetry(async()=>{calls++;throw conflict('С сеткой уже выполняется операция');},()=>notices++,async()=>{}));
 assert.equal(calls,6);assert.equal(notices,5);
});
test('rebase preserves the local switch and imports unedited remote markup',()=>{
 const draft={markup:'old',originalMarkup:'old',enabled:false,originalEnabled:true};
 assert.deepEqual(mergeMarkupDraft(draft,'fresh',true),{markup:'fresh',originalMarkup:'fresh',enabled:false,originalEnabled:true});
});

test('current server lock message retries then saves the exact manually edited markup',async()=>{
 const manual='<link rel="alternate" hreflang="pl" href="https://manual.test/" />\n';
 const draft={markup:manual,originalMarkup:'old',enabled:true,originalEnabled:true};
 let attempts=0,notices=0;
 const result=await saveMarkupWithRetry(async()=>{
  if(++attempts===1)throw conflict('Ожидает освобождения сетки. Продолжение выполняется автоматически.');
  return mergeMarkupDraft(draft,'automatic new path',false);
 },()=>notices++,async()=>{});
 assert.equal(attempts,2);assert.equal(notices,1);assert.equal(result.markup,manual);assert.equal(result.enabled,false);
});
test('exhausted lock retry reports an actionable stop instead of promising automatic continuation',async()=>{
 await assert.rejects(saveMarkupWithRetry(async()=>{throw conflict('Ожидает освобождения сетки. Продолжение выполняется автоматически.');},()=>{},async()=>{}),/Нажмите Enter/);
});
