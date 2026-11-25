import {test} from 'node:test';
import assert from 'node:assert/strict';
import {graphCardAction,redirectChain,redirectBranch,unattachedGraphDomains,arrangeRedirectGraph,extendedBoardHeight,routeKey} from '../src/redirectGraphLayout.ts';
const row=(url,value)=>({url,value});

test('chain follows redirects to Main and leaves siblings out',()=>{
 const result=redirectChain('https://www.drop.test/',[row('drop.test','new.test'),row('new.test','main.test'),row('other.test','main.test')],'main.test');
 assert.deepEqual([...result.nodes],['drop.test','new.test','main.test']);assert.deepEqual([...result.links],['drop.test>new.test','new.test>main.test']);assert.equal(result.reachesMain,true);assert.equal(result.cycle,false);
});
test('incomplete paths do not claim to reach Main',()=>{const r=redirectChain('drop.test',[row('drop.test','end.test')],'main.test');assert.equal(r.reachesMain,false);assert.deepEqual([...r.nodes],['drop.test','end.test']);});
test('cycle tracing terminates and records the complete visible loop',()=>{const r=redirectChain('a.test',[row('a.test','b.test'),row('b.test','a.test')],'main.test');assert.equal(r.cycle,true);assert.equal(r.nodes.size,2);assert.equal(r.links.size,2);assert.equal(r.reachesMain,false);});
test('Main ends tracing even if malformed data contains its outgoing redirect',()=>{assert.equal(redirectChain('main.test',[row('main.test','bad.test')],'main.test').links.size,0);});
test('expansion adds one visible viewport using board coordinates at every zoom',()=>{assert.equal(extendedBoardHeight(1200,600,.5),2400);assert.equal(extendedBoardHeight(1200,600,2),1500);assert.equal(extendedBoardHeight(99999,600,1),100000);});
function assertNoOverlaps(layout,main){const boxes=Object.entries(layout.positions).map(([key,p])=>({...p,key,w:key==='main:'+main?360:280,h:key==='main:'+main?100:112}));for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){const a=boxes[i],b=boxes[j];assert.ok(a.x+a.w<=b.x||b.x+b.w<=a.x||a.y+a.h<=b.y||b.y+b.h<=a.y,`Overlap: ${a.key} / ${b.key}`);}}
test('sorting places each source below its destination and keeps chains together',()=>{const r=arrangeRedirectGraph(['main.test','new.test','drop.test'],[row('drop.test','new.test'),row('new.test','main.test')],'main.test',1400);assert.ok(r.positions['drop.test'].y>r.positions['new.test'].y);assert.ok(r.positions['new.test'].y>r.positions['main:main.test'].y);assertNoOverlaps(r,'main.test');});
test('large branching networks pack without overlap and do not mutate real redirects',()=>{const names=['main.test'],rows=[];for(let n=0;n<20;n++){names.push(`new${n}.test`);rows.push(row(`new${n}.test`,'main.test'));for(let d=0;d<3;d++){names.push(`drop${n}-${d}.test`);rows.push(row(`drop${n}-${d}.test`,`new${n}.test`));}}const before=JSON.stringify(rows);const result=arrangeRedirectGraph(names,rows,'main.test',1500);assert.equal(Object.keys(result.positions).length,81);assert.equal(JSON.stringify(rows),before);assertNoOverlaps(result,'main.test');assert.ok(result.width<1600);});
test('sorting keeps disconnected domains and malformed cycles visible exactly once',()=>{const names=['a.test','b.test','main.test','alone.test'];const result=arrangeRedirectGraph(names,[row('a.test','b.test'),row('b.test','a.test')],'main.test',900);assert.equal(Object.keys(result.positions).length,4);assertNoOverlaps(result,'main.test');});
test('sorting is stable regardless of previous card order and aliases',()=>{const names=['www.drop.test','main.test','new.test'];const rows=[row('drop.test','https://new.test/path/'),row('new.test','main.test')];assert.deepEqual(arrangeRedirectGraph(names,rows,'www.main.test',1400),arrangeRedirectGraph([...names].reverse(),rows,'main.test',1400));assert.equal(routeKey('www.drop.test','https://new.test/'),'drop.test>new.test');});


test('moving a middle domain highlights every incoming subchain and its path to Main',()=>{
 const rows=[row('tiny.test','drop.test'),row('drop.test','new.test'),row('other-drop.test','new.test'),row('new.test','middle.test'),row('middle.test','main.test'),row('sibling.test','middle.test'),row('other.test','main.test')];
 const result=redirectBranch('www.new.test',rows,'main.test');
 assert.deepEqual([...result.nodes].sort(),['drop.test','main.test','middle.test','new.test','other-drop.test','tiny.test']);
 assert.equal(result.links.size,5);assert.equal(result.links.has('tiny.test>drop.test'),true);assert.equal(result.links.has('other-drop.test>new.test'),true);assert.equal(result.nodes.has('sibling.test'),false);assert.equal(result.nodes.has('other.test'),false);assert.equal(result.reachesMain,true);
});
test('moving Main highlights all its redirect branches but excludes disconnected domains',()=>{
 const result=redirectBranch('main.test',[row('drop.test','new.test'),row('new.test','main.test'),row('other.test','main.test'),row('alone.test','outside.test')],'main.test');
 assert.deepEqual([...result.nodes].sort(),['drop.test','main.test','new.test','other.test']);assert.equal(result.links.size,3);
});
test('incoming cycles terminate without losing their visible links',()=>{
 const result=redirectBranch('a.test',[row('a.test','b.test'),row('b.test','a.test'),row('drop.test','b.test')],'main.test');
 assert.equal(result.cycle,true);assert.equal(result.nodes.size,3);assert.equal(result.links.size,3);
});
test('an invalid outgoing Main redirect never merges unrelated branches into the active subtree',()=>{
 const result=redirectBranch('new.test',[row('new.test','main.test'),row('main.test','new.test'),row('other.test','main.test')],'main.test');
 assert.equal(result.nodes.has('other.test'),false);assert.equal(result.links.has('main.test>new.test'),false);
});

test('red warning includes only visible domains without a complete path to Main',()=>{const result=unattachedGraphDomains(['main.test','direct.test','indirect.test','alone.test','cycle-a.test','cycle-b.test'],[row('direct.test','main.test'),row('indirect.test','direct.test'),row('cycle-a.test','cycle-b.test'),row('cycle-b.test','cycle-a.test')],'main.test');assert.deepEqual([...result].sort(),['alone.test','cycle-a.test','cycle-b.test']);});
test('removing the middle edge marks its entire incoming subtree as disconnected',()=>{const names=['main.test','new.test','drop.test','tiny.test'];const rows=[row('new.test','main.test'),row('drop.test','new.test'),row('tiny.test','drop.test')];assert.equal(unattachedGraphDomains(names,rows,'main.test').size,0);assert.deepEqual([...unattachedGraphDomains(names,rows.slice(1),'main.test')].sort(),['drop.test','new.test','tiny.test']);});
test('restoring a path clears red warnings, including www aliases',()=>{assert.equal(unattachedGraphDomains(['www.drop.test','main.test'],[row('drop.test','https://www.main.test/')],'main.test').size,0);});


test('a newreg receiving an incoming redirect can immediately start its next hop',()=>{assert.equal(graphCardAction('new.test',[row('drop.test','new.test')],'main.test'),'connect');});
test('a domain already forwarding traffic inspects by body click but connects by plus',()=>{const rows=[row('new.test','next.test')];assert.equal(graphCardAction('new.test',rows,'main.test'),'inspect');assert.equal(graphCardAction('new.test',rows,'main.test',{plus:true}),'connect');});
test('an in-progress connection can choose a newreg that already has an outgoing redirect',()=>{assert.equal(graphCardAction('next.test',[row('next.test','main.test')],'main.test',{connecting:true}),'connect');});
test('hand zone always inspects the branch and never accidentally connects',()=>{assert.equal(graphCardAction('new.test',[],'main.test',{branch:true,connecting:true}),'branch');});
test('Main remains inspectable while a free chain endpoint starts a connection',()=>{assert.equal(graphCardAction('main.test',[],'main.test'),'inspect');assert.equal(graphCardAction('www.new.test',[row('drop.test','new.test')],'main.test'),'connect');});
