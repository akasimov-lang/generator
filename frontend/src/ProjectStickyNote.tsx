import React from "react";
import {createPortal} from "react-dom";
import {Save, X, GripHorizontal} from "lucide-react";
import {NOTE_CHANGED, type NoteApi} from "./projectNoteIndex";
import "./styles/project-sticky-note.css";
type Note = {text:string;revision:string;updated_at?:string|null;updated_by?:string|null};
type Point = {x:number;y:number};
type Size = {width:number;height:number};
const defaultSize:Size={width:350,height:430};
const empty: Note = {text:"",revision:""};
function fitSize(s:Size,p:Point={x:8,y:8}):Size {
  return {width:Math.min(Math.max(260,Number.isFinite(s.width)?s.width:350),Math.max(0,innerWidth-p.x-8)),height:Math.min(Math.max(220,Number.isFinite(s.height)?s.height:430),Math.max(0,innerHeight-p.y-8))};
}
function fit(p:Point,size:Size):Point {return {x:Math.max(8,Math.min(Number.isFinite(p.x)?p.x:8,innerWidth-size.width-8)),y:Math.max(8,Math.min(Number.isFinite(p.y)?p.y:8,innerHeight-size.height-8))};}
function PaperIcon({filled}:{filled:boolean}) {
  return <span className={`stickyPaperIcon ${filled?"isWritten":""}`} aria-hidden="true"><span className="stickyPaperLines"/>{filled&&<span className="stickyPaperPen"/>}</span>;
}
export function ProjectStickyNote({siteId,project,username,api,hasNote}:{siteId:string;project:string;username:string;api:NoteApi;hasNote?:boolean}) {
  const key=`project-note-draft:${username}:${siteId}`, positionKey=`project-note-position:${username}:${siteId}`,sizeKey=`project-note-size:${username}:${siteId}`;
  const [open,setOpen]=React.useState(false),[filled,setFilled]=React.useState(!!hasNote),[version,render]=React.useReducer(n=>n+1,0);
  const [size,setSize]=React.useState<Size>(()=>{try{return fitSize(JSON.parse(localStorage.getItem(sizeKey)||"null")||defaultSize);}catch{return fitSize(defaultSize);}});
  const sizeRef=React.useRef(size);sizeRef.current=size;
  const [position,setPosition]=React.useState<Point>(()=>{try{return fit(JSON.parse(localStorage.getItem(positionKey)||"null")||{x:innerWidth-380,y:120},size);}catch{return fit({x:innerWidth-380,y:120},size);}});
  const sizing=React.useRef<{id:number;x:number;y:number;origin:Size;position:Point}|null>(null);
  const model=React.useRef({text:"",saved:"",revision:"",loaded:false,loading:false,saving:false,error:"",conflict:null as Note|null,storageError:false});
  const alive=React.useRef(true),timer=React.useRef<ReturnType<typeof setTimeout>|null>(null),button=React.useRef<HTMLButtonElement>(null),area=React.useRef<HTMLTextAreaElement>(null);
  const drag=React.useRef<{id:number;x:number;y:number;origin:Point}|null>(null);
  const update=()=>{if(alive.current)render();};
  const announce=(text:string)=>{if(alive.current)setFilled(!!text.trim());window.dispatchEvent(new CustomEvent(NOTE_CHANGED,{detail:{siteId,hasNote:!!text.trim()}}));};
  const stash=()=>{const m=model.current;if(!m.loaded)return;try{if(m.text===m.saved)sessionStorage.removeItem(key);else sessionStorage.setItem(key,JSON.stringify({text:m.text,revision:m.revision}));m.storageError=false;}catch{m.storageError=true;}};
  const save=async()=>{
    const m=model.current;
    if(!m.loaded||m.saving||m.conflict||m.text===m.saved)return;
    const text=m.text,revision=m.revision;m.saving=true;m.error="";stash();update();
    try{
      const result=await api<Note>(`/sites/${siteId}/note`,{method:"PUT",body:JSON.stringify({text,revision})});
      m.saved=result.text;m.revision=result.revision;announce(result.text);stash();
    }catch(e){
      m.error=e instanceof Error?e.message:"Не удалось сохранить заметку.";
      if((e as {statusCode?:number}).statusCode===409){
        try{m.conflict=await api<Note>(`/sites/${siteId}/note`);}catch{m.conflict={...empty,text:"Не удалось загрузить актуальную версию. Повторно откройте проект."};}
      }
    }finally{m.saving=false;update();}
    if(!m.error&&!m.conflict&&m.text!==m.saved)void save();
  };
  const load=async()=>{
    const m=model.current;if(m.loading||m.loaded)return;m.loading=true;m.error="";update();
    try{
      const result=await api<Note>(`/sites/${siteId}/note`);m.saved=result.text;m.revision=result.revision;m.text=result.text;
      try{
        const draft=JSON.parse(sessionStorage.getItem(key)||"null");
        if(draft&&typeof draft.text==="string"&&typeof draft.revision==="string"){
          m.text=draft.text;
          if(draft.text!==result.text&&draft.revision!==result.revision){m.revision=draft.revision;m.conflict=result;m.error="Заметка изменена в другой вкладке. Сравните тексты.";}
        }
      }catch{m.storageError=true;}
      m.loaded=true;announce(result.text);stash();
    }catch(e){m.error=e instanceof Error?e.message:"Не удалось загрузить заметку.";}
    finally{m.loading=false;update();}
    if(!m.conflict)void save();
  };
  React.useEffect(()=>{setFilled(!!hasNote);},[hasNote]);
  React.useEffect(()=>{
    alive.current=true;
    // Workspace icon needs a presence check; table icons receive the batched index.
    if(hasNote===undefined)void load();
    const online=()=>{if(model.current.loaded)void save();else void load();};
    const resize=()=>{const next=fitSize(sizeRef.current);sizeRef.current=next;setSize(next);setPosition(p=>fit(p,next));};
    const leave=(e:BeforeUnloadEvent)=>{if(model.current.text!==model.current.saved){stash();e.preventDefault();e.returnValue="";}};
    window.addEventListener("online",online);window.addEventListener("resize",resize);window.addEventListener("beforeunload",leave);
    return()=>{alive.current=false;if(timer.current)clearTimeout(timer.current);stash();void save();window.removeEventListener("online",online);window.removeEventListener("resize",resize);window.removeEventListener("beforeunload",leave);};
  },[siteId,api,key]);
  React.useEffect(()=>{if(open&&model.current.loaded)area.current?.focus();},[open,model.current.loaded]);
  const close=()=>{if(timer.current)clearTimeout(timer.current);void save();setOpen(false);button.current?.focus();};
  const move=(p:Point)=>{const next=fit(p,sizeRef.current);setPosition(next);try{localStorage.setItem(positionKey,JSON.stringify(next));}catch{/* Position is optional. */}};
  const resizeNote=(value:Size,anchor=position)=>{const next=fitSize(value,anchor);sizeRef.current=next;setSize(next);try{localStorage.setItem(sizeKey,JSON.stringify(next));}catch{/* Size is optional. */}};
  const m=model.current,dirty=m.text!==m.saved;
  const status=m.error?m.error:m.loading?"Загрузка заметки":m.saving?"Сохраняется…":dirty?"Ожидает сохранения":"Сохранено";
  return <><button ref={button} type="button" className="projectStickyTrigger" title={filled?`Заметка проекта ${project} — есть запись`:`Добавить заметку: ${project}`} aria-label={`Заметка проекта ${project}`} aria-expanded={open} onClick={()=>{if(open)close();else{setOpen(true);if(m.loaded&&!m.saving&&!dirty&&!m.conflict)m.loaded=false;void load();}}}><PaperIcon filled={filled}/></button>
    {open&&createPortal(<section className="projectStickyNote" style={{left:position.x,top:position.y,width:size.width,height:size.height}} role="dialog" aria-label={`Заметка: ${project}`} onKeyDown={e=>{if(e.key==="Escape"){e.stopPropagation();close();}}}>
      <header className="projectStickyHeader">
        <div className="projectStickyGrip" role="button" tabIndex={0} aria-label="Переместить заметку: перетащите или используйте клавиши направления" onPointerDown={e=>{if(e.button!==0)return;e.preventDefault();e.currentTarget.focus();e.currentTarget.setPointerCapture(e.pointerId);drag.current={id:e.pointerId,x:e.clientX,y:e.clientY,origin:position};}} onPointerMove={e=>{const d=drag.current;if(d&&d.id===e.pointerId)move({x:d.origin.x+e.clientX-d.x,y:d.origin.y+e.clientY-d.y});}} onPointerUp={()=>{drag.current=null;}} onPointerCancel={()=>{drag.current=null;}} onLostPointerCapture={()=>{drag.current=null;}} onKeyDown={e=>{const d:Record<string,Point>={ArrowLeft:{x:-16,y:0},ArrowRight:{x:16,y:0},ArrowUp:{x:0,y:-16},ArrowDown:{x:0,y:16}};if(d[e.key]){e.preventDefault();move({x:position.x+d[e.key].x,y:position.y+d[e.key].y});}}}><GripHorizontal size={17}/><span title={project}>{project}</span></div>
        <button type="button" className="projectStickyClose" aria-label="Закрыть заметку" onClick={close}><X size={18}/></button>
      </header>
      <textarea ref={area} className="projectStickyText" aria-label={`Текст заметки ${project}`} placeholder="Что важно помнить об этом проекте?" value={m.text} maxLength={20000} disabled={!m.loaded} onChange={e=>{m.text=e.target.value;m.error=m.conflict?m.error:"";stash();update();if(timer.current)clearTimeout(timer.current);timer.current=setTimeout(()=>void save(),650);}}/>
      {m.storageError&&<p className="projectStickyError">Черновик не удалось сохранить в браузере. Дождитесь сохранения на сервере перед закрытием страницы.</p>}
      {m.error&&<div className="projectStickyError" role="alert"><p>{m.error}</p>{m.conflict?<><label>Текст на сервере<textarea readOnly value={m.conflict.text}/></label><div><button type="button" onClick={()=>{const server=m.conflict!;m.text=server.text;m.saved=server.text;m.revision=server.revision;m.conflict=null;m.error="";stash();announce(m.text);update();}}>Оставить серверный</button><button type="button" disabled={!m.conflict.revision} onClick={()=>{m.revision=m.conflict!.revision;m.saved=m.conflict!.text;m.conflict=null;m.error="";stash();void save();}}>Сохранить мой текст</button></div></>:<button type="button" disabled={m.saving||m.loading} onClick={()=>void(m.loaded?save():load())}>Повторить</button>}</div>}
      <footer className="projectStickyFooter"><span className={`projectStickySave ${m.error?"hasError":m.saving||dirty?"isSaving":""}`} role="status" title={status} aria-label={status}><Save size={16}/><span className="projectStickySrOnly">{status}</span></span><small>{m.text.length.toLocaleString("ru-RU")} / 20 000</small></footer>
      <button type="button" className="projectStickyResize" title="Потяните за угол, чтобы изменить размер" aria-label="Изменить размер заметки" onPointerDown={e=>{if(e.button!==0)return;e.preventDefault();e.currentTarget.focus();e.currentTarget.setPointerCapture(e.pointerId);sizing.current={id:e.pointerId,x:e.clientX,y:e.clientY,origin:sizeRef.current,position};}} onPointerMove={e=>{const d=sizing.current;if(d&&d.id===e.pointerId)resizeNote({width:d.origin.width+e.clientX-d.x,height:d.origin.height+e.clientY-d.y},d.position);}} onPointerUp={()=>{sizing.current=null;}} onPointerCancel={()=>{sizing.current=null;}} onLostPointerCapture={()=>{sizing.current=null;}} onKeyDown={e=>{const changes:Record<string,Size>={ArrowLeft:{width:-16,height:0},ArrowRight:{width:16,height:0},ArrowUp:{width:0,height:-16},ArrowDown:{width:0,height:16}};if(changes[e.key]){e.preventDefault();resizeNote({width:size.width+changes[e.key].width,height:size.height+changes[e.key].height});}}}><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 12 12 4M9 12l3-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg></button>
    </section>,document.body)}
  </>;
}
