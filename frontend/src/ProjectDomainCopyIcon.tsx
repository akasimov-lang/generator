import React from 'react';
import {Check, Copy} from 'lucide-react';
import './styles/project-domain-copy.css';

export function ProjectDomainCopyIcon({domain,copy}:{domain:string;copy:(value:string)=>Promise<void>}) {
  const [status,setStatus]=React.useState<'idle'|'copied'|'error'>('idle');
  React.useEffect(()=>{if(status==='idle')return;const timer=window.setTimeout(()=>setStatus('idle'),2000);return()=>window.clearTimeout(timer);},[status]);
  const message=status==='copied'?'Домен скопирован':status==='error'?'Не удалось скопировать домен':`Скопировать домен ${domain}`;
  async function handleCopy(event:React.MouseEvent<HTMLButtonElement>){event.stopPropagation();try{await copy(domain);setStatus('copied');}catch{setStatus('error');}}
  return <><button type="button" className={`projectDomainCopyIcon ${status}`} aria-label={message} title={message} onClick={event=>void handleCopy(event)}>{status==='copied'?<Check size={16} strokeWidth={1.8} aria-hidden="true"/>:<Copy size={16} strokeWidth={1.6} aria-hidden="true"/>}</button><span className="projectDomainCopyAnnouncement" role="status" aria-live="polite">{status==='idle'?'':message}</span></>;
}
