export type PageRedirectRow={id:string;domain:string;url:string;value:string;original?:{domain:string;url:string;value:string};removed?:boolean};
export function pageRedirectDraftKey(scope:string,owner:string) {
  return `page-redirect-draft:${encodeURIComponent(owner)}:${encodeURIComponent(scope)}`;
}
export function readPageRedirectDraft(raw:string|null):PageRedirectRow[]|null {
  try {
    const doc=JSON.parse(raw||'null');
    const address=(value:unknown):value is {domain:string;url:string;value:string}=>!!value&&typeof value==='object'&&['domain','url','value'].every(key=>typeof (value as Record<string,unknown>)[key]==='string');
    if(doc?.version!==1||!Array.isArray(doc.rows)||!doc.rows.every((row:unknown)=>address(row)&&typeof (row as PageRedirectRow).id==='string'&&((row as PageRedirectRow).removed===undefined||typeof (row as PageRedirectRow).removed==='boolean')&&(!(row as PageRedirectRow).original||address((row as PageRedirectRow).original))))return null;
    if(new Set(doc.rows.map((row:PageRedirectRow)=>row.id)).size!==doc.rows.length)return null;
    return doc.rows;
  }catch{return null;}
}
