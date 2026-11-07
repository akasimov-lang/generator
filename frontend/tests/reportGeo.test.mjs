import assert from 'node:assert/strict';
import {test} from 'node:test';
import {reportCountry} from '../src/reportGeo.ts';
test('locale regions take precedence over language and project labels',()=>{
 assert.equal(reportCountry('cs_CZ'),'CZ');assert.equal(reportCountry('da_DK'),'DK');assert.equal(reportCountry('en_CA','#1_project_US'),'CA');
});
test('legacy ambiguous lowercase GEO uses the explicit Fibery country',()=>{
 assert.equal(reportCountry('sl','#700_online casino _SK'),'SK');assert.equal(reportCountry('sl'),'SI');assert.equal(reportCountry('SL','#700_online casino _SK'),'SL');
});
test('language aliases and country aliases retain their different meanings',()=>{
 assert.equal(reportCountry('uk'),'UA');assert.equal(reportCountry('UK'),'GB');assert.equal(reportCountry('da'),'DK');assert.equal(reportCountry('CS'),'CZ');assert.equal(reportCountry('unknown'),null);assert.equal(reportCountry('ZZ'),null);
});
