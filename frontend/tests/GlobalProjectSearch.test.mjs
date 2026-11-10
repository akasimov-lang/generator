import assert from "node:assert/strict";
import {after,test} from "node:test";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {createServer} from "vite";

const server=await createServer({configFile:false,root:new URL("..",import.meta.url).pathname,server:{middlewareMode:true,hmr:false},optimizeDeps:{noDiscovery:true,include:[]},appType:"custom"});
after(()=>server.close());
const {GlobalProjectSearchInput,GlobalProjectSearchResults,matchingGlobalProjects}=await server.ssrLoadModule("/src/GlobalProjectSearch.tsx");
const snapshot=Object.freeze([
 Object.freeze({id:"pl",name:"brand-pl.test",brand:"Lemon",cache_geo:"PL",cache_canon:"main-pl.test",cache_domains:Object.freeze(["shared-domain.test"]),project_status:"mass_actions"}),
 Object.freeze({id:"cz",name:"brand-cz.test",brand:"BetOnRed",cache_geo:"CZ",cache_canon:"shared-domain.test",cache_domains:Object.freeze(["xn--80ae9b7b.xn--p1ai"]),project_status:"working",is_active:false}),
 Object.freeze({id:"base",name:"editorial.test",base_url:"https://www.source.test/",fibery_name:"#2026 Reference Project",cache_domains:Object.freeze([]),project_status:"hands_only"}),
]);
const render=props=>renderToStaticMarkup(React.createElement(GlobalProjectSearchResults,{sites:snapshot,query:"",onOpen:()=>{},...props}));

test("search uses the complete permitted snapshot across GEO, brands and project statuses without mutating it",()=>{
 const ids=matchingGlobalProjects(snapshot,"https://SHARED-DOMAIN.test/path?q=x").map(site=>site.id);
 assert.deepEqual(ids,["pl","cz"]);
 assert.equal(snapshot[0].project_status,"mass_actions");assert.equal(snapshot[1].is_active,false);
 assert.deepEqual(matchingGlobalProjects(snapshot.slice(0,1),"авсэ"),[]);
});

test("network aliases, Main, base URL and project names remain searchable with IDN and pasted URLs",()=>{
 assert.deepEqual(matchingGlobalProjects(snapshot,"АВСЭ.рф").map(site=>site.id),["cz"]);
 assert.deepEqual(matchingGlobalProjects(snapshot,"https://main-pl.test/page/").map(site=>site.id),["pl"]);
 assert.deepEqual(matchingGlobalProjects(snapshot,"www.source.test").map(site=>site.id),["base"]);
 assert.deepEqual(matchingGlobalProjects(snapshot,"#2026 reference").map(site=>site.id),["base"]);
 assert.deepEqual(matchingGlobalProjects(snapshot,"brand-cz").map(site=>site.id),["cz"]);
});

test("exact network matches precede broader text matches without changing source order",()=>{
 const sites=[{id:"partial",name:"other.test",cache_domains:["sub.example.test"]},{id:"exact",name:"example.test",cache_domains:[]}];
 assert.deepEqual(matchingGlobalProjects(sites,"example.test").map(site=>site.id),["exact","partial"]);
 assert.deepEqual(sites.map(site=>site.id),["partial","exact"]);
});

test("finds Fibery project numbers with or without a hash",()=>{
 const sites=[{id:"fibery",name:"casino.test",fibery_name:"#698_Casino_PL"},{id:"empty",name:"empty.test",fibery_name:null}];
 assert.deepEqual(matchingGlobalProjects(sites,"698").map(site=>site.id),["fibery"]);
 assert.deepEqual(matchingGlobalProjects(sites," #698 ").map(site=>site.id),["fibery"]);
 assert.deepEqual(matchingGlobalProjects(sites.slice(1),"698"),[]);
});

test("finds a partial Fibery name regardless of case and handles missing names",()=>{
 const sites=[{id:"fibery",name:"casino.test",fibery_name:"#698_Казино Польша_PL"},{id:"empty",name:"empty.test"}];
 assert.deepEqual(matchingGlobalProjects(sites,"казино ПОЛЬША").map(site=>site.id),["fibery"]);
 assert.deepEqual(matchingGlobalProjects(sites,"empty.test").map(site=>site.id),["empty"]);
});

test("results are navigation links with brand/GEO context and no mass action controls",()=>{
 const html=render({query:"shared-domain.test"});
 assert.match(html,/Результаты поиска · 2/);assert.match(html,/href="\/project-network\/brand-cz.test\/"/);
 assert.match(html,/BetOnRed/);assert.match(html,/🇨🇿/);assert.match(html,/Main/);
 assert.doesNotMatch(html,/type="checkbox"|Переклеить|Сохранить|Удалить/);
 assert.equal(render({query:"  "}),"");
 assert.match(render({query:"missing.test"}),/Проекты не найдены/);
});

test("broad results are paginated instead of mounting every site row",()=>{
 const sites=Array.from({length:125},(_,i)=>({id:String(i),name:`example-${i}.test`}));
 const html=render({sites,query:"example"});
 assert.equal((html.match(/href="\/project-network\//g)||[]).length,50);
 assert.match(html,/Результаты поиска · 125/);assert.match(html,/1–50 из 125/);
 assert.match(html,/Страницы результатов поиска/);
});

test("header input exposes the search scope, associated results and explicit clearing",()=>{
 const html=renderToStaticMarkup(React.createElement(GlobalProjectSearchInput,{query:"brand.test",onChange:()=>{}}));
 assert.match(html,/type="search"/);assert.match(html,/aria-controls="mass-global-search-results"/);
 assert.match(html,/Поиск по всем сайтам/);assert.match(html,/Домен, имя или № Fibery/);
 assert.match(html,/Очистить поиск по всем сайтам/);
});
