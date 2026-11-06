import assert from 'node:assert/strict';
import {test} from 'node:test';
import {saveDraftForDrops,restoredDraftFromDrops} from '../src/pilotDropsNavigation.ts';
test('disabled stock checkbox survives visiting Drops',()=>{
 const data=new Map();const storage={getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value),removeItem:key=>data.delete(key)};
 const token='11111111-1111-4111-8111-111111111111';
 const form={selection:{brands:['Lemon Casino'],geos:[]},titleMode:'minimal',allowStockDrops:false,shares:{subdomains:'20',without_alternates:'10',redirects:'40',title_h1:'40',paragraphs:'30'}};
 assert.equal(saveDraftForDrops(storage,token,'/auto-reglue/pilot?new=1',form),true);
 const restored=restoredDraftFromDrops(storage,`/auto-reglue/pilot?new=1&resumeDrops=${token}`);
 assert.equal(restored.form.allowStockDrops,false);
});
