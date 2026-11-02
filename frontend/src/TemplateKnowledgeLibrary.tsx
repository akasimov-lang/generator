import React from "react";
import { Upload, Loader2 } from "lucide-react";
import { TemplateCombobox } from "./TemplateCombobox";
import { TEMPLATE_GEOS } from "./templateLocaleOptions";
import { isGeneralBrand, templateBrandOptions, type KnowledgeScope, type TemplateProject } from "./templateBrandOptions";
type Api = <T>(path:string, options?:RequestInit) => Promise<T>;
type Structure = {status?:string; pages?:{url:string;title:string;path:string;status?:string;headings?:{level:string;text:string}[]}[];errors?:{url:string;message:string}[];error?:string};
type Example = {id:string;title:string;filename:string;url:string;structure?:Structure};
type Library = {count:number;sources:Example[];scopes:KnowledgeScope[]};
export function TemplateKnowledgeLibrary({api,projects,onScopesChanged,onSaved}:{api:Api;projects:TemplateProject[];onScopesChanged:(scopes:KnowledgeScope[])=>void;onSaved?:()=>Promise<void>}) {
  const [brand,setBrand]=React.useState("");const [geo,setGeo]=React.useState("PL");
  const [data,setData]=React.useState<Library>({count:0,sources:[],scopes:[]});
  const [files,setFiles]=React.useState<File[]>([]);const [html,setHtml]=React.useState("");const [url,setUrl]=React.useState("");
  const [busy,setBusy]=React.useState(false);const [loading,setLoading]=React.useState(false);const [error,setError]=React.useState("");const [message,setMessage]=React.useState("");
  const input=React.useRef<HTMLInputElement>(null);const sequence=React.useRef(0);
  const general=isGeneralBrand(brand);const options=templateBrandOptions(projects,data.scopes,geo);
  const load=React.useCallback(async()=>{const seq=++sequence.current;setLoading(true);try{const next=await api<Library>(`/site-templates/knowledge${brand?`?${new URLSearchParams({brand,geo})}`:""}`,{cache:"no-store"});if(!Array.isArray(next.sources)||!Array.isArray(next.scopes))throw new Error("Не удалось прочитать базу знаний.");if(seq===sequence.current){setData(next);onScopesChanged(next.scopes);setError("");}}catch(e){if(seq===sequence.current)setError(e instanceof Error?e.message:"Не удалось загрузить базу знаний.");}finally{if(seq===sequence.current)setLoading(false);}},[api,brand,geo,onScopesChanged]);
  React.useEffect(()=>{setData(current=>({...current,count:0,sources:[]}));void load();return()=>{sequence.current++;};},[load]);
  const parsing=data.sources.some(s=>["queued","running"].includes(s.structure?.status||""));
  React.useEffect(()=>{if(!parsing)return;const timer=setInterval(()=>void load(),4000);return()=>clearInterval(timer);},[parsing,load]);
  async function upload(event:React.FormEvent){
    event.preventDefault();if(!brand||(!general&&!geo)||busy)return;
    setBusy(true);setError("");setMessage("");const failures:string[]=[];let saved=0,duplicates=0;
    const uploads=[...files.map(file=>({name:file.name,file})),...(html.trim()?[{name:"Вставленный пример.txt",file:null}]:[])];
    for(const item of uploads){try{
      if(item.file&&(!/\.(html?|txt|docx?)$/i.test(item.name)||item.file.size>2_000_000))throw new Error("Выберите HTML, TXT, DOC или DOCX до 2 МБ.");
      const ext=item.name.split('.').pop()?.toLowerCase();
      const content=!item.file?html:ext==='doc'||ext==='docx'?(await api<{html:string}>(`/site-templates/source-document?extension=${ext}`,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:item.file})).html:await item.file.text();
      const next=await api<Library&{source:{duplicate:boolean}}>('/site-templates/knowledge',{method:'POST',body:JSON.stringify({brand,geo:general?'':geo,html:content,url,filename:item.name})});
      setData(next);onScopesChanged(next.scopes);if(next.source.duplicate)duplicates++;else saved++;
    }catch(e){failures.push(`${item.name}: ${e instanceof Error?e.message:'Не удалось загрузить.'}`);}}
    if(!failures.length){setFiles([]);setHtml("");if(input.current)input.current.value="";}
    setMessage(`Загружено: ${saved}${duplicates?` · Уже в базе: ${duplicates}`:""}`);setError(failures.join('\n'));setBusy(false);
    if(saved)await onSaved?.();
  }
  return <section className="tg-card tg-knowledge" aria-label="База знаний конкурентов"><div className="tg-knowledge-heading"><div><h3>Примеры конкурентов</h3><p>Сохраняйте примеры для следующих шаблонов. Они подключаются автоматически.</p></div><span className="tg-knowledge-count" role="status" aria-live="polite">{brand?loading?"Обновляем…":`В базе: ${data.count}`:"Выберите бренд"}</span></div>
    <form onSubmit={event=>void upload(event)}><fieldset disabled={busy}><div className="tg-knowledge-fields">
      {general?<div className="tg-knowledge-all-geo"><strong>Все GEO</strong><small>Общая база для общих ключей</small></div>:<TemplateCombobox label="ГЕО базы знаний" value={geo} options={TEMPLATE_GEOS} onChange={value=>{setGeo(value);setBrand("");setMessage("");}}/>}
      <TemplateCombobox label="Бренд базы знаний" value={brand} options={options} allowCustom placeholder="Выберите бренд" onChange={value=>{setBrand(value);setMessage("");}}/>
      <label>URL главной страницы{general?" *":""}<input type="url" aria-label="URL примера конкурента" required={general} value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://example.com/"/></label>
    </div><div className="tg-knowledge-upload"><label className="button secondary"><Upload size={15}/>{general?"Загрузить главную":"Выбрать примеры"}<input ref={input} type="file" aria-label="Файлы примеров конкурентов" accept=".html,.htm,.txt,.doc,.docx" multiple={!general} onChange={e=>setFiles(Array.from(e.target.files||[]))}/></label><small>{files.length?files.map(f=>f.name).join(', '):'HTML, TXT, DOC, DOCX · до 2 МБ на пример'}</small><button type="submit" className="button primary" disabled={busy||!brand||(!files.length&&!html.trim())}>{busy&&<Loader2 size={15} className="tg-spin"/>}{busy?"Загружаем…":"Сохранить в базу знаний"}</button></div>
    <details className="tg-knowledge-paste"><summary>Вставить HTML или текст</summary><textarea aria-label="Текст примера конкурента" rows={4} value={html} onChange={e=>setHtml(e.target.value)} placeholder="Главная страница конкурента…"/></details>
    {general&&<p className="tg-help">Загрузите только главную страницу и укажите её домен. Внутренние страницы и структуру сайта парсер соберёт автоматически.</p>}
    </fieldset></form>{message&&<p role="status">{message}</p>}{error&&<p role="alert" className="tg-knowledge-error">{error}</p>}
    {!!data.sources.length&&<details className="tg-knowledge-examples"><summary>Загруженные примеры · {data.count}</summary>{data.sources.map(source=><article key={source.id}><strong>{source.title||source.filename}</strong><small>{source.filename} {source.url&&<a href={source.url} target="_blank" rel="noopener noreferrer">{source.url}</a>}</small>{source.structure?.status&&<span>{source.structure.status==='completed'?`Структура: ${source.structure.pages?.length||0} страниц`:source.structure.status==='failed'?'Не удалось собрать структуру':'Собираем структуру…'}</span>}{source.structure?.error&&<small>{source.structure.error}</small>}{!!source.structure?.pages?.length&&<details><summary>Структура сайта</summary><ul>{source.structure.pages.map(page=><li key={page.url}><a href={page.url} target="_blank" rel="noopener noreferrer">{page.path}</a> · {page.title||'Без заголовка'}{page.status==='unavailable'&&' · Недоступна'}</li>)}</ul></details>}</article>)}</details>}
  </section>;
}
