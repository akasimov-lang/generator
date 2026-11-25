import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readRedirectDraft,recoveryDraft,redirectDraftKey,removeDraftConnection} from '../src/redirectDraft.ts';
const baseline={url:'drop.test',value:'old.test'};
const row={id:'one',original:'drop.test',url:'drop.test',value:'new.test',expected:{rows:[baseline]}};
test('draft round trip keeps edited target and concurrency precondition separately',()=>{const restored=readRedirectDraft(JSON.stringify({version:1,rows:[row],saved_at:'2026-11-25T12:00:00Z'}));assert.equal(restored.rows[0].value,'new.test');assert.deepEqual(restored.rows[0].expected.rows,[baseline]);});
test('incomplete and invalid-for-submit links can still be saved as a draft',()=>{assert.equal(readRedirectDraft(JSON.stringify({version:1,rows:[{...row,url:'',value:''}],saved_at:'now'})).rows[0].url,'');});
test('damaged or unsupported drafts cannot replace working editor state',()=>{assert.equal(readRedirectDraft('{'),null);assert.equal(readRedirectDraft(JSON.stringify({version:1,rows:[{...row,expected:null}],saved_at:'now'})),null);});
test('draft storage separates users and projects',()=>{assert.notEqual(redirectDraftKey('one','a'),redirectDraftKey('one','b'));assert.notEqual(redirectDraftKey('one','a'),redirectDraftKey('two','a'));});
test('old-tab recovery preserves new live routes not present in its snapshot',()=>{let id=0;const result=recoveryDraft(JSON.stringify({version:1,path:'/one',desiredRows:[{url:'drop.test',value:'new.test'}]}),'/one',[baseline,{url:'added.test',value:'main.test'}],()=>String(++id));assert.equal(result.rows[0].value,'new.test');assert.deepEqual(result.rows[0].expected.rows,[baseline]);assert.equal(result.rows[1].url,'added.test');});
test('recovery from another project is rejected',()=>{assert.equal(recoveryDraft(JSON.stringify({version:1,path:'/other',desiredRows:[]}),'/one',[],()=>''),null);});

test('deleting a confirmed connection keeps its original concurrency snapshot',()=>{const result=removeDraftConnection([row],'drop.test','new.test');assert.equal(result[0].removed,true);assert.deepEqual(result[0].expected.rows,[baseline]);assert.equal(row.removed,undefined);});
test('deleting a new draft connection needs no live removal request',()=>{const fresh={...row,id:'new',original:'',expected:{rows:[]}};assert.deepEqual(removeDraftConnection([fresh],'drop.test','new.test'),[]);});
test('deleting an edge preserves incoming redirects and other planned changes',()=>{const incoming={...row,id:'incoming',url:'incoming.test',value:'drop.test',original:''};const result=removeDraftConnection([incoming,row],'drop.test','new.test');assert.equal(result[0],incoming);assert.equal(result[1].removed,true);});
test('a stale selected target cannot delete a different current redirect',()=>{const rows=[row];assert.equal(removeDraftConnection(rows,'drop.test','stale.test'),rows);});
