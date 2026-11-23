import React from 'react';
import { createRoot } from 'react-dom/client';
import { DomainRedirects } from '../src/DomainRedirects';
import { ReglueRedirectPolicy } from '../src/ReglueRedirectPolicy';
import { NetworkEditQueue } from '../src/networkEditQueue';
import '../src/styles/global.css';
window.calls=[];window.rows=[{url:'naukaprogramowania.pl',value:'katechezatarnow.pl'}];window.items=[];window.policy=false;window.failPolicy=false;window.hang=false;
const snapshot=()=>({items:structuredClone(window.items),limit:30,network:null});
async function api(path, options={}) {
 if(path.endsWith('/redirect-policy')) {
  if(options.method==='PATCH') {if(window.failPolicy)throw Error('Ошибка сохранения настройки');window.policy=JSON.parse(options.body).enabled;}
  return {site_id:'site',enabled:window.policy};
 }
 if(options.method==='POST') {
  const body=JSON.parse(options.body);window.calls.push(body);
  window.items=window.items.filter(i=>i.id!==body.request_id);
  window.items.unshift({id:body.request_id,request:body,status:'waiting',message:'В очереди. Ожидает предыдущее изменение…',created_at:new Date().toISOString()});
  if(window.hang)return new Promise(()=>{});
 }
 return snapshot();
}
const queue=new NetworkEditQueue('site',api,100);window.queue=queue;
window.phase=async(status,message)=>{
 const item=window.items[0];item.status=status;item.message=message;
 if(status==='completed')window.rows=[{url:item.request.redirect_source,value:item.request.redirect_target}];
 await queue.refresh();
};
function Harness(){
 const [,render]=React.useReducer(n=>n+1,0);
 React.useEffect(()=>queue.subscribe(render),[]);
 const [busy,setBusy]=React.useState(false);
 return <main style={{padding:20,maxWidth:1100}}><ReglueRedirectPolicy siteId='site' api={api} onBusyChange={setBusy}/><button disabled={busy}>Тест переклея</button><DomainRedirects redirects={window.rows} revision='r' available disabled={false} canon='katechezatarnow.pl' queue={queue} onSave={async request=>queue.enqueue({...request,action:'domain_redirect',revision:'r'})} onRetargetMain={async()=>false}/></main>;
}
createRoot(document.getElementById('root')).render(<Harness/>);
