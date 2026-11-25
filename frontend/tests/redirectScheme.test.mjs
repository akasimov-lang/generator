import {test} from 'node:test';
import assert from 'node:assert/strict';
import {cleanAddress,completeDrops,schemeProblems,unlinkedDomains,sourceChoices,orderRedirectChanges,graphDomainNames,redirectDomainScope} from '../src/redirectScheme.ts';
const domains=['old.test','second.test','new.test','main.test'];
const types={'old.test':'drop','second.test':'drop','new.test':'newreg','main.test':'newreg'};
test('pasted whitespace and protocol are removed while path case survives',()=>assert.equal(cleanAddress(' https:// new.test /Play/ '),'new.test/Play/'));
test('all unconnected drops get newreg destinations in the same network',()=>{const rows=completeDrops([],domains,types,'main.test');assert.equal(rows.length,2);assert.deepEqual(schemeProblems(rows,domains,types,'main.test'),[]);});
test('existing correct drop link is preserved',()=>{const rows=completeDrops([{url:'old.test',value:'new.test/Play/'}],domains,types,'main.test');assert.equal(rows[0].value,'new.test/Play/');});
test('drop to outside network rejected',()=>assert.match(schemeProblems([{url:'old.test',value:'outside.test'}],domains,types,'main.test').join(),/новорег/));
test('cycles rejected',()=>assert.match(schemeProblems([{url:'new.test',value:'main.test'},{url:'main.test',value:'new.test'}],domains,types,'').join(),/Цикл/));
test('duplicate aliases rejected',()=>assert.match(schemeProblems([{url:'old.test',value:'new.test'},{url:'www.old.test',value:'main.test'}],domains,types,'main.test').join(),/Повторяется/));
test('unconnected includes neither sources nor destinations',()=>assert.deepEqual(unlinkedDomains(domains,[{url:'old.test',value:'https://new.test/page/'}]),['second.test','main.test']));
test('missing newregs cannot silently plan redirects',()=>assert.throws(()=>completeDrops([],['old.test'],types,''),/новорегов/));

test('source picker sorts drops first and excludes confirmed and draft sources',()=>assert.deepEqual(sourceChoices(['main.test','new.test','second.test','old.test'],types,['old.test'],'main.test'),['second.test','new.test']));
test('source picker keeps selected value available without moving newregs above drops',()=>assert.deepEqual(sourceChoices(domains,types,['new.test'],'main.test','new.test'),['old.test','second.test','new.test']));

test('send final destinations first to avoid a temporary cycle during reversal',()=>assert.deepEqual(orderRedirectChanges([{url:'b.test',value:'a.test'},{url:'a.test',value:'c.test'}]).map(r=>r.url),['a.test','b.test']));
test('remove obsolete routes before new redirects',()=>assert.deepEqual(orderRedirectChanges([{url:'a.test',value:'b.test'},{url:'b.test',value:'a.test',removed:true}]).map(r=>r.url),['b.test','a.test']));

test('canvas initially includes only Main and redirect participants',()=>{const result=graphDomainNames(domains,[{url:'old.test',value:'main.test'}],'main.test',[]);assert.deepEqual(result.nodes,['main.test','old.test']);assert.deepEqual(result.unused,['second.test','new.test']);});
test('adding an unconnected domain to canvas does not create any redirects',()=>{const rows=[];const result=graphDomainNames(domains,rows,'main.test',['second.test']);assert.deepEqual(result.nodes,['main.test','second.test']);assert.deepEqual(result.unused,['old.test','new.test']);assert.deepEqual(rows,[]);});
test('Main aliases render once and removed participant returns to the list',()=>{const result=graphDomainNames(['main.test','old.test'],[],'www.main.test',[]);assert.deepEqual(result.nodes,['www.main.test']);assert.deepEqual(result.unused,['old.test']);});

test('AMP domains are excluded from source choices even when selected',()=>assert.deepEqual(sourceChoices(['amp.test','old.test'],{'amp.test':'amp','old.test':'drop'},[],'','amp.test'),['old.test']));
test('AMP membership removes sources, destinations and visible graph candidates',()=>{const result=redirectDomainScope(['old.test','new.test','amp.test'],[{url:'old.test',value:'amp.test'},{url:'amp.test',value:'new.test'},{url:'old.test',value:'new.test'}],{},['amp.test']);assert.deepEqual(result.domains,['old.test','new.test']);assert.deepEqual(result.redirects,[{url:'old.test',value:'new.test'}]);});
test('an amp-looking newreg remains eligible without an AMP role',()=>assert.deepEqual(redirectDomainScope(['brand-amp.test'],[],{'brand-amp.test':'newreg'}).domains,['brand-amp.test']));
test('children of AMP domains cannot reappear through redirects or custom destinations',()=>{const result=redirectDomainScope(['child.amp.test','safe.test'],[{url:'safe.test',value:'child.amp.test'}],{},['amp.test']);assert.deepEqual(result.domains,['safe.test']);assert.deepEqual(result.redirects,[]);assert.equal(result.isAmp('https://another.amp.test/path/'),true);});
test('empty AMP settings do not hide newly added blank rows',()=>{const result=redirectDomainScope([],[],{},['','']);assert.equal(result.isAmp(''),false);assert.equal(result.ampKeys.has(''),false);});


test('redirect chains may continue through multiple newregs before Main',()=>{assert.deepEqual(schemeProblems([{url:'drop.test',value:'new.test'},{url:'new.test',value:'next.test'},{url:'next.test',value:'main.test'}],['drop.test','new.test','next.test','main.test'],{'drop.test':'drop','new.test':'newreg','next.test':'newreg','main.test':'drop'},'main.test'),[]);});
