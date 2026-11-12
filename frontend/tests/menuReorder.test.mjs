import assert from 'node:assert/strict';
import {test} from 'node:test';
import {menuMove,keyboardMenuMove,applyMenuMove,menuDragPreview,persistMenuMove} from '../src/menuReorder.ts';
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

test('optimistic move carries the whole branch and preserves the original snapshot',()=>{
  const rows=[{id:'a',url:'/a',children:[{id:'aa',custom:true}],order:0},{id:'b',url:'/b',order:1},{id:'c',url:'/c',order:2}];
  const original=structuredClone(rows);
  const moved=applyMenuMove(rows,{source:[0],target:[2],position:'after'});
  assert.deepEqual(moved.map(row=>row.id),['b','c','a']);
  assert.deepEqual(moved.map(row=>row.order),[0,1,2]);
  assert.equal(moved[2].children,rows[0].children);
  assert.equal(moved[2].url,'/a');assert.deepEqual(rows,original);
});
test('nested optimistic move changes only siblings under the selected raw parent',()=>{
  const rows=[{id:'parent',subMenu:[{id:'a',url:'/a'},{id:'b',url:'/b'}]},{id:'other',children:[{id:'untouched'}]}];
  const moved=applyMenuMove(rows,{source:[0,1],target:[0,0],position:'before'});
  assert.deepEqual(moved[0].subMenu.map(row=>row.id),['b','a']);
  assert.equal(moved[1],rows[1]);assert.equal(rows[0].subMenu[0].id,'a');
  assert.throws(()=>applyMenuMove(rows,{source:[0,1],target:[1,0],position:'before'}));
});
test('pointer preview moves variable-height branches into nonoverlapping slots',()=>{
  const slots=[{key:'a',top:10,height:160},{key:'b',top:170,height:50},{key:'c',top:220,height:70}];
  assert.deepEqual(menuDragPreview(slots,'a',280),{target:'c',position:'after',offsets:{b:-160,c:-160,a:120}});
  assert.deepEqual(menuDragPreview(slots,'c',20),{target:'a',position:'before',offsets:{c:-210,a:70,b:70}});
});
test('preview uses original slots so repeated pointer positions cannot oscillate',()=>{
  const slots=[{key:'a',top:0,height:50},{key:'b',top:50,height:50},{key:'c',top:100,height:50}];
  const forward=menuDragPreview(slots,'a',80);
  assert.equal(forward.target,'b');assert.deepEqual(menuDragPreview(slots,'a',80),forward);
  assert.equal(menuDragPreview(slots,'a',20).target,undefined);
  assert.equal(menuDragPreview(slots,'missing',20),null);
});
const rows=[{id:'a',url:'/a',order:0},{id:'b',url:'/b',order:1}];
const move={source:[0],target:[1],position:'after'};
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
test('drop updates immediately while saving and confirmation uses the returned menu without reloading',async()=>{
  const reply=deferred(),calls=[],shown=[];
  const saving=persistMenuMove(async(path,options)=>{calls.push([path,JSON.parse(options.body)]);return reply.promise;},'first','header',rows,move,items=>shown.push(items));
  assert.deepEqual(shown[0].map(row=>row.id),['b','a']);
  assert.deepEqual(calls,[['/sites/first/menu/header/reorder',{...move,expected_menu:rows}]]);
  const confirmed=applyMenuMove(rows,move);reply.resolve({success:true,items:confirmed});await saving;
  assert.equal(shown.at(-1),confirmed);assert.equal(calls.length,1);
});
test('conflict rolls back optimistic order and shows authoritative cache without a second write',async()=>{
  const actual=[{id:'new'},{id:'a'},{id:'b'}],shown=[],calls=[];
  await assert.rejects(persistMenuMove(async(path,options)=>{
    calls.push([path,options]);if(options.method==='POST')throw Error('Conflict');
    return {default_menu:{footer:actual}};
  },'second','footer',rows,move,items=>shown.push(items)),/Conflict/);
  assert.deepEqual(shown[0].map(row=>row.id),['b','a']);
  assert.equal(shown[1],rows);assert.equal(shown[2],actual);
  assert.equal(calls.filter(([,options])=>options.method==='POST').length,1);
  assert.equal(calls[1][0],'/sites/lookup?site_id=second');
});
test('network failure and failed recovery leave original order and never report success',async()=>{
  const shown=[];let writes=0;
  await assert.rejects(persistMenuMove(async(_path,options)=>{if(options.method==='POST')writes++;throw Error('offline');},'first','header',rows,move,items=>shown.push(items)),/offline/);
  assert.equal(shown.at(-1),rows);assert.equal(writes,1);
});
