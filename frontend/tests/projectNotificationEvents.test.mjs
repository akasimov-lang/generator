import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import {createServer} from 'vite';
const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {projectApiResult,PROJECT_CHANGED_EVENT,NOTICE_EVENT}=await server.ssrLoadModule('/src/projectNotificationEvents.ts');
const siteId='00000000-0000-0000-0000-000000000001';
const events=[];
globalThis.window={dispatchEvent:event=>events.push(event)};
after(()=>delete globalThis.window);
test('menu reorder success and failure stay inline without global refresh or notification',()=>{
  projectApiResult(`/sites/${siteId}/menu/header/reorder`,'POST');
  projectApiResult(`/sites/${siteId}/menu/footer/reorder`,'POST',Error('Conflict'));
  assert.deepEqual(events,[]);
});
test('other project writes still trigger refresh and failure notification',()=>{
  projectApiResult(`/sites/${siteId}/sections`,'POST');
  projectApiResult(`/sites/${siteId}/sections`,'POST',Error('Offline'));
  assert.equal(events[0].type,PROJECT_CHANGED_EVENT);
  assert.equal(events[1].type,NOTICE_EVENT);
});
