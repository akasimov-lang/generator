import React from "react";
import { titleRewriteLabel, type TitleRewriteMode } from "./titleRewriteModes";

export type DistributionKey = "subdomains"|"without_alternates"|"redirects"|"title_h1"|"paragraphs"|"internal_pages";
export type Distribution = {total:number;counts:Record<DistributionKey,number>;baseline:number;emergency_subdomains:number;heading_modes?:Record<string,number>;target_kinds?:Record<string,number>};
const settings: {key:DistributionKey;label:string;selected:string;remainder:string}[] = [
 {key:"subdomains",label:"Поддомены",selected:"Main становится поддоменом",remainder:"Main — корневой домен новорега или дропа"},
 {key:"without_alternates",label:"Без альтернейтов",selected:"Альтернейты выключены или отсутствуют",remainder:"Альтернейты включены и заданы"},
 {key:"redirects",label:"301",selected:"Новый 301 со старого Main на новый",remainder:"Новый 301 со старого Main не добавляется"},
 {key:"title_h1",label:"Title/H1",selected:"Обновление Title и H1",remainder:"Title и H1 не переписываются"},
 {key:"paragraphs",label:"Абзацы",selected:"Переписываются все поддерживаемые абзацы главной страницы с сохранением смысла, фактов и ссылок",remainder:"Абзацы главной страницы не переписываются"},
 {key:"internal_pages",label:"Внутренние страницы",selected:"3–6 пунктов меню в один уровень, генерация и автопубликация текстов для одностраничных монобрендов",remainder:"Новые пункты меню и страницы не создаются"},
];
const valid=(value:string)=>/^\d+$/.test(value)&&Number(value)<=100;
const amount=(count:number,total:number)=>`${count} (${total?(count*100/total).toLocaleString("ru-RU",{maximumFractionDigits:1}):"0"}%)`;

export function PilotDistribution({entered,saved,data,changed=false,titleMode="minimal",savedTitleMode,planningMode="percentages"}:{
 entered:Record<DistributionKey,string>;saved?:Record<DistributionKey,number>;data?:Distribution;changed?:boolean;titleMode?:TitleRewriteMode;savedTitleMode?:TitleRewriteMode;planningMode?:"percentages"|"mixed";
}){
 return <details className="pilotDistribution">
  <summary>Куда распределяются проценты и остаток</summary>
  <p>Каждый процент считается отдельно от общего числа планируемых переклеев. Один проект может одновременно получить несколько настроек. Проценты не складываются: общего остатка до 100% нет.</p>
  {changed&&<p role="status">Введённые значения ещё не применены. Нажмите «Обновить план». Фактические количества ниже относятся к сохранённому плану.</p>}
  <p>Режим заголовков: {titleRewriteLabel(titleMode)}. Для выбранной доли проектов меняются Title и соответствующие заголовки содержимого главной страницы. Description сохраняется.{data&&savedTitleMode!==titleMode&&<> В сохранённом плане: {titleRewriteLabel(savedTitleMode||"minimal")}.</>}</p>
  {titleMode==="mixed"&&<p>Этот режим не меняет способы переклея. Три способа переписывания распределяются поровну среди выбранных проектов, с разницей не более одного при совместимости всех страниц. Нередактируемые заголовки ограничивают распределение.</p>}
  {data?.heading_modes&&<p>Заголовки в сохранённом плане: точечно — {data.heading_modes.minimal||0}; полностью Title/H1 — {data.heading_modes.full_h1||0}; полностью Title/H1–H6 — {data.heading_modes.full_all||0}.</p>}
  {data?.target_kinds&&<p>Main в сохранённом плане: новорег — {data.target_kinds.newreg||0}; дроп — {data.target_kinds.drop||0}; поддомен новорега — {data.target_kinds.sub_newreg||0}; поддомен дропа — {data.target_kinds.sub_drop||0}.</p>}
  {planningMode==="mixed"&&<p>В смешанном режиме доля без альтернейтов считается только среди совместимых корневых новорегов. Поддомены сохраняют родительский домен в x-default. Проекты, уже переклеенные на текущей неделе, исключены из распределения.</p>}
  <div className="pilotDistributionScroll"><table>
   <thead><tr><th>Настройка</th><th>Введено</th><th>Сохранённый план</th><th>{data?"Остальные проекты в плане":"Цель для остальных проектов"}</th></tr></thead>
   <tbody>{settings.map(setting=><tr key={setting.key}>
    <td><strong>{setting.label}</strong><small>{setting.key==="title_h1"?titleRewriteLabel(data?(savedTitleMode||"minimal"):titleMode):setting.selected}</small></td>
    <td>{valid(entered[setting.key])?`${entered[setting.key]}%`:"—"}</td>
    <td>{data?<><strong>{amount(data.counts[setting.key]??0,data.total)}</strong>{saved&&<small>Цель: {saved[setting.key]??0}%{planningMode==="mixed"&&setting.key==="without_alternates"?" совместимых новорегов":""}</small>}</>:"После планирования"}</td>
    <td><strong>{data?amount(data.total-(data.counts[setting.key]??0),data.total):valid(entered[setting.key])?`${100-Number(entered[setting.key])}%`:"—"}</strong><small>{setting.remainder}</small></td>
   </tr>)}</tbody>
  </table></div>
  {data&&<p>Без всех дополнительных опций одновременно: <strong>{amount(data.baseline,data.total)}</strong> — корневой Main, с альтернейтами, без нового 301, без обновления Title/H1 и абзацев, без создания внутренних страниц. Это пересечение условий, а не сумма остатков.</p>}
  <p>{data?"Canonical распределяется отдельно; его фактические варианты показаны выше.":"Canonical распределяется отдельно при планировании."} Схема альтернейтов выбирается из совместимых вариантов с учётом истории проекта.</p>
  <p>Внутренние страницы создаются только у подтверждённых одностраничных монобрендов. Процент считается от всех проектов плана; если подходящих сайтов меньше, фактическое количество будет ниже.</p>
  <p>Остаток по 301 не означает удаление ранее настроенных редиректов. Доли округляются до целых проектов; доступность доменов, совместимость схем и возможность редактировать H1 могут ограничить распределение.</p>
  <p>Для сеток без резервов разрешён поддомен сверх заданной доли{data?`: в плане ${data.emergency_subdomains} таких исключений`:""}.</p>
 </details>;
}
