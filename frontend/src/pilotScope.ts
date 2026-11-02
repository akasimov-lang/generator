export type PilotScopeMode = "include" | "exclude";
export type PilotSelection = {brands: string[]; geos: string[]; scope_mode?: PilotScopeMode};
export type PilotGroup = {brand: string; geo: string; count: number};
export type PilotOption = {value: string; label: string; count: number; pinned?: boolean; disabled?: boolean};
export const brandKey = (value: string) => {
 const key=value.toLocaleLowerCase().replace(/[^\p{L}\p{N}_]/gu, "");
 return key==="maxacasino"?"maxa":key;
};
export const geoKey = (value: string) => {
 const key=value.trim().replace(/_/g,"-").split("-").at(-1)!.toUpperCase();
 return key==="CS"?"CZ":key;
};
export function savedSelection(value?: Partial<PilotSelection> & {brand?: string; geo?: string}): PilotSelection {
 return {brands:value?.brands??(value?.brand?[value.brand]:[]),geos:(value?.geos??(value?.geo?[value.geo]:[])).map(geoKey),scope_mode:value?.scope_mode??"include"};
}
export function sameSelection(a: PilotSelection, b: PilotSelection): boolean {
 const keys=(values:string[],key:(value:string)=>string)=>[...new Set(values.map(key))].sort().join("\n");
 return (a.scope_mode??"include")===(b.scope_mode??"include")&&keys(a.brands,brandKey)===keys(b.brands,brandKey)&&keys(a.geos,geoKey)===keys(b.geos,geoKey);
}
export function inPilotScope(row: {brand?:string;geo:string}, selection: PilotSelection): boolean {
 const matchesBrand=!selection.brands.length||selection.brands.some(value=>brandKey(value)===brandKey(row.brand||"Общие ключи"));
 const matchesGeo=!selection.geos.length||selection.geos.some(value=>geoKey(value)===geoKey(row.geo));
 if(selection.scope_mode==="exclude")return !selection.brands.length||!selection.geos.length||!(matchesBrand&&matchesGeo);
 return matchesBrand&&matchesGeo;
}
export function scopeError(groups:PilotGroup[], selection:PilotSelection):string {
 if(new Set(selection.brands.map(brandKey)).size>5)return "Можно выбрать не более 5 брендов.";
 if(selection.scope_mode!=="exclude")return "";
 if(!selection.brands.length||!selection.geos.length)return "Для исключения выберите хотя бы один бренд и одно ГЕО.";
 const empty=selection.geos.map(geoKey).filter(geo=>!groups.some(row=>geoKey(row.geo)===geo&&row.count>0&&inPilotScope(row,selection)));
 return empty.length?`Нельзя исключить все проекты в ГЕО ${[...new Set(empty)].join(", ")}. Оставьте хотя бы один бренд в каждом выбранном ГЕО.`:"";
}
export function scopeFacets(groups: PilotGroup[], selection: PilotSelection) {
 const brands=new Map<string,{label:string;count:number}>(),geos=new Map<string,number>();
 const selectedBrands=new Set(selection.brands.map(brandKey)),selectedGeos=new Set(selection.geos.map(geoKey));
 let total=0,excluded=0,available=0,brandTotal=0,geoTotal=0;
 for(const row of groups){
  const key=brandKey(row.brand),geo=geoKey(row.geo);
  const matchesGeo=!selectedGeos.size||selectedGeos.has(geo),matchesBrand=!selectedBrands.size||selectedBrands.has(key);
  if(matchesGeo){const current=brands.get(key);brands.set(key,{label:current?.label||row.brand,count:(current?.count||0)+row.count});brandTotal+=row.count;}
  if(matchesBrand){geos.set(geo,(geos.get(geo)||0)+row.count);geoTotal+=row.count;}
  available+=row.count;
  if(inPilotScope(row,selection))total+=row.count;
  else if(selection.scope_mode==="exclude")excluded+=row.count;
 }
 // Keep the two priority countries visible even when this brand selection has no projects there.
 for(const code of ["PL","CZ"])if(groups.some(row=>geoKey(row.geo)===code)&&!geos.has(code))geos.set(code,0);
 // A selection that no longer matches remains removable, never silently becomes “all”.
 for(const value of selection.brands)if(!brands.has(brandKey(value)))brands.set(brandKey(value),{label:value,count:0});
 for(const value of selection.geos)if(!geos.has(geoKey(value)))geos.set(geoKey(value),0);
 const brandOptions:PilotOption[]=[...brands].map(([key,row])=>({value:selection.brands.find(value=>brandKey(value)===key)||row.label,label:row.label,count:row.count,disabled:row.count===0&&!selectedBrands.has(key)}))
  .sort((a,b)=>b.count-a.count||a.label.localeCompare(b.label,"ru"));
 const names=new Intl.DisplayNames(["ru"],{type:"region"});
 const geoOptions:PilotOption[]=[...geos].filter(([geo])=>/^[A-Z]{2}$/.test(geo)).map(([value,count])=>({value,count,disabled:count===0&&!selectedGeos.has(value),pinned:value==="PL"||value==="CZ",label:`${String.fromCodePoint(...[...value].map(c=>127397+c.charCodeAt(0)))} ${names.of(value)} (${value})`}))
  .sort((a,b)=>Number(b.pinned)-Number(a.pinned)||(a.pinned&&b.pinned?(a.value==="PL"?-1:1):b.count-a.count||a.label.localeCompare(b.label,"ru")));
 return {brands:brandOptions,geos:geoOptions,total,excluded,available,brandTotal,geoTotal};
}
export function toggleSelection(values:string[],value:string,max?:number):string[]{
 if(!value)return [];
 if(values.includes(value))return values.filter(current=>current!==value);
 return max!==undefined&&values.length>=max?values:[...values,value];
}
