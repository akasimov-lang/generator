import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const server=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,server:{middlewareMode:true,hmr:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
after(()=>server.close());
const {LastReglueSummary}=await server.ssrLoadModule('/src/LastReglueSummary.tsx');
const render=props=>renderToStaticMarkup(React.createElement(LastReglueSummary,props));
const last={at:'2026-10-30T12:47:32Z',old_main:'mostbetuz1.atticrestaurant.com',new_main:'atticrestaurant.com',old_path:'/uz/',new_path:'/uz/'};
test('confirmed change shows Moscow time and complete historical scheme for tooltip and keyboard focus',()=>{
 const html=render({last});
 assert.match(html,/30.10.2026, 15:47:32 МСК/);
 assert.match(html,/mostbetuz1.atticrestaurant.com → atticrestaurant.com/);
 assert.match(html,/Внутряк: \/uz\/ → \/uz\//);
 assert.match(html,/tabindex="0"/);assert.match(html,/title=/);
});
test('newer externally observed change never displays an outdated local scheme as the last change',()=>{
 const html=render({last,observedAt:'2026-10-30T13:00:00Z'});
 assert.match(html,/Смена Main обнаружена.*16:00:00 МСК/);
 assert.doesNotMatch(html,/mostbetuz1|Внутряк/);
 assert.equal(render({observedAt:'invalid'}),'');
});

test('recent fake-path replacements show before and after with Moscow time and a twenty-entry limit',()=>{
 const recent=Array.from({length:25},(_,i)=>({id:String(i),kind:'fake_path',at:`2026-11-05T09:${String(i).padStart(2,"0")}:00Z`,old_main:'main.test',new_main:'main.test',old_path:'/old/',new_path:'/new-'+i}));
 const html=render({last,recent});
 assert.equal((html.match(/<article/g)||[]).length,20);
 assert.match(html,/Замена внутряка: 05.11.2026, 12:24:00 МСК/);
 assert.match(html,/Внутряк: \/old\/ → \/new-24/);
 assert.doesNotMatch(html,/new-0(?:<|\s)|new-1(?:<|\s)|Последний переклей/);
 assert.ok(html.indexOf('new-24')<html.indexOf('new-7'));
});

test('recent history preserves a newer externally observed Main change without inventing its addresses',()=>{
 const html=render({last,recent:[{...last,id:'confirmed',kind:'reglue'}],observedAt:'2026-10-30T13:00:00Z'});
 assert.match(html,/Смена Main обнаружена: 30.10.2026, 16:00:00 МСК/);
 assert.ok(html.indexOf('Смена Main обнаружена')<html.indexOf('Переклей:'));
 assert.equal((html.match(/Внутряк:/g)||[]).length,1);
});

test('cache observations are explicitly labelled and keep old and new paths',()=>{
 const html=render({recent:[{id:'cache',source:'cache',comparison:'last_recorded',kind:'fake_path',at:'2026-11-06T09:00:00Z',old_main:'main.test',new_main:'main.test',old_path:'/dragonia-casino/',new_path:'/risorse%20per%20le%20scuole/'}]});
 assert.match(html,/Кеш · обнаружено/);
 assert.match(html,/Время обнаружения изменения при синхронизации/);
 assert.match(html,/последней записью истории/);
 assert.match(html,/\/dragonia-casino\/ → \/risorse%20per%20le%20scuole\//);
});

test('detailed cached Main change replaces the legacy observation placeholder',()=>{
 const html=render({last,observedAt:'2026-11-06T09:00:00Z',recent:[{id:'cache',source:'cache',kind:'reglue',at:'2026-11-06T09:00:00Z',old_main:'old.test',new_main:'new.test',old_path:'/old/',new_path:'/new/'}]});
 assert.equal((html.match(/<article/g)||[]).length,1);
 assert.match(html,/old.test → new.test/);
 assert.doesNotMatch(html,/Смена Main обнаружена/);
});

test('confirmed alternate update shares the sidebar history with timestamp and saved markup',()=>{
 const html=render({recent:[{id:'alts',kind:'alternates',at:'2026-11-09T11:48:00Z',initiator:'anton',old_main:null,new_main:null,old_path:null,new_path:null,alternates_before:{markup:'<link rel="alternate" hreflang="pl" href="https://old.test/" />',enabled:true},alternates_after:{markup:'<link rel="alternate" hreflang="pl" href="https://new.test/" />',enabled:false}}]});
 assert.match(html,/Обновление альтернейтов: 09.11.2026, 14:48:00 МСК/);
 assert.match(html,/Подтверждено · anton/);assert.match(html,/Включены → Выключены/);
 assert.match(html,/<summary>Разметка до и после<\/summary>/);
 assert.match(html,/https:\/\/old.test/);assert.match(html,/https:\/\/new.test/);
 assert.match(html,/&lt;link/);assert.doesNotMatch(html,/<link rel="alternate"|Внутряк:|Переклей:/);
});

test('legacy alternate history distinguishes an unknown baseline from empty markup',()=>{
 const html=render({recent:[{id:'legacy',kind:'alternates',at:'2026-11-09T11:48:00Z',old_main:null,new_main:null,old_path:null,new_path:null,alternates_before:null,alternates_after:{markup:'',enabled:false}}]});
 assert.match(html,/Нет исходных данных → Выключены/);
 assert.match(html,/Исходная разметка не сохранена/);assert.match(html,/Разметка пустая/);
});

test('alternate changes sort with Main and fake-page events without replacing their labels',()=>{
 const html=render({recent:[{...last,id:'main',kind:'reglue'},{...last,id:'path',kind:'fake_path',at:'2026-10-30T13:00:00Z'},{...last,id:'alts',kind:'alternates',at:'2026-10-30T14:00:00Z',alternates_after:{markup:'',enabled:false}}]});
 assert.ok(html.indexOf('Обновление альтернейтов')<html.indexOf('Замена внутряка'));
 assert.ok(html.indexOf('Замена внутряка')<html.indexOf('Переклей:'));
 assert.equal((html.match(/Внутряк:/g)||[]).length,2);
});
