import {test} from 'node:test';
import assert from 'node:assert/strict';
import {boundary,edgePoints,movedPointer,clampShelfWidth} from '../src/redirectGraphGeometry.ts';
test('arrow ends at the Main circle boundary instead of behind the node',()=>{const edge=edgePoints({x:0,y:0,width:100,height:100},{x:200,y:0,width:100,height:100,circle:true});assert.deepEqual(edge,{start:{x:100,y:50},end:{x:200,y:50}});});
test('diagonal line meets a circle radius',()=>{const p=boundary({x:0,y:0,width:100,height:100,circle:true},{x:150,y:150});assert.ok(Math.abs(Math.hypot(p.x-50,p.y-50)-50)<1e-9);});
test('small pointer jitter remains a click while moving a card does not create a link',()=>{assert.equal(movedPointer({x:0,y:0},{x:3,y:3}),false);assert.equal(movedPointer({x:0,y:0},{x:9,y:0}),true);});

test('sidebar width leaves room for the board and caps excessive dragging',()=>{assert.equal(clampShelfWidth(800,1400),640);assert.equal(clampShelfWidth(10,1400),180);assert.equal(clampShelfWidth(600,600),360);});
test('saved sidebar width adapts to a narrow window',()=>{assert.equal(clampShelfWidth(600,360),180);assert.equal(clampShelfWidth(NaN,1400),300);});
