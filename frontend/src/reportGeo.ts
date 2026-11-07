const LANGUAGE_COUNTRIES: Record<string,string> = {
 ar:'AE',bg:'BG',cs:'CZ',da:'DK',de:'DE',en:'GB',es:'ES',et:'EE',fi:'FI',fr:'FR',hu:'HU',it:'IT',lt:'LT',nl:'NL',pl:'PL',pt:'PT',ro:'RO',ru:'RU',sk:'SK',sl:'SI',sr:'RS',sv:'SE',tr:'TR',uk:'UA',el:'GR'
};
export function reportCountry(geo?:string|null,fiberyName?:string):string|null {
 const value=(geo||'').trim();
 const parts=value.split(/[-_]/).filter(Boolean);
 let country:string|undefined;
 if(parts.length>1)country=parts.at(-1)?.toUpperCase();
 else if(/^[a-z]{2}$/.test(value)) {
  // Old Webdev records may contain only a language tag. The explicit Fibery
  // country suffix disambiguates these records without inferring from domains.
  const explicit=[...(fiberyName||'').matchAll(/_([A-Z]{2})(?=_|$)/g)].at(-1)?.[1];
  country=explicit||LANGUAGE_COUNTRIES[value]||value.toUpperCase();
 } else country=value.toUpperCase();
 if(country==='CS')country='CZ';
 if(country==='UK')country='GB';
 if(!country||country==='ZZ'||!/^[A-Z]{2}$/.test(country))return null;
 const name=new Intl.DisplayNames(['ru'],{type:'region'}).of(country);
 return name&&name!==country?country:null;
}
