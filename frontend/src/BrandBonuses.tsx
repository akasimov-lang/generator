import React from "react";
import { BookOpen, Gift, Globe2, List, Search } from "lucide-react";
import { bonusPath, bonusRoute, filterBonusBrands, type BonusBrand, type BonusCatalog, type BrandOffer } from "./brandBonusCatalog";
import "./styles/brand-bonuses.css";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
const countries: Record<string, string> = { PL: "🇵🇱 Польша", CZ: "🇨🇿 Чехия" };
function day(value: string) { const d = new Date(value); return Number.isNaN(d.valueOf()) ? "—" : d.toLocaleDateString("ru-RU", { timeZone: "Europe/Moscow" }); }
function Logo({ brand }: { brand: BonusBrand }) {
  const [failed, setFailed] = React.useState(false);
  return <span className="bonusBrandLogo">{brand.logo_url && !failed ? <img src={brand.logo_url} alt="" width="60" height="36" loading="lazy" onError={() => setFailed(true)} /> : <span aria-hidden="true">{brand.name.slice(0, 2)}</span>}</span>;
}
function LocalLink({ href, children, className, current }: { href: string; children: React.ReactNode; className?: string; current?: boolean }) {
  return <a className={className} href={href} aria-current={current ? "page" : undefined} onClick={event => {
    if (event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault(); window.history.pushState(null, "", href); window.dispatchEvent(new PopStateEvent("popstate")); window.scrollTo(0, 0);
  }}>{children}</a>;
}
function Status({ offer }: { offer: BrandOffer }) {
  const expired = offer.status === "expired" || Boolean(offer.valid_until && new Date(`${offer.valid_until}T23:59:59+03:00`).getTime() < Date.now());
  return <span className={`bonusOfferStatus ${expired ? "expired" : offer.status}`}>
    {expired ? "Акция завершена" : offer.status === "verified" ? "Описание проверено" : "Сохранённые условия"} · {day(offer.observed_at)}
  </span>;
}
function Offer({ brand, offer, showBrand }: { brand: BonusBrand; offer: BrandOffer; showBrand?: boolean }) {
  return <article className="brandBonusOffer">
    {showBrand && <LocalLink className="bonusBrandName" href={bonusPath(brand.geo, brand.id)}><Logo brand={brand} /><strong>{brand.name}</strong><small>{countries[brand.geo]}</small></LocalLink>}
    <div className="brandBonusOfferHeading"><span className="bonusGift"><Gift size={20} /></span><h3>{offer.title}</h3></div>
    <div className="bonusOfferMeta"><span>{offer.category}</span><Status offer={offer} /></div>
    {offer.facts.length > 0 && <dl className="bonusOfferFacts">{offer.facts.map((fact, i) => <div key={`${fact.label}-${i}`}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>)}</dl>}
    {offer.valid_until && <p className="bonusEndDate">Срок акции: до {day(offer.valid_until)}</p>}
  </article>;
}

export default function BrandBonuses({ api, navigationLocation }: { api: Api; navigationLocation: string }) {
  const [location, setLocation] = React.useState(() => window.location.pathname + window.location.search);
  const [catalog, setCatalog] = React.useState<BonusCatalog | null>(null);
  const [error, setError] = React.useState("");
  const [retry, setRetry] = React.useState(0);
  React.useEffect(() => setLocation(window.location.pathname + window.location.search), [navigationLocation]);
  React.useEffect(() => { const update = () => setLocation(window.location.pathname + window.location.search); window.addEventListener("popstate", update); return () => window.removeEventListener("popstate", update); }, []);
  React.useEffect(() => {
    const abort = new AbortController(); setError("");
    api<BonusCatalog>("/brand-bonuses", { signal: abort.signal }).then(setCatalog).catch(e => { if (!abort.signal.aborted) setError(e instanceof Error ? e.message : "Не удалось загрузить каталог."); });
    return () => abort.abort();
  }, [api, retry]);
  const url = new URL(location, window.location.origin);
  const route = bonusRoute(url.pathname);
  const query = url.searchParams.get("q") || "";
  const view = url.searchParams.get("view") === "bonuses" ? "bonuses" : "brands";
  function search(value: string) { const params = new URLSearchParams(url.search); value ? params.set("q", value) : params.delete("q"); const path = url.pathname + (params.size ? `?${params}` : ""); window.history.replaceState(window.history.state, "", path); setLocation(path); }
  function listPath(geo: string, mode = view) { const params = new URLSearchParams(); if (query) params.set("q", query); if (mode === "bonuses") params.set("view", mode); return bonusPath(geo) + (params.size ? `?${params}` : ""); }
  if (error) return <section className="brandBonuses"><div role="alert" className="bonusCatalogError">{error}<button className="button secondary" onClick={() => setRetry(n => n + 1)}>Повторить загрузку</button></div></section>;
  if (!catalog) return <p role="status">Загрузка брендов и бонусов…</p>;
  const selected = route.id ? catalog.items.find(item => item.geo === route.geo && item.id === route.id) : undefined;
  if (!route.valid || (route.id && !selected)) return <section className="brandBonuses"><h2>Страница не найдена</h2><LocalLink href={bonusPath()}>Открыть каталог бонусов</LocalLink></section>;
  const items = filterBonusBrands(catalog.items, route.geo, query);
  const offerCount = items.reduce((sum, brand) => sum + brand.offers.length, 0);
  return <section className="brandBonuses" aria-label="Каталог бонусов брендов">
    <div className="bonusCatalogIntro"><p>Бренды и известные предложения для Польши и Чехии.</p><small>Собрано: {day(catalog.updated_at)}</small></div>
    <nav className="bonusCountryTabs" aria-label="Страна бонусов">
      <LocalLink href={listPath("")} current={!route.geo}><Globe2 size={18} /> Все страны <span>{catalog.total}</span></LocalLink>
      {catalog.countries.map(country => <LocalLink key={country.code} href={listPath(country.code)} current={route.geo === country.code}><span aria-hidden="true">{country.flag}</span> {country.name} <span>{country.brands}</span></LocalLink>)}
    </nav>
    {selected ? <>
      <LocalLink className="bonusBackLink" href={listPath(route.geo)}><List size={16} /> Все бренды · {countries[route.geo]}</LocalLink>
      <header className="bonusBrandHeader"><Logo brand={selected} /><div><h2>{selected.name}</h2><p>{countries[selected.geo]} · Известных бонусов: {selected.offers.length}</p></div></header>
      <div className="brandBonusOfferList">{selected.offers.map(offer => <Offer key={offer.id} brand={selected} offer={offer} />)}</div>
    </> : <>
      <div className="bonusCatalogToolbar"><nav aria-label="Вид каталога" className="bonusViewTabs"><LocalLink href={listPath(route.geo, "brands")} current={view === "brands"}><BookOpen size={17} /> Бренды</LocalLink><LocalLink href={listPath(route.geo, "bonuses")} current={view === "bonuses"}><Gift size={17} /> Бонусы</LocalLink></nav>
        <label className="bonusCatalogSearch"><Search size={18} /><input type="search" value={query} onChange={e => search(e.target.value)} placeholder="Найти бренд или бонус" aria-label="Поиск брендов и бонусов" /></label></div>
      <p className="bonusCatalogCount" role="status">Брендов: {items.length} · Бонусов: {offerCount}</p>
      {!items.length ? <div className="bonusCatalogEmpty"><Search size={24} /><p>По вашему запросу ничего не найдено.</p><button className="button secondary" onClick={() => search("")}>Сбросить поиск</button></div> : view === "brands" ? <div className="bonusBrandTable"><table><thead><tr><th>Бренд</th><th>Страна</th><th>Бонусов</th><th>Известное предложение</th></tr></thead><tbody>{items.map(brand => <tr key={`${brand.geo}-${brand.id}`}><td><LocalLink className="bonusBrandName" href={bonusPath(brand.geo, brand.id)}><Logo brand={brand} /><strong>{brand.name}</strong></LocalLink></td><td>{countries[brand.geo]}</td><td><LocalLink className="bonusCountLink" href={bonusPath(brand.geo, brand.id)}>{brand.offers.length}</LocalLink></td><td><LocalLink href={bonusPath(brand.geo, brand.id)}>{brand.offers[0]?.title || "Нет сохранённых предложений"}</LocalLink></td></tr>)}</tbody></table></div> : <div className="brandBonusOfferList">{items.flatMap(brand => brand.offers.map(offer => <Offer key={`${brand.geo}-${brand.id}-${offer.id}`} brand={brand} offer={offer} showBrand />))}</div>}
    </>}
  </section>;
}
