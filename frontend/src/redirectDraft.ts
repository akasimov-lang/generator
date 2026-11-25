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
