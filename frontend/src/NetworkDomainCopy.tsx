import React from 'react';

export async function copyNetworkDomain(domain:string) {
  await navigator.clipboard.writeText(domain);
}

export function NetworkDomainCopy({domain,emphasized=false}:{domain:string;emphasized?:boolean}) {
  const [status,setStatus]=React.useState<'idle'|'copied'|'error'>('idle');
  const request=React.useRef(0);
  React.useEffect(()=>{if(status==='idle')return;const timer=window.setTimeout(()=>setStatus('idle'),2400);return()=>window.clearTimeout(timer);},[status]);
  async function copy(){const current=++request.current;try{await copyNetworkDomain(domain);if(request.current===current)setStatus('copied');}catch{if(request.current===current)setStatus('error');}}
  return <span className="networkDomainCopyCell"><button type="button" className={`networkDomainCopy${emphasized?' emphasized':''}`} title="Скопировать домен" aria-label={`Скопировать домен ${domain}`} onClick={()=>void copy()}>{domain}</button><span className={`networkDomainCopyStatus ${status}`} role="status" aria-live="polite">{status==='copied'?'Скопировано':status==='error'?'Не удалось скопировать':''}</span></span>;
}
