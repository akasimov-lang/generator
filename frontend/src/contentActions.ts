import type { MassActionFilter } from "./massActionScope";

export type ContentAction = "meta_headings" | "paragraphs" | "trim_50" | "trim_99";
export type HeadingAction = "meta_headings" | "full_title_h1" | "full_title_headings";
export const contentLabels: Record<ContentAction, string> = {
 meta_headings: "Переписать мета и заголовки", paragraphs: "Переписать абзацы",
 trim_50: "Обрезать 50% контента", trim_99: "Обрезать 99% контента",
};
export const headingActionOptions: {value:HeadingAction;label:string;keywords:string}[] = [
 {value:"meta_headings",label:"Title, Description и заголовки",keywords:"мета описание h1 h2 h3"},
 {value:"full_title_h1",label:"Полностью: Title и H1",keywords:"тайтл главный заголовок"},
 {value:"full_title_headings",label:"Полностью: Title и все заголовки H1–H6",keywords:"тайтл h2 h3 h4 h5 h6"},
];
export function contentActionDescription(action:ContentAction,heading:HeadingAction="meta_headings"):string {
 if(action==="paragraphs")return "Переписываем абзацы по общим правилам рерайта и базе знаний бренда и GEO, с проверкой смысла и фактов. Возможны преобразования списков и таблиц. Title, Description и заголовки сохраняются; для них выберите «Переписать мета и заголовки».";
 if(action==="trim_50")return "Остаются H1 и примерно половина основных абзацев. Это сокращение по числу абзацев, а не точные 50% слов; рерайт не выполняется.";
 if(action==="trim_99")return "Остаются H1 и один абзац. Фактический процент сокращения зависит от исходного текста; рерайт не выполняется.";
 return heading==="full_title_h1"?"Полностью переписываем Title и H1. Остальные заголовки, Description и основной текст сохраняются.":heading==="full_title_headings"?"Полностью переписываем Title и все заголовки H1–H6. Description и основной текст сохраняются.":"Переписываем Title, Description и заголовки, сохраняя смысл, факты и язык страницы. Основной текст сохраняется.";
}
export const contentPending=(status?:string)=>status==="queued"||status==="generating";

export function contentBatchPayload(action:ContentAction,heading:HeadingAction,filter:MassActionFilter|null,selected:string[],provider:string) {
 if(!filter)throw new Error("Выберите бренд и GEO.");
 const site_ids=[...new Set(selected)];
 if(!site_ids.length||site_ids.length>100)throw new Error("Выберите от 1 до 100 проектов.");
 const trimming=action.startsWith("trim_");
 if(!trimming&&!provider)throw new Error("Выберите провайдера для обработки.");
 return {filter,action:action==="meta_headings"?heading:action,site_ids,provider_id:trimming?null:provider};
}
