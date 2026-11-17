import React from "react";
import { ArrowLeft, ArrowUpRight, Award, BookOpen, Check, Edit3, Plus, Save, Search, Users, X } from "lucide-react";
import { TemplateCombobox } from "./TemplateCombobox";
import { openDetailPage, backFromDetail } from "./detailNavigation";
import { filterPersonas, personaId, personaWords, type Persona, type PersonaCatalog, type PersonaCountry } from "./personaCatalog";
import "./styles/personas.css";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
function message(error: unknown) { return error instanceof Error ? error.message : "Не удалось загрузить данные. Повторите попытку."; }
function plainClick(event: React.MouseEvent<HTMLAnchorElement>) { return !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey && event.button === 0; }
function ProfileLink({ person, children }: { person: Persona; children: React.ReactNode }) {
  const href = `/personas/${person.id}/`;
  return <a href={href} onClick={event => { if (plainClick(event)) { event.preventDefault(); openDetailPage(href); } }}>{children}</a>;
}
function Portrait({ person, large = false }: { person: Pick<Persona, "portrait_url" | "first_name" | "last_name">; large?: boolean }) {
  const [failed, setFailed] = React.useState(false);
  return <div className={`personaPortrait${large ? " large" : ""}`}>
    {person.portrait_url && !failed ? <img src={person.portrait_url} alt={`${person.first_name} ${person.last_name}`} width={large ? 184 : 56} height={large ? 184 : 56} loading={large ? "eager" : "lazy"} onError={() => setFailed(true)} /> : <span>{person.first_name[0]}{person.last_name[0]}</span>}
  </div>;
}

export default function Personas({ api, canEdit, navigationLocation }: { api: Api; canEdit: boolean; navigationLocation: string }) {
  const [location, setLocation] = React.useState(() => window.location.pathname + window.location.search);
  const [catalog, setCatalog] = React.useState<PersonaCatalog | null>(null);
  const [error, setError] = React.useState("");
  const [retry, setRetry] = React.useState(0);
  const url = new URL(location, window.location.origin);
  const id = personaId(url.pathname);
  const geo = url.searchParams.get("geo") || "";
  const query = url.searchParams.get("q") || "";
  React.useEffect(() => setLocation(window.location.pathname + window.location.search), [navigationLocation]);
  React.useEffect(() => {
    const change = () => setLocation(window.location.pathname + window.location.search);
    window.addEventListener("popstate", change); return () => window.removeEventListener("popstate", change);
  }, []);
  React.useEffect(() => {
    const abort = new AbortController(); setError("");
    api<PersonaCatalog>("/personas", { signal: abort.signal }).then(setCatalog).catch(e => { if (!abort.signal.aborted) setError(message(e)); });
    return () => abort.abort();
  }, [api, retry]);
  function filters(next: { geo?: string; q?: string }) {
    const params = new URLSearchParams(url.search);
    for (const [key, value] of Object.entries(next)) value ? params.set(key, value) : params.delete(key);
    const path = `/personas${params.size ? `?${params}` : ""}`;
    window.history.replaceState(window.history.state, "", path); setLocation(path);
  }
  function saved(person: Persona) {
    setCatalog(current => {
      if (!current) return current;
      const items = current.items.some(p => p.id === person.id) ? current.items.map(p => p.id === person.id ? person : p) : [...current.items, person];
      return { ...current, items, total: items.length, countries: current.countries.map(country => ({ ...country, count: items.filter(p => p.geo === country.code).length })) };
    });
  }
  const items = filterPersonas(catalog?.items || [], geo, query);
  return <section className="personasView">
    {id ? <PersonaProfile key={id} id={id} api={api} canEdit={canEdit} countries={catalog?.countries || []} onSaved={saved} /> : <>
      <div className="personaCatalogHeader"><div><div className="personaEyebrow"><Users size={16} /> БАЗА АВТОРОВ</div><h2>Люди за текстами</h2><p>Профили, специализации и биографии для редакционных проектов.</p></div>{canEdit && <button className="button" onClick={() => openDetailPage("/personas/new/")}><Plus size={18} /> Добавить персону</button>}</div>
      <div className="personaGeoTabs" aria-label="Фильтр GEO">
        <button className={!geo ? "active" : ""} aria-pressed={!geo} onClick={() => filters({ geo: "" })}>Все GEO <b>{catalog?.total ?? "—"}</b></button>
        {catalog?.countries.map(country => <button key={country.code} className={geo === country.code ? "active" : ""} aria-pressed={geo === country.code} onClick={() => filters({ geo: country.code })}><span aria-hidden="true">{country.flag}</span> {country.name} <b>{country.count}</b></button>)}
      </div>
      <div className="personaSearch"><Search size={19} /><input aria-label="Поиск авторов" placeholder="Имя, фамилия или специализация" value={query} onChange={event => filters({ q: event.target.value })} />{query && <button aria-label="Очистить поиск" onClick={() => filters({ q: "" })}><X size={16} /></button>}<span>{items.length} авторов</span></div>
      {error ? <div className="personaError" role="alert">{error}<button className="button secondary compact" onClick={() => setRetry(v => v + 1)}>Повторить</button></div> : !catalog ? <p role="status">Загрузка базы авторов…</p> : <div className="personaTableWrap"><table className="personaTable">
        <thead><tr><th scope="col">GEO</th><th scope="col">Имя</th><th scope="col">Фамилия</th><th scope="col">Специализация</th><th scope="col">Биография</th><th scope="col">Награды</th><th scope="col"><span className="personaSrOnly">Профиль</span></th></tr></thead>
        <tbody>{items.map(person => <tr key={person.id}>
          <td><span className="personaGeo" title={person.country}><span aria-hidden="true">{person.flag}</span> {person.geo}</span></td>
          <td><div className="personaNameCell"><ProfileLink person={person}><Portrait person={person} /></ProfileLink><ProfileLink person={person}>{person.first_name}</ProfileLink></div></td>
          <td><ProfileLink person={person}>{person.last_name}</ProfileLink></td>
          <td lang={person.language}><strong>{person.specialization}</strong><small>{person.specializations.length} специализаций</small></td>
          <td><p lang={person.language} className="personaExcerpt">{person.biography_excerpt || person.biography}</p><small>{person.word_count} слов · <ProfileLink person={person}>Читать полностью</ProfileLink></small></td>
          <td><span className="personaAwardCount"><Award size={17} />{person.awards.length}</span></td>
          <td><ProfileLink person={person}><span className="personaOpen">Профиль <ArrowUpRight size={16} /></span></ProfileLink></td>
        </tr>)}</tbody>
      </table>{!items.length && <div className="personaEmpty">По этим условиям авторов нет.<button className="button secondary compact" onClick={() => filters({ geo: "", q: "" })}>Сбросить фильтры</button></div>}</div>}
      <p className="personaNote">Редакционные персоны с AI-портретами. Награды — вымышленные внутренние редакционные отличия.</p>
    </>}
  </section>;
}

function PersonaProfile({ id, api, canEdit, countries, onSaved }: { id: string; api: Api; canEdit: boolean; countries: PersonaCountry[]; onSaved: (person: Persona) => void }) {
  const [person, setPerson] = React.useState<Persona | null>(null);
  const [error, setError] = React.useState("");
  const [editing, setEditing] = React.useState(id === "new");
  const [retry, setRetry] = React.useState(0);
  const [success, setSuccess] = React.useState(false);
  React.useEffect(() => {
    if (id === "new") return;
    const abort = new AbortController(); setError("");
    api<Persona>(`/personas/${id}`, { signal: abort.signal }).then(setPerson).catch(e => { if (!abort.signal.aborted) setError(message(e)); });
    return () => abort.abort();
  }, [id, api, retry]);
  React.useEffect(() => { if (success) { const timer = window.setTimeout(() => setSuccess(false), 3000); return () => clearTimeout(timer); } }, [success]);
  async function save(payload: Partial<Persona>) {
    const value = await api<Persona>(id === "new" ? "/personas" : `/personas/${id}`, { method: id === "new" ? "POST" : "PUT", body: JSON.stringify(payload) });
    onSaved(value); setPerson(value); setEditing(false); setSuccess(true);
    if (id === "new") { window.history.replaceState(window.history.state, "", `/personas/${value.id}/?from=${encodeURIComponent("/personas")}`); window.dispatchEvent(new PopStateEvent("popstate")); }
  }
  return <>
    <div className="personaProfileBar"><a href="/personas" onClick={e => { if (plainClick(e)) { e.preventDefault(); backFromDetail("/personas"); } }}><ArrowLeft size={17} /> Все персоны</a><span role="status">{success && <><Check size={16} /> Сохранено успешно!</>}</span>{person && canEdit && !editing && <button className="button secondary compact" onClick={() => setEditing(true)}><Edit3 size={16} /> Редактировать</button>}</div>
    {error ? <div className="personaError" role="alert">{error}<button className="button secondary compact" onClick={() => setRetry(v => v + 1)}>Повторить</button></div> : editing && canEdit && (person || id === "new") ? <PersonaEditor person={person} countries={countries} onSave={save} onCancel={() => id === "new" ? backFromDetail("/personas") : setEditing(false)} /> : id === "new" && !canEdit ? <p>Добавлять авторов может администратор.</p> : !person ? <p role="status">Загрузка профиля…</p> : <>
      <header className="personaHero"><Portrait person={person} large /><div><div className="personaEyebrow"><span aria-hidden="true">{person.flag}</span> {person.country} · {person.geo}</div><h2 lang={person.language}>{person.first_name} {person.last_name}</h2><p className="personaRole" lang={person.language}>{person.specialization}</p><div className="personaStats"><span><BookOpen size={16} /> {person.word_count} слов</span><span>{person.specializations.length} специализаций</span><span><Award size={16} /> {person.awards.length} наград</span></div><small>Редакционная персона · AI-портрет</small></div></header>
      <div className="personaProfileGrid"><article className="personaBiography"><h3>Биография</h3><div lang={person.language}>{person.biography.split(/\n\s*\n/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div></article><aside className="personaSidebar"><section><h3>Специализации</h3><ul className="personaTags" lang={person.language}>{person.specializations.map(tag => <li key={tag}>{tag}</li>)}</ul></section><section><h3><Award size={20} /> Редакционные награды</h3><p className="personaNote">Вымышленные внутренние отличия персоны.</p><ul className="personaAwards" lang={person.language}>{person.awards.map((award, index) => <li key={`${award.title}-${index}`}><span>{award.title}</span><time>{award.year}</time></li>)}</ul></section></aside></div>
    </>}
  </>;
}

function PersonaEditor({ person, countries, onSave, onCancel }: { person: Persona | null; countries: PersonaCountry[]; onSave: (data: Partial<Persona>) => Promise<void>; onCancel: () => void }) {
  const [firstName, setFirstName] = React.useState(person?.first_name || "");
  const [lastName, setLastName] = React.useState(person?.last_name || "");
  const [geo, setGeo] = React.useState(person?.geo || "PL");
  const [role, setRole] = React.useState(person?.specialization || "");
  const [biography, setBiography] = React.useState(person?.biography || "");
  const [tags, setTags] = React.useState(person?.specializations.join("\n") || "");
  const [awards, setAwards] = React.useState(person?.awards || Array.from({ length: 4 }, () => ({ title: "", year: new Date().getFullYear() })));
  const [error, setError] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const count = personaWords(biography);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); if (saving) return;
    const specializations = tags.split("\n").map(v => v.trim()).filter(Boolean);
    if (count < 400) { setError("Биография должна содержать минимум 400 слов."); return; }
    if (specializations.length < 4 || specializations.length > 9) { setError("Добавьте от 4 до 9 специализаций, каждую с новой строки."); return; }
    setSaving(true); setError("");
    try { await onSave({ first_name: firstName, last_name: lastName, geo, specialization: role, biography, specializations, awards, portrait_url: person?.portrait_url || "", ...(person ? { revision: person.revision } : {}) }); }
    catch (e) { setError(message(e)); } finally { setSaving(false); }
  }
  return <form className="personaEditor" onSubmit={submit}><h2>{person ? "Редактирование профиля" : "Новая персона"}</h2><fieldset disabled={saving}>
    <div className="personaFields"><label>Имя<input value={firstName} required maxLength={80} onChange={e => setFirstName(e.target.value)} /></label><label>Фамилия<input value={lastName} required maxLength={80} onChange={e => setLastName(e.target.value)} /></label><TemplateCombobox label="GEO" value={geo} onChange={setGeo} options={countries.map(c => ({ value: c.code, label: `${c.flag} ${c.code} · ${c.name}` }))} /></div>
    <label>Основная специализация<input value={role} required minLength={3} maxLength={180} onChange={e => setRole(e.target.value)} /></label>
    <label>Биография <small className={count < 400 ? "personaIncomplete" : ""}>{count} / минимум 400 слов</small><textarea value={biography} rows={16} required maxLength={50000} onChange={e => setBiography(e.target.value)} /></label>
    <label>Специализации <small>От 4 до 9, каждая с новой строки</small><textarea value={tags} required rows={7} onChange={e => setTags(e.target.value)} /></label>
    <div className="personaEditorAwards"><h3>Редакционные награды <small>От 4 до 9</small></h3>{awards.map((award, index) => <div className="personaAwardFields" key={index}><label>Название {index + 1}<input value={award.title} required minLength={3} maxLength={200} onChange={e => setAwards(values => values.map((v, i) => i === index ? { ...v, title: e.target.value } : v))} /></label><label>Год<input type="number" min={1900} max={2100} required value={award.year} onChange={e => setAwards(values => values.map((v, i) => i === index ? { ...v, year: Number(e.target.value) } : v))} /></label><button className="button secondary compact" type="button" disabled={awards.length <= 4} aria-label={`Удалить награду ${index + 1}`} onClick={() => setAwards(values => values.filter((_, i) => i !== index))}><X size={16} /></button></div>)}<button className="button secondary compact" type="button" disabled={awards.length >= 9} onClick={() => setAwards(values => [...values, { title: "", year: new Date().getFullYear() }])}><Plus size={16} /> Добавить награду</button></div>
    <p className="personaNote">Профиль сохраняется как редакционная персона с вымышленными внутренними наградами.</p>
    {error && <p className="personaError" role="alert">{error}</p>}<div className="personaEditorActions"><button className="button" type="submit"><Save size={17} />{saving ? "Сохраняем…" : "Сохранить профиль"}</button><button className="button secondary" type="button" onClick={onCancel}>Отмена</button></div>
  </fieldset></form>;
}
