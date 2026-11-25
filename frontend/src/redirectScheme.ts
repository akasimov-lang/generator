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
    if(source && types[source]==='drop' && (!target || types[target]!=='newreg')) errors.push(`Дроп ${source}: выберите новорег этой сетки.`);
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
  const targets=domains.filter(d=>types[d]==='newreg' && !rows.some(r=>host(r.url)===host(d) && types[domains.find(n=>host(n)===host(r.value))||'']==='drop'));
  if(!targets.length) throw new Error('В сетке нет доступных новорегов. Укажите типы доменов.');
  let index=0;
  for(const domain of domains.filter(d=>types[d]==='drop' && host(d)!==host(canon))) {
    const row=next.find(r=>host(r.url)===host(domain));
    if(row && targets.some(t=>host(t)===host(row.value))) continue;
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
  const all=[...new Set([canon,...domains,...rows.flatMap(r=>[r.url,host(r.value)])])].filter(Boolean).filter((d,i,a)=>a.findIndex(v=>host(v)===host(d))===i);
  const linked=new Set(rows.flatMap(r=>[host(r.url),host(r.value)]));
  const nodes=all.filter(d=>host(d)===host(canon)||linked.has(host(d))||placed.includes(host(d)));
  const unused=domains.filter(d=>!nodes.some(n=>host(n)===host(d)));
  return {nodes,unused,linked};
}
export function redirectDomainScope(domains:string[],rows:RedirectRow[],types:Record<string,string>,excluded:string[]=[]) {
  const ampKeys=new Set([...excluded,...Object.keys(types).filter(d=>types[d]==='amp')].map(host).filter(Boolean));
  const isAmp=(value:string)=>{const name=host(value);if(!name)return false;return [...ampKeys].some(root=>name===root||name.endsWith('.'+root));};
  for(const domain of [...domains,...rows.flatMap(r=>[r.url,r.value])])if(isAmp(domain))ampKeys.add(host(domain));
  return {ampKeys,isAmp,domains:domains.filter(d=>!isAmp(d)),redirects:rows.filter(r=>!isAmp(r.url)&&!isAmp(r.value))};
}
