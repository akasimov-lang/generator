import assert from 'node:assert/strict';
import {test} from 'node:test';
import {menuMove,keyboardMenuMove} from '../src/menuReorder.ts';
const a={key:'a',group:'root',title:'A',address:[0]},b={key:'b',group:'root',title:'B',address:[1]},c={key:'c',group:'root',title:'C',address:[2]};
test('drag before and after sends exact source and destination addresses',()=>{
  assert.deepEqual(menuMove(c,a,'before'),{source:[2],target:[0],position:'before'});
  assert.deepEqual(menuMove(a,c,'after'),{source:[0],target:[2],position:'after'});
});
test('same position, missing cached nodes and other groups do not send writes',()=>{
  assert.equal(menuMove(a,a,'after'),null);
  assert.equal(menuMove(a,b,'before'),null);
  assert.equal(menuMove(b,a,'after'),null);
  assert.equal(menuMove(a,{...c,group:'footer'},'after'),null);
  assert.equal(menuMove({...a,address:undefined},c,'after'),null);
});
test('nested items stay in their actual parent and move as whole branches',()=>{
  const childA={...a,group:'parent',address:[0,0]},childB={...b,group:'parent',address:[0,1]};
  assert.deepEqual(menuMove(childB,childA,'before'),{source:[0,1],target:[0,0],position:'before'});
  assert.equal(menuMove(childA,{...childB,address:[1,1]},'before'),null);
});
test('keyboard movement uses adjacent siblings and stops at boundaries',()=>{
  assert.equal(keyboardMenuMove([a,b,c],'a',-1),null);
  assert.equal(keyboardMenuMove([a,b,c],'c',1),null);
  assert.deepEqual(keyboardMenuMove([a,b,c],'b',-1),{source:[1],target:[0],position:'before'});
  assert.deepEqual(keyboardMenuMove([a,b,c],'b',1),{source:[1],target:[2],position:'after'});
});
