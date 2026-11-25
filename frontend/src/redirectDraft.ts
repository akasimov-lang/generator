export type DraftRedirect={url:string;value:string};
export type RedirectDraftRow=DraftRedirect & {id:string;original:string;removed?:boolean;expected: {rows:DraftRedirect[]}};
export type RedirectDraftDocument={version:1;rows:RedirectDraftRow[];saved_at:string};
export const redirectDraftKey=(scope:string,owner:string)=>`redirect-draft:v1:${encodeURIComponent(owner)}:${scope}`;
export function readRedirectDraft(raw:string|null):RedirectDraftDocument|null {
  try {const value=JSON.parse(raw||'null');if(value?.version!==1||!Array.isArray(value.rows)||value.rows.length>1000||typeof value.saved_at!=='string')return null;
    const rows:RedirectDraftRow[]=value.rows.map((r:RedirectDraftRow)=>{if(!r||typeof r.id!=='string'||typeof r.original!=='string'||typeof r.url!=='string'||typeof r.value!=='string'||!Array.isArray(r.expected?.rows)||r.expected.rows.some(e=>typeof e.url!=='string'||typeof e.value!=='string'))throw new Error('Invalid draft');return {id:r.id,original:r.original,url:r.url,value:r.value,removed:r.removed===true,expected:{rows:r.expected.rows.map(e=>({url:e.url,value:e.value}))}};});
    return {version:1,rows,saved_at:value.saved_at};
  }catch{return null;}
}
export function recoveryDraft(raw:string|null,path:string,base:DraftRedirect[],id:()=>string):RedirectDraftDocument|null {
  try {const value=JSON.parse(raw||'null');if(value?.version!==1||value.path!==path||!Array.isArray(value.desiredRows)||value.desiredRows.length>1000)return null;
    const rows:RedirectDraftRow[]=base.map(r=>({...r,id:id(),original:r.url,expected:{rows:[{...r}]}}));
    for(const desired of value.desiredRows){if(typeof desired.url!=='string'||typeof desired.value!=='string')return null;const index=rows.findIndex(r=>r.url===desired.url);if(index>=0)rows[index]={...rows[index],value:desired.value,removed:desired.removed===true};else rows.push({id:id(),url:desired.url,value:desired.value,original:'',removed:desired.removed===true,expected:{rows:[]}});}
    return {version:1,rows,saved_at:typeof value.saved_at==='string'?value.saved_at:new Date().toISOString()};
  }catch{return null;}
}
/** Remove only the selected edge; confirmed rows keep their concurrency snapshot. */
export function removeDraftConnection(rows:RedirectDraftRow[],source:string,target:string):RedirectDraftRow[] {
  const index=rows.findIndex(row=>!row.removed&&row.url===source&&row.value===target);
  if(index<0)return rows;
  return rows.flatMap((row,i)=>i!==index?[row]:row.original?[{...row,removed:true}]:[]);
}

/** Remove completed deletions and unchanged baseline rows deleted elsewhere. */
export function pruneConfirmedRedirectDeletes(rows:RedirectDraftRow[],live:DraftRedirect[]):RedirectDraftRow[] {
  const key=(value:string)=>{try{const raw=value.trim().replace(/^\/+/, '').replace(/^https?:\/\//i,'').replace(/^\/+/, '');if(/[\\\s]/.test(raw))return null;const url=new URL('https://'+raw);if(url.username||url.password||url.port||!['','/'].includes(url.pathname)||url.search||url.hash)return null;return url.hostname.toLowerCase().replace(/\.$/,'')||null;}catch{return null;}};
  const sources=new Set(live.map(r=>key(r.url)).filter(Boolean));
  const next=rows.filter(row=>{const original=key(row.original),unchanged=row.url===row.original&&row.expected.rows.length===1&&key(row.expected.rows[0].url)===original&&row.value===row.expected.rows[0].value;return !(original&&!sources.has(original)&&(row.removed||unchanged));});
  return next.length===rows.length?rows:next;
}

export function settledRedirectDeleteFailures<T extends {status:string;request:{action:string;redirect_delete?:unknown;redirect_original_source?:unknown;redirect_source?:unknown}}>(items:T[],live:DraftRedirect[]):T[] {
  return items.filter(item=>{if(item.status!=='failed'||item.request.action!=='domain_redirect'||item.request.redirect_delete!==true)return false;const source=String(item.request.redirect_original_source||item.request.redirect_source||'');return pruneConfirmedRedirectDeletes([{id:'receipt',url:source,value:'',original:source,removed:true,expected:{rows:[]}}],live).length===0;});
}
