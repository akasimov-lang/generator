import React from "react";

type SchemaValue = {enabled?:boolean;markup?:string};
export type StructuredDataEvidence = {
 before?:SchemaValue;after?:SchemaValue;planned?:SchemaValue;
 public_verified:boolean;checked_at?:string;
};
const record=(value:unknown):Record<string,unknown>=>value&&typeof value==="object"&&!Array.isArray(value)?value as Record<string,unknown>:{};
const snapshot=(raw:unknown):SchemaValue=>{
 const value=record(raw);
 return {enabled:typeof value.enabled==="boolean"?value.enabled:undefined,markup:typeof value.markup==="string"?value.markup:undefined};
};
export function normalizeStructuredData(raw:unknown):StructuredDataEvidence|undefined {
 if(!raw||typeof raw!=="object"||Array.isArray(raw))return undefined;
 const value=record(raw);
 return {before:snapshot(value.before),after:snapshot(value.after),planned:snapshot(value.planned),
  public_verified:value.public_verified===true,checked_at:typeof value.checked_at==="string"?value.checked_at:undefined};
}
const enabled=(value?:boolean)=>value===true?"Включена":value===false?"Выключена":"Нет подтверждённых данных";
const markup=(value?:string)=>value===undefined?"Нет подтверждённых данных":value===""?"Код не задан":<pre><code>{value}</code></pre>;

export function StructuredDataChanges({value}:{value?:StructuredDataEvidence}) {
 const checked=value?.checked_at&&!Number.isNaN(Date.parse(value.checked_at))
  ?new Date(value.checked_at).toLocaleString("ru-RU",{timeZone:"Europe/Moscow"}):null;
 return <div className="maintenanceStructuredData">
  <div className="maintenanceChangesScroll"><table className="maintenanceChanges"><thead><tr><th>Микроразметка</th><th>До</th><th>После</th></tr></thead><tbody>
   <tr><th scope="row">Настройка Webdev</th><td>{enabled(value?.before?.enabled)}</td><td>{enabled(value?.after?.enabled)}</td></tr>
   <tr><th scope="row">Код JSON-LD</th><td>{markup(value?.before?.markup)}</td><td>{markup(value?.after?.markup)}</td></tr>
  </tbody></table></div>
  <p>{value?.public_verified?"Код проверен на опубликованной странице.":"Проверка кода на опубликованной странице пока не подтверждена."}{checked?` Проверено: ${checked} МСК.`:""}</p>
  {value?.planned?.markup&&value.planned.markup!==value.after?.markup&&<details><summary>Подготовленный код</summary>{markup(value.planned.markup)}</details>}
 </div>;
}
