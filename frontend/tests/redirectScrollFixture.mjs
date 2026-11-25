// Run from frontend with Node (no browser): node tests/redirectScrollFixture.mjs [output.json]
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import {readFile,writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
const server=await createServer({configFile:false,root:process.cwd(),server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true,include:[]},appType:'custom'});
try{
  globalThis.location={pathname:'/project-network/main.test/'};
  const {RedirectWorkspace}=await server.ssrLoadModule('/src/RedirectWorkspace.tsx');
  const {PageRedirectWorkspace}=await server.ssrLoadModule('/src/PageRedirectWorkspace.tsx');
  const base={canon:'main.test',revision:'one',available:true,disabled:false,onSave:async()=>true};
  const redirects=Array.from({length:50},(_,i)=>({url:`source-${i}.test`,value:'main.test'}));
  const domains=redirects.map(r=>r.url);
  const domain=renderToStaticMarkup(React.createElement(RedirectWorkspace,{...base,redirects,domains,onRetargetMain:async()=>true}));
  const groups=[{domain:'main.test',redirects:Array.from({length:46},(_,i)=>({url:`/page-${i}/`,value:'https://main.test/new/'}))}];
  const pages=renderToStaticMarkup(React.createElement(PageRedirectWorkspace,{...base,groups,domains}));
  const common=(await Promise.all(['src/styles/global.css','src/styles/template-generator.css','src/styles/save-indicator.css'].map(p=>readFile(p,'utf8')))).join('\n');
  const original=execFileSync('git',['show','4734ce5:frontend/src/styles/domain-redirects.css'],{encoding:'utf8'});
  const patched=await readFile('src/styles/domain-redirects.css','utf8');
  const html=css=>`<!doctype html><html><head><meta charset="utf-8"><style>${common}\n${css}</style></head><body><main style="padding:20px;min-width:0"><div class="dataPanel projectNetworkPanel"><div class="dataPanelBody"><div class="networkWithNavigation networkWorkspace"><div class="networkMembership">${domain}${pages}</div><aside>Сетки бренда</aside></div></div></div></main></body></html>`;
  await writeFile(process.argv[2]||'/tmp/pagepilot-scroll-fixture.json',JSON.stringify({before:html(original),after:html(patched)}));
}finally{await server.close();}
