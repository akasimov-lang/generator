import assert from 'node:assert/strict';
import {test} from 'node:test';
import {mergeMarkupDraft,mergeCanonicalDraft} from '../src/networkDrafts.ts';

test('a canonical save acknowledgement preserves edits to the other canonical field',()=>{
 const sent={standard:'new root',fake:'old fake',originalStandard:'old root',originalFake:'old fake'};
 const current={...sent,fake:'new fake typed during save'};
 const result=mergeCanonicalDraft(current,'new root','old fake',sent);
 assert.deepEqual(result,{standard:'new root',fake:current.fake,originalStandard:'new root',originalFake:'old fake'});
 assert.deepEqual(mergeCanonicalDraft(result,'new root','old fake'),result);
});
test('typing more in the same field while saving preserves the new text and updates its baseline',()=>{
 const sent={markup:'first',enabled:true,originalMarkup:'old',originalEnabled:true};
 const current={...sent,markup:'second'};
 assert.deepEqual(mergeMarkupDraft(current,'first',true,sent),{...current,originalMarkup:'first'});
});
test('remote refresh updates clean fields and rebases edited PagePilot values',()=>{
 const current={standard:'unsaved',fake:'old fake',originalStandard:'old root',originalFake:'old fake'};
 assert.deepEqual(mergeCanonicalDraft(current,'external root','external fake'),{
  standard:'unsaved',fake:'external fake',originalStandard:'external root',originalFake:'external fake'});
});
test('a successful save of the unchanged draft makes it clean',()=>{
 const sent={markup:'new',enabled:false,originalMarkup:'old',originalEnabled:true};
 assert.deepEqual(mergeMarkupDraft(sent,'new',false,sent),{markup:'new',enabled:false,originalMarkup:'new',originalEnabled:false});
});

test('a stale browser draft keeps its edited text without retaining a conflicting baseline',()=>{
 const old={markup:'PagePilot selection',enabled:true,originalMarkup:'old server markup',originalEnabled:true};
 assert.deepEqual(mergeMarkupDraft(old,'new server markup',false),{
  markup:'PagePilot selection',enabled:false,originalMarkup:'new server markup',originalEnabled:false});
});
test('an already confirmed browser value becomes clean on reload',()=>{
 const old={markup:'saved',enabled:true,originalMarkup:'before',originalEnabled:false};
 assert.deepEqual(mergeMarkupDraft(old,'saved',true),{markup:'saved',enabled:true,originalMarkup:'saved',originalEnabled:true});
});

test('acknowledgement imports automatic changes to untouched fields without a new dirty draft',()=>{
 const sent={standard:'manual root',originalStandard:'old root',fake:'old path',originalFake:'old path'};
 assert.deepEqual(mergeCanonicalDraft(sent,'manual root','new automatic path',sent),{
  standard:'manual root',originalStandard:'manual root',fake:'new automatic path',originalFake:'new automatic path'});
});
test('a confirmed switch change does not restore an old automatic alternate path',()=>{
 const sent={markup:'old path',originalMarkup:'old path',enabled:false,originalEnabled:true};
 assert.deepEqual(mergeMarkupDraft(sent,'new path',false,sent),{
  markup:'new path',originalMarkup:'new path',enabled:false,originalEnabled:false});
});
test('an edit reverted during save remains a deliberate local change',()=>{
 const sent={markup:'first edit',originalMarkup:'old path',enabled:true,originalEnabled:true};
 const current={...sent,markup:'old path'};
 assert.deepEqual(mergeMarkupDraft(current,'first edit',true,sent),{...current,originalMarkup:'first edit'});
});
test('a clean alternate follows a later automatic fake path change',()=>{
 const saved={markup:'manual path',originalMarkup:'manual path',enabled:true,originalEnabled:true};
 assert.deepEqual(mergeMarkupDraft(saved,'automatic path',true),{...saved,markup:'automatic path',originalMarkup:'automatic path'});
});
