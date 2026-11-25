import assert from 'node:assert/strict';
import {test} from 'node:test';
import {pageRedirectDraftKey,readPageRedirectDraft} from '../src/pageRedirectDraft.ts';
const row={id:'one',domain:'main.test',url:'/page/',value:'https://main.test/target/',original:{domain:'main.test',url:'/page',value:'https://old.test/'},removed:true};
test('draft restoration preserves slash differences, original addresses and pending deletion',()=>{
  assert.deepEqual(readPageRedirectDraft(JSON.stringify({version:1,rows:[row]})),[row]);
});
test('a new unfinished row survives reload',()=>{
  const blank={id:'new',domain:'main.test',url:'',value:''};
  assert.deepEqual(readPageRedirectDraft(JSON.stringify({version:1,rows:[blank]})),[blank]);
});
test('invalid stored originals cannot become redirect edit preconditions',()=>{
  assert.equal(readPageRedirectDraft(JSON.stringify({version:1,rows:[{...row,original:{url:'/page/'}}]})),null);
});
test('duplicate row ids cannot restore ambiguous editing state',()=>{
  assert.equal(readPageRedirectDraft(JSON.stringify({version:1,rows:[row,row]})),null);
});
test('broken browser storage is ignored',()=>{
  assert.equal(readPageRedirectDraft('{broken'),null);
});
test('draft storage separates users and projects without separator collisions',()=>{
  assert.notEqual(pageRedirectDraftKey('project-one','anton'),pageRedirectDraftKey('project-two','anton'));
  assert.notEqual(pageRedirectDraftKey('project-one','anton'),pageRedirectDraftKey('project-one','other'));
  assert.notEqual(pageRedirectDraftKey('c','a:b'),pageRedirectDraftKey('b:c','a'));
});
