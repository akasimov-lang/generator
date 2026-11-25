import {test} from 'node:test';
import assert from 'node:assert/strict';
import {boundary,edgePoints,movedPointer,clampShelfWidth,clampBoardZoom,boardPoint,cardSize,resizedNodeBox} from '../src/redirectGraphGeometry.ts';
test('arrow ends at the Main circle boundary instead of behind the node',()=>{const edge=edgePoints({x:0,y:0,width:100,height:100},{x:200,y:0,width:100,height:100,circle:true});assert.deepEqual(edge,{start:{x:100,y:50},end:{x:200,y:50}});});
test('diagonal line meets a circle radius',()=>{const p=boundary({x:0,y:0,width:100,height:100,circle:true},{x:150,y:150});assert.ok(Math.abs(Math.hypot(p.x-50,p.y-50)-50)<1e-9);});
test('small pointer jitter remains a click while moving a card does not create a link',()=>{assert.equal(movedPointer({x:0,y:0},{x:3,y:3}),false);assert.equal(movedPointer({x:0,y:0},{x:9,y:0}),true);});

test('sidebar width leaves room for the board and caps excessive dragging',()=>{assert.equal(clampShelfWidth(800,1400),640);assert.equal(clampShelfWidth(10,1400),180);assert.equal(clampShelfWidth(600,600),360);});
test('saved sidebar width adapts to a narrow window',()=>{assert.equal(clampShelfWidth(600,360),180);assert.equal(clampShelfWidth(NaN,1400),300);});

test('zoom respects supported range and restores invalid saved values',()=>{assert.equal(clampBoardZoom(.1),.4);assert.equal(clampBoardZoom(4),2);assert.equal(clampBoardZoom(NaN),1);});
test('pointer and dropped domains keep board coordinates when zoomed out',()=>assert.deepEqual(boardPoint({x:250,y:150},{x:50,y:50},.5),{x:400,y:200}));
test('pointer coordinates account for zoom in and viewport offset',()=>assert.deepEqual(boardPoint({x:250,y:150},{x:50,y:50},2),{x:100,y:50}));
test('default card sizes remain unchanged until explicitly resized',()=>{assert.deepEqual(cardSize(undefined),{width:280,height:112});assert.deepEqual(cardSize(undefined,true),{width:360,height:100});});
test('top-right resizing follows zoom and keeps the opposite corner fixed',()=>{const start={x:30,y:150,width:280,height:112};const next=resizedNodeBox(start,{x:50,y:-25},.5);assert.deepEqual(next,{x:30,y:100,width:380,height:162});assert.equal(next.y+next.height,start.y+start.height);const edge=edgePoints(next,{x:600,y:100,width:280,height:112});assert.equal(edge.start.x,next.x+next.width);});
test('resize cannot collapse content or move above the working board',()=>{assert.deepEqual(resizedNodeBox({x:0,y:0,width:280,height:112},{x:-999,y:-999},1),{x:0,y:0,width:240,height:112});assert.deepEqual(cardSize({width:99999,height:99999}),{width:900,height:600});});
