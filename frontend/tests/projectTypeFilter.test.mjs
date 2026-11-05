import assert from 'node:assert/strict';
import {test} from 'node:test';
import {projectType,projectTypeFilter,matchesProjectType} from '../src/projectTypeFilter.ts';
test('explicit project type takes precedence over brand',()=>{
 assert.equal(projectType({site_type:'general',brand:'Example'}),'general');
 assert.equal(projectType({site_type:'monobrand',brand:''}),'monobrand');
});
test('legacy projects are classified by their brand',()=>{
 assert.equal(projectType({brand:' Example '}),'monobrand');
 assert.equal(projectType({brand:' Общие Ключи '}),'general');
 assert.equal(projectType({brand:null}),'general');
});
test('type filters narrow the already selected domain category',()=>{
 const dropProjects=[{id:'a',brand:'Example'},{id:'b',brand:'Общие ключи'}];
 assert.deepEqual(dropProjects.filter(site=>matchesProjectType(site,'monobrand')).map(site=>site.id),['a']);
 assert.deepEqual(dropProjects.filter(site=>matchesProjectType(site,'general')).map(site=>site.id),['b']);
 assert.equal(dropProjects.filter(site=>matchesProjectType(site,null)).length,2);
});
test('return URL restores valid type filters and ignores unknown values',()=>{
 assert.equal(projectTypeFilter('?domainFilter=drops&projectType=monobrand'),'monobrand');
 assert.equal(projectTypeFilter('?projectType=general'),'general');
 assert.equal(projectTypeFilter('?projectType=invalid'),null);
});
