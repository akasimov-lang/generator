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
