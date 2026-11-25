import "./styles/domain-redirects.css";
export type DomainRedirect = {url:string;value:string};
export type RedirectEdit = {redirect_delete?:boolean;expected?:{rows:DomainRedirect[]};redirect_source:string;redirect_target:string;redirect_original_source:string};

function redirectHost(value:string):string {
  try {
    const url=new URL(value.trim().includes("://")?value.trim():`https://${value.trim()}`);
    return ["http:","https:"].includes(url.protocol)?url.hostname.toLowerCase().replace(/\.$/,""):"";
  }catch{return "";}
}

export function domainRedirectTargets(redirects:DomainRedirect[],available:boolean):Map<string,string> {
  const targets=new Map<string,string>();
  if(available)for(const row of redirects){
    if(!row||typeof row.url!=="string"||typeof row.value!=="string")continue;
    const source=redirectHost(row.url),target=redirectHost(row.value);
    if(source&&target)targets.set(source,target);
  }
  return targets;
}

export function domainRedirectTarget(domain:string,targets:Map<string,string>):string|undefined {
  return targets.get(redirectHost(domain));
}

export { RedirectWorkspace as DomainRedirects } from "./RedirectWorkspace";
