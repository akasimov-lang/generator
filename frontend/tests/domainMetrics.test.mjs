import assert from 'node:assert/strict';
import {test} from 'node:test';
import {metricCount,metricForDomain} from '../src/domainMetrics.ts';
test('confirmed zero is distinct from missing Ahrefs data',()=>{assert.equal(metricCount(0),'0');assert.equal(metricCount(null),'—');assert.equal(metricCount(undefined),'—');});
test('large counts compact only for cards',()=>{assert.equal(metricCount(12500),'12,500');assert.equal(metricCount(12500,true),'12.5K');});
test('Ahrefs data stays scoped to its exact host',()=>{const record={dr:33};const metrics={'www.one.test':record};assert.equal(metricForDomain(metrics,'https://www.one.test/'),record);assert.equal(metricForDomain(metrics,'one.test'),undefined);assert.equal(metricForDomain(metrics,'child.one.test'),undefined);});
