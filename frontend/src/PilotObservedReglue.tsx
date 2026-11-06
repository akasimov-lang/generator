import React from "react";

export type ObservedReglue={operation_id:string;at:string;before:{main:string;fake_path?:string|null};after:{main:string;fake_path?:string|null};planned_main?:string};

export function PilotObservedReglue({value}:{value:ObservedReglue}) {
 const at=new Intl.DateTimeFormat("ru-RU",{timeZone:"Europe/Moscow",dateStyle:"short",timeStyle:"medium"}).format(new Date(value.at));
 return <div className="pilotObservedReglue" aria-label="Подтверждённый результат переклея">
  <small><strong>Выполнено вне этого плана</strong></small>
  <small>До: {value.before.main}</small><small>После: {value.after.main}</small>
  {(value.before.fake_path!=null||value.after.fake_path!=null)&&<small>Внутренняя страница: {value.before.fake_path??"Не зафиксирована"} → {value.after.fake_path??"Не зафиксирована"}</small>}
  <small>{at} МСК</small>
 </div>;
}
