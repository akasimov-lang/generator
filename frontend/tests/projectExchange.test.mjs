import assert from 'node:assert/strict';
import test from 'node:test';
import {isProjectExchangeRequest,queuePollDue} from '../src/projectExchange.ts';

test('queue and overview polling do not light up the Webdev exchange badge',()=>{
 assert.equal(isProjectExchangeRequest('/sites/one/network/fake-main-queue'),false);
 assert.equal(isProjectExchangeRequest('/sites/one/network/edit-queue'),false);
 assert.equal(isProjectExchangeRequest('/sites/one/overview'),false);
 assert.equal(isProjectExchangeRequest('/sites/one/network'),false);
});
test('explicit live refresh and write still indicate exchange',()=>{
 assert.equal(isProjectExchangeRequest('/sites/one/network?refresh=true'),true);
 assert.equal(isProjectExchangeRequest('/sites/one/network/operations','POST'),true);
 assert.equal(isProjectExchangeRequest('/sites/one/notifications','POST'),false);
});
test('idle queue polls every 30 seconds; active queue every 3; hidden tabs stop',()=>{
 assert.equal(queuePollDue(0,0,3000,false),false);
 assert.equal(queuePollDue(0,0,29999,false),false);
 assert.equal(queuePollDue(0,0,30000,false),true);
 assert.equal(queuePollDue(1,0,2999,false),false);
 assert.equal(queuePollDue(1,0,3000,false),true);
 assert.equal(queuePollDue(1,0,30000,true),false);
});
