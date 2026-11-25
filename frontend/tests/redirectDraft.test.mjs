import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readRedirectDraft,recoveryDraft,redirectDraftKey,removeDraftConnection,pruneConfirmedRedirectDeletes,settledRedirectDeleteFailures} from '../src/redirectDraft.ts';
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

test('a confirmed deletion disappears from the draft instead of being sent twice',()=>{const deleted={...row,removed:true};assert.deepEqual(pruneConfirmedRedirectDeletes([deleted],[]),[]);});
test('a deletion still present in Webdev remains pending',()=>{const rows=[{...row,removed:true}];assert.equal(pruneConfirmedRedirectDeletes(rows,[baseline]),rows);});
test('reconciliation preserves all unrelated unsent edits and incomplete rows',()=>{const changed={...row,id:'edit',url:'edit.test',original:'edit.test'},blank={...row,id:'blank',url:'',original:'',value:''};const deleted={...row,removed:true};assert.deepEqual(pruneConfirmedRedirectDeletes([deleted,changed,blank],[]),[changed,blank]);});
test('an empty source in a new draft is not evidence of a confirmed deletion',()=>{const rows=[{...row,original:'',removed:true}];assert.equal(pruneConfirmedRedirectDeletes(rows,[]),rows);});
test('www and bare source domains remain distinct during deletion reconciliation',()=>{assert.deepEqual(pruneConfirmedRedirectDeletes([{...row,removed:true}],[{url:'www.drop.test',value:'main.test'}]),[]);});
test('source normalization matches pasted host case without changing destination paths',()=>{const rows=[{...row,original:'https://DROP.test/',removed:true}];assert.equal(pruneConfirmedRedirectDeletes(rows,[baseline]),rows);});

test('an unchanged baseline deleted from Webdev is removed without re-creating it',()=>{const old={...row,value:baseline.value};assert.deepEqual(pruneConfirmedRedirectDeletes([old],[]),[]);});
test('a deliberately edited row is preserved when its original disappeared',()=>{const rows=[row];assert.equal(pruneConfirmedRedirectDeletes(rows,[]),rows);});

test('obsolete failed deletion receipts can be hidden after confirmed absence',()=>{const item={id:'gone',status:'failed',request:{action:'domain_redirect',redirect_delete:true,redirect_original_source:'drop.test'}};assert.deepEqual(settledRedirectDeleteFailures([item],[]),[item]);assert.deepEqual(settledRedirectDeleteFailures([item],[baseline]),[]);});
test('unconfirmed requests and failed additions never get dismissed as completed deletes',()=>{const failedAdd={status:'failed',request:{action:'domain_redirect',redirect_source:'drop.test'}},pendingDelete={status:'unconfirmed',request:{action:'domain_redirect',redirect_delete:true,redirect_source:'drop.test'}};assert.deepEqual(settledRedirectDeleteFailures([failedAdd,pendingDelete],[]),[]);});
