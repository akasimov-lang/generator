import React from "react";
import "./styles/transfer-confirmation.css";

export type Confirmation = {operation_started_at?:string;started_at?:string;next_check_at?:string|null;interval_seconds?:number;attempt?:number;limit?:number;exhausted?:boolean};
const stages:Record<string,[string,number]>={prepared:["Подготовка",5],transfer_delete:["Извлечение",25],delete_domain:["Извлечение",25],transfer_create:["Добавление",70],create_domains:["Добавление",70],create_subdomains:["Создание поддомена",75],create_fake_main:["Создание внутряка",80],reserve:["Назначение резерва",85],reglue:["Смена Main",90],alternates:["Сохранение альтернейтов",95]};
const duration=(n:number)=>`${Math.floor(n/60)}:${String(n%60).padStart(2,"0")}`;
export function TransferConfirmation({status,phase,data}:{status?:string;phase?:string;data?:Confirmation}) {
 const [now,setNow]=React.useState(Date.now());
 const active=["queued","running","waiting","planned"].includes(status||"");
 React.useEffect(()=>{if(!active)return;const id=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(id);},[active]);
 if(!active)return null;
 const [label,percent]=stages[(phase||"").replace(/^cross_/,"")]||["Подготовка",5];
 const since=Date.parse(data?.started_at||data?.operation_started_at||"");
 const next=Date.parse(data?.next_check_at||"");
 const elapsed=Number.isFinite(since)?Math.max(0,Math.floor((now-since)/1000)):null;
 const remaining=Number.isFinite(next)?Math.max(0,Math.ceil((next-now)/1000)):null;
 return <div className="transferConfirmation" title="Шкала показывает этап операции, а не оставшееся время Webdev.">
  <span>{status==="waiting"?"Ожидаем подтверждения":status==="queued"?"В очереди":label}{elapsed!==null&&` · ${duration(elapsed)}`}</span>
  <progress aria-label={`Перенос: ${label}`} aria-valuetext={`${label}; подтверждение Webdev ещё не получено`} value={percent} max={100}/>
  <small>{data?.exhausted?"Автопроверки завершены — обновите отчёт":remaining!==null?(remaining>0?`Следующая проверка через ${remaining} с` :"Ожидаем результат проверки"):status==="waiting"?"Ожидаем проверку Webdev":"Операция выполняется"}</small>
  {status==="waiting"&&data?.limit&&<small>Проверок: {data.attempt||0}/{data.limit} · интервал {data.interval_seconds||10} с</small>}
 </div>;
}
