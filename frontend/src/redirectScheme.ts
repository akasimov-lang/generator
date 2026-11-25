export type RedirectRow = {url:string; value:string};
export const cleanAddress = (value:string) => value.replace(/\s/g, '').replace(/^https?:\/\//i, '').replace(/^\/+/, '');
export function host(value:string) { try { return new URL('https://' + cleanAddress(value)).hostname.toLowerCase().replace(/^www\./,''); } catch { return ''; } }
export function schemeProblems(rows:RedirectRow[], domains:string[], types:Record<string,string>, canon:string) {
  const members=new Map(domains.map(d=>[host(d),d]));
  const seen=new Set<string>(), edges=new Map<string,string>(), errors:string[]=[];
  for(const row of rows) {
    const from=host(row.url), to=host(row.value);
    if(!from || !to) { errors.push('Заполните оба адреса каждой строки.'); continue; }
    if(seen.has(from)) errors.push(`Повторяется источник: ${row.url}`);
    seen.add(from); edges.set(from,to);
    if(from===to) errors.push(`Редирект на себя: ${row.url}`);
    if(from===host(canon)) errors.push(`Main должен отдавать страницу: ${row.url}`);
    const source=members.get(from), target=members.get(to);
    if(source && types[source]==='drop' && to!==host(canon) && (!target || !['drop','newreg'].includes(types[target]))) errors.push(`Дроп ${source}: выберите дроп или новорег этой сетки.`);
  }
  for(const start of edges.keys()) {
    const visited=new Set<string>(); let node:string|undefined=start;
    while(node && edges.has(node)) { if(visited.has(node)) { errors.push(`Цикл редиректов: ${start}`); break; } visited.add(node); node=edges.get(node); }
  }
  return [...new Set(errors)];
}
export function unlinkedDomains(domains:string[], rows:RedirectRow[]) {
  const linked=new Set(rows.flatMap(row=>[host(row.url),host(row.value)]));
  return domains.filter(d=>!linked.has(host(d)));
}
export function completeDrops(rows:RedirectRow[], domains:string[], types:Record<string,string>, canon:string) {
  const next=rows.map(r=>({...r}));
  const allowed=new Set(domains.filter(d=>['drop','newreg'].includes(types[d])).map(host));
  if(canon)allowed.add(host(canon));
  const pending=domains.filter(d=>types[d]==='drop'&&host(d)!==host(canon)&&!next.some(r=>host(r.url)===host(d)&&host(r.url)!==host(r.value)&&allowed.has(host(r.value))));
  if(!pending.length)return next;
  const targets=domains.filter(d=>types[d]==='newreg' && !rows.some(r=>host(r.url)===host(d) && types[domains.find(n=>host(n)===host(r.value))||'']==='drop'));
  if(!targets.length) throw new Error('В сетке нет доступных новорегов. Укажите типы доменов.');
  let index=0;
  for(const domain of pending) {
    const row=next.find(r=>host(r.url)===host(domain));
    const target=targets[index++ % targets.length];
    if(row) row.value=target; else next.push({url:domain,value:target});
  }
  return next;
}
export function sourceChoices(domains:string[], types:Record<string,string>, assigned:string[], canon:string, current='') {
  const occupied=new Set(assigned.map(host));
  const rank=(d:string)=>types[d]==='drop'?0:types[d]==='newreg'?1:2;
  return [...new Set([...domains,...(current?[current]:[])])]
    .filter(d=>types[d]!=='amp'&&(host(d)===host(current)||(!occupied.has(host(d))&&host(d)!==host(canon))))
    .sort((a,b)=>rank(a)-rank(b)||a.localeCompare(b));
}
/** Remove obsolete edges first, then update destinations before their incoming edges. */
export function orderRedirectChanges<T extends RedirectRow & {removed?:boolean}>(rows:T[]):T[] {
  const result=rows.filter(r=>r.removed), visited=new Set<T>();
  const active=rows.filter(r=>!r.removed);
  const visit=(row:T)=>{if(visited.has(row))return;visited.add(row);const target=active.find(r=>host(r.url)===host(row.value));if(target)visit(target);result.push(row);};
  active.forEach(visit);
  return result;
}
/** Layout positions alone never add an unlinked domain to the working scheme. */
export function graphDomainNames(domains:string[], rows:RedirectRow[], canon:string, placed:string[]) {
  const all:string[]=[],seen=new Set<string>();
  for(const domain of [canon,...domains,...rows.flatMap(r=>[r.url,host(r.value)])]){if(!domain)continue;const name=host(domain);if(!seen.has(name)){seen.add(name);all.push(domain);}}
  const linked=new Set(rows.flatMap(row=>[host(row.url),host(row.value)])),main=host(canon),manual=new Set(placed);
  const nodes=all.filter(domain=>{const name=host(domain);return name===main||linked.has(name)||manual.has(name);});
  const visible=new Set(nodes.map(host));
  const unused=domains.filter(domain=>!visible.has(host(domain)));
  return {nodes,unused,linked};
}
export function redirectDomainScope(domains:string[],rows:RedirectRow[],types:Record<string,string>,excluded:string[]=[]) {
  const ampKeys=new Set([...excluded,...Object.keys(types).filter(d=>types[d]==='amp')].map(host).filter(Boolean));
  const isAmp=(value:string)=>{const name=host(value);if(!name)return false;return [...ampKeys].some(root=>name===root||name.endsWith('.'+root));};
  for(const domain of [...domains,...rows.flatMap(r=>[r.url,r.value])])if(isAmp(domain))ampKeys.add(host(domain));
  return {ampKeys,isAmp,domains:domains.filter(d=>!isAmp(d)),redirects:rows.filter(r=>!isAmp(r.url)&&!isAmp(r.value))};
}

/** Resolve domain identities/types once instead of scanning every domain per option. */
export function prepareRedirectDomainOptions(domains:string[],types:Record<string,string>,canon:string) {
  type Choice={value:string;label:string;keywords:string;tone:'blue'|'green'|undefined;name:string;kind:string};
  const byValue=new Map<string,Choice>(),byHost=new Map<string,Choice>();
  const make=(value:string,name:string,kind:string):Choice=>({value,label:value,name,kind,tone:kind==='drop'?'blue':kind==='newreg'?'green':undefined,keywords:kind==='drop'?'дроп drop':kind==='newreg'?'новорег newreg':''});
  for(const value of domains){const name=host(value),option=make(value,name,types[value]||'');byValue.set(value,option);if(!byHost.has(name))byHost.set(name,option);}
  const rank=(kind:string)=>kind==='drop'?0:kind==='newreg'?1:2;
  const ordered=[...byValue.values()].filter(o=>o.kind!=='amp').sort((a,b)=>rank(a.kind)-rank(b.kind)||a.value.localeCompare(b.value));
  const main=host(canon);
  function resolve(value:string){const exact=byValue.get(value);if(exact)return exact;const name=host(value);return make(value,name,byHost.get(name)?.kind||types[value]||'');}
  return {
    tone:(value:string)=>resolve(value).tone,
    sources:(current:string,assigned:ReadonlySet<string>)=>{const selected=resolve(current),pool=current&&!byValue.has(current)?[...ordered,selected].sort((a,b)=>rank(a.kind)-rank(b.kind)||a.value.localeCompare(b.value)):ordered;return pool.filter(o=>o.kind!=='amp'&&(o.name===selected.name||(!assigned.has(o.name)&&o.name!==main)));},
    targets:(source:string)=>{const from=resolve(source);return ordered.filter(o=>o.name!==from.name&&(from.kind!=='drop'||['drop','newreg'].includes(o.kind)||o.name===main));}
  };
}

/** Use the network's classified parent type for subdomains without an explicit type. */
export function redirectDomainTypes(types:Record<string,string>,classification:Record<string,{parent_type?:string|null}>) {
  const result={...types};
  for(const [domain,role] of Object.entries(classification))if(!result[domain]&&role.parent_type)result[domain]=role.parent_type;
  return result;
}
