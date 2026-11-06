import assert from 'node:assert/strict';
import {test} from 'node:test';
import {pilotDomainFilter,pilotFilterReturnPath,projectFromPilotFilter} from '../src/pilotFilterNavigation.ts';
const report='/auto-reglue/pilot/logs?id=report-id&domainFilter=drops';
test('project links retain the exact report and selected category',()=>{
 const href=projectFromPilotFilter('/project-network/example.com/',report);
 assert.equal(new URL(href,'https://local.test').searchParams.get('pilotReturn'),report);
 assert.equal(pilotDomainFilter(new URL(report,'https://local.test').search),'drops');
});
test('ordinary project navigation has no return arrow context',()=>{
 assert.equal(projectFromPilotFilter('/project-network/example.com/','/sites'),'/project-network/example.com/');
 assert.equal(pilotFilterReturnPath('/auto-reglue/pilot/logs?id=report-id'),null);
});
test('external return URLs are rejected',()=>{
 assert.equal(pilotFilterReturnPath('https://evil.test'+report),null);
 assert.equal(pilotFilterReturnPath('//evil.test'+report),null);
 assert.equal(pilotFilterReturnPath('/\\evil.test'+report),null);
});
test('unknown filters and unrelated internal routes are rejected',()=>{
 assert.equal(pilotDomainFilter('?domainFilter=unknown'),null);
 assert.equal(pilotFilterReturnPath('/sites?id=report-id&domainFilter=drops'),null);
});
test('resetting the filter removes the return context',()=>{
 assert.equal(pilotFilterReturnPath('/auto-reglue/pilot/logs?id=report-id&domainFilter='),null);
});

test('added pages filter preserves return navigation and project type',()=>{
 const path='/auto-reglue/pilot/logs?id=report-id&domainFilter=internal_pages&projectType=general';
 assert.equal(pilotDomainFilter('?domainFilter=internal_pages'),'internal_pages');
 assert.equal(pilotFilterReturnPath(path),path);
 assert.equal(new URL(projectFromPilotFilter('/project-network/example.com/',path),'https://local.test').searchParams.get('pilotReturn'),path);
});

test('maintenance report returns to the same plan without a domain filter',()=>{
 const path='/auto-reglue/pilot/report?maintenance=bbdb21a4-e48a-470c-9943-1db229b28f8e';
 assert.equal(pilotFilterReturnPath(path),path);
 assert.equal(new URL(projectFromPilotFilter('/project-menu/example.com/',path),'https://local.test').searchParams.get('pilotReturn'),path);
});
