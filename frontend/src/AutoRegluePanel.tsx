import React from "react";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type Rules = { schedule_enabled: boolean; interval_days: number; scheme_mode: "preserve" | "add_auxiliary" | "base_only"; auxiliary_hreflangs: string[] };
type Config = Rules & { domain_layout: "subdomain_main" | "root_main"; scope: "mass" | "personal"; enabled: boolean; drop_domain: string; x_default_use_newreg: boolean; x_default_newreg_domain: string; parent_kind: "drop" | "newreg"; newreg_domain: string; language: string; profile_id: string; variant: "current" | "provided" | "before" | "after"; fake_main_path: string };
type GlobalConfig = Rules & { enabled: boolean; max_projects: number };
type Template = { id: string; project: string; brand: string; geo: string; variants: Record<string, unknown> };
type Plan = { site_id: string; project: string; old_main: string; new_main: string; drop_domain: string; x_default_domain?: string; language_domain?: string; alternateMarkup: string; required_page_urls: string[]; added_hreflang?: string | null; pool_exhausted?: boolean; preview_token: string; requestId: string };
type Run = { id: string; site_id: string; status: string; phase: string; message: string; plan: Plan };
type ProjectData = { next_run_at?: string | null; language_pool?: string[]; config: Config; settings: GlobalConfig; eligible: boolean; geo: string; templates: Template[]; runs: Run[] };
const active = ["queued", "running", "waiting", "partial"];
const labels: Record<string, string> = { queued: "В очереди", running: "Выполняется", waiting: "Ожидает подтверждения", partial: "Нужна проверка результата", completed: "Завершён", failed: "Ошибка", cancelled: "Остановлен" };
const phases: Record<string, string> = { prepared: "Подготовлен", reserve: "Сохранение резерва", reglue: "Смена Main", alternates: "Обновление альтернейтов", completed: "Все этапы подтверждены" };
const errorText = (e: unknown) => e instanceof Error ? e.message : "Не удалось выполнить запрос";
const body = (method: string, value: unknown): RequestInit => ({ method, body: JSON.stringify(value) });

function PlanPreview({ plan }: { plan: Plan }) {
  return <div className="autoRegluePlan"><strong>{plan.project}</strong><p>{plan.old_main} → <b>{plan.new_main}</b></p><p>x-default: <b>{plan.x_default_domain || plan.drop_domain}</b></p>
    {plan.language_domain && <p>Домен языковых альтернейтов: <b>{plan.language_domain}</b></p>}{plan.added_hreflang && <p>Новый фейковый альтернейт: <b>{plan.added_hreflang}</b></p>}{plan.pool_exhausted && <p>Список языков исчерпан: схема сохраняется.</p>}<pre>{plan.alternateMarkup}</pre>{plan.required_page_urls.length > 0 && <p className="muted">Перед сменой Main будут проверены страницы: {plan.required_page_urls.join(", ")}. Их нужно создать заранее.</p>}</div>;
}

function AutomationRules({ value, onChange, pool }: { value: Rules; onChange: (patch: Partial<Rules>) => void; pool: string[] }) {
  const [languages, setLanguages] = React.useState((value.auxiliary_hreflangs || []).join(", "));
  return <div className="networkSection">
    <label className="checkboxRow"><input type="checkbox" checked={!!value.schedule_enabled} onChange={e => onChange({ schedule_enabled: e.target.checked })} /> Включить расписание автопереклеев</label>
    <label>Периодичность автопереклея<select value={value.interval_days || 7} onChange={e => onChange({ interval_days: Number(e.target.value) })}>{[3, 4, 5, 7, 14].map(days => <option key={days} value={days}>Раз в {days} {days < 5 ? "дня" : "дней"}</option>)}</select></label>
    <p className="muted">Сохранение включённого расписания создаёт задачу и сразу ставит первый переклей в очередь. Дальше запуски идут по сохранённому графику. Обновление страницы, перезапуск сервера и повторное сохранение не сбрасывают отсчёт. Изменение периода считается от последнего планового запуска. Незавершённый переклей блокирует следующий.</p>
    <label className="checkboxRow"><input type="checkbox" checked={value.scheme_mode === "add_auxiliary"} onChange={() => onChange({ scheme_mode: "add_auxiliary" })} /> Добавлять новый фейковый альтернейт при каждом переклее</label>
    <label className="checkboxRow"><input type="checkbox" checked={!value.scheme_mode || value.scheme_mode === "preserve"} onChange={() => onChange({ scheme_mode: "preserve" })} /> Сохранять схему: обновлять адреса и дроп в x-default</label>
    <label className="checkboxRow"><input type="checkbox" checked={value.scheme_mode === "base_only"} onChange={() => onChange({ scheme_mode: "base_only" })} /> Только базовые альтернейты — без фейковых языков и GEO</label>
    {value.scheme_mode === "base_only" && <div className="autoRegluePlan">
      <p>При переклее сохраняются ровно три ссылки. Остальные языковые альтернейты удаляются из разметки.</p>
      <ul><li><b>Язык проекта</b>, без GEO (например az) — главная страница языкового домена или поддомена.</li>
        <li><b>Язык-GEO</b> (например az-AZ) — внутренняя страница; путь берётся из настроек или схемы проекта.</li>
        <li><b>x-default</b> — корневой дроп. При canonical на языковом домене выбирается неиспользованный дроп сетки; при canonical = x-default используется новый корневой Main. Новорег разрешается отдельным чекбоксом «Использовать новорег в x-default» внутри проекта.</li></ul>
      <p>Пример для языка az, GEO AZ и пути /events/:</p>
      <pre>{'<link rel="alternate" hreflang="az" href="https://pinup-casino-az.clubheavenjax.com/" />\n<link rel="alternate" hreflang="az-AZ" href="https://pinup-casino-az.clubheavenjax.com/events/" />\n<link rel="alternate" hreflang="x-default" href="https://clubheavenjax.com/" />'}</pre>
      <p className="muted">Адреса в примере иллюстративные. Для запуска подставляются язык, GEO, выбранные домены и путь конкретного проекта.</p>
    </div>}
    {value.scheme_mode !== "base_only" && <><label>Языки для новых фейковых альтернейтов<textarea rows={3} value={languages} onChange={e => { setLanguages(e.target.value); onChange({ auxiliary_hreflangs: e.target.value.split(/[\s,;]+/).filter(Boolean) }); }} /></label>
    <button type="button" className="button secondary compact" onClick={() => { setLanguages(pool.join(", ")); onChange({ auxiliary_hreflangs: pool }); }}>Заполнить языками ЕС и СНГ</button>
    <p className="muted">В режиме добавления берём один следующий неиспользованный код. При исчерпании списка сохраняем схему. Адреса ведут на новый Main, пути сохраняются, x-default — на выбранный корневой домен.</p></>}
  </div>;
}

function Runs({ runs, api, refresh }: { runs: Run[]; api: Api; refresh: () => Promise<void> }) {
  const [busy, setBusy] = React.useState(""); const [error, setError] = React.useState("");
  async function control(id: string, action: string) {
    setBusy(id); setError("");
    try { await api(`/auto-reglue/runs/${id}/${action}`, { method: "POST" }); await refresh(); }
    catch (e) { setError(errorText(e)); } finally { setBusy(""); }
  }
  return <section className="networkSection"><h3>Запуски</h3>{error && <p role="alert">{error}</p>}{!runs.length && <p className="muted">Запусков пока нет.</p>}
    {runs.map(run => <div className="autoReglueRun" key={run.id}><strong>{run.plan.project} · {labels[run.status] || run.status}</strong><span>{phases[run.phase] || run.phase}</span><p>{run.message}</p>
      {active.includes(run.status) && <div className="networkActions"><button className="button secondary compact" disabled={!!busy} onClick={() => void control(run.id, "resume")}>Проверить результат и продолжить</button><button className="button secondary compact" disabled={!!busy} onClick={() => void control(run.id, "cancel")}>Остановить</button></div>}
    </div>)}{runs.some(r => active.includes(r.status)) && <p className="muted">Остановка не отменяет уже подтверждённую смену Main. При неизвестном результате повторная запись не отправляется.</p>}</section>;
}

function ProjectConfigEditor({ siteId, api }: { siteId: string; api: Api }) {
  const [data, setData] = React.useState<ProjectData | null>(null); const [draft, setDraft] = React.useState<Config | null>(null);
  const [plan, setPlan] = React.useState<Plan | null>(null); const [busy, setBusy] = React.useState(false); const [error, setError] = React.useState("");
  const load = React.useCallback(async () => { const next = await api<ProjectData>(`/auto-reglue/projects/${siteId}`); setData(next); setDraft(old => old || next.config); }, [api, siteId]);
  React.useEffect(() => { void load().catch(e => setError(errorText(e))); }, [load]);
  const pending = data?.runs.some(r => active.includes(r.status));
  React.useEffect(() => { if (!pending) return; const timer = setInterval(() => void load().catch(e => setError(errorText(e))), 5000); return () => clearInterval(timer); }, [load, pending]);
  async function perform(fn: () => Promise<void>) { setBusy(true); setError(""); try { await fn(); } catch (e) { setError(errorText(e)); } finally { setBusy(false); } }
  if (!draft || !data) return <p>{error || "Загружаем настройки…"}</p>;
  const dirty = JSON.stringify(draft) !== JSON.stringify(data.config);
  const change = (patch: Partial<Config>) => { setDraft({ ...draft, ...patch }); setPlan(null); };
  const baseOnly = (draft.scope === "personal" ? draft.scheme_mode : data.settings.scheme_mode) === "base_only";
  const template = data.templates.find(t => t.id === draft.profile_id);
  return <div className="autoReglueSettings">{error && <div className="notice" role="alert">{error}</div>}
    <p>GEO проекта: <b>{data.geo || "не задано"}</b>. Допуск: {draft.scope === "personal" ? "Персональные настройки" : data.eligible ? "Массовые действия" : "нужен статус «Массовые действия»"}.</p>
    {draft.scope !== "personal" && !data.settings.enabled && <p className="notice">Включите общие настройки в разделе «Автопереклей».</p>}
    <label className="checkboxRow"><input type="checkbox" checked={draft.scope === "personal"} onChange={e => change({ scope: e.target.checked ? "personal" : "mass" })} /> Персональный автопереклей — исключить проект из массовых запусков</label>
    {draft.scope === "personal" && <p className="notice">Используются только настройки этого проекта, независимо от статуса и глобальных правил массового автопереклея.</p>}
    <label className="checkboxRow"><input type="checkbox" checked={draft.enabled} onChange={e => change({ enabled: e.target.checked })} /> Участвует в автопереклеях</label>
    <h3>Соотношение canonical и альтернейтов</h3>
    <label className="checkboxRow"><input type="radio" name={`domain-layout-${siteId}`} checked={draft.domain_layout === "root_main"} onChange={() => change({ domain_layout: "root_main" })} /> Canonical = x-default; языковые альтернейты на поддомене</label>
    <label className="checkboxRow"><input type="radio" name={`domain-layout-${siteId}`} checked={draft.domain_layout !== "root_main"} onChange={() => change({ domain_layout: "subdomain_main" })} /> Canonical = домен языковых альтернейтов; x-default отдельно</label>
    {baseOnly && draft.domain_layout !== "root_main" && <p className="notice">x-default выбирается по порядку из неиспользованных дропов сетки. Исключаем историю Main, x-default и остальных альтернейтов. Тип домена задаётся во вкладке «Сетка». При разрешении новорега выбираем неиспользованный новорег. Если кандидата нет, переклей не запускается.</p>}
    {draft.domain_layout === "root_main" && <p className="notice">При каждом запуске меняем корневой Main. Берём следующий домен типа «Дроп» (или «Новорег» при включённом чекбоксе ниже), который не был Main, и его неиспользованный поддомен из сетки. Типы задаются во вкладке «Сетка».</p>}
    <label className="checkboxRow"><input type="checkbox" checked={!!draft.x_default_use_newreg} onChange={e => change({ x_default_use_newreg: e.target.checked })} /> Использовать новорег в x-default</label>
    <div className="autoReglueFields">
      {!baseOnly && draft.x_default_use_newreg && draft.domain_layout !== "root_main" && <label>Новорег для x-default<input value={draft.x_default_newreg_domain || ""} onChange={e => change({ x_default_newreg_domain: e.target.value })} placeholder="new-domain.com" /></label>}
      {draft.domain_layout !== "root_main" && (!baseOnly || draft.parent_kind === "drop") && <label>{baseOnly ? "Родительский дроп для Main" : "Дроп для x-default"}<input value={draft.drop_domain} placeholder="example.com" onChange={e => change({ drop_domain: e.target.value })} /></label>}
      <label>Язык проекта (если не задан в кэше)<input value={draft.language} placeholder="az" onChange={e => change({ language: e.target.value })} /></label>
      {draft.domain_layout !== "root_main" && <label>Поддомены для нового Main<select value={draft.parent_kind} onChange={e => change({ parent_kind: e.target.value as Config["parent_kind"] })}><option value="drop">Поддомены дропа</option><option value="newreg">Поддомены новорега</option></select></label>}
      {draft.domain_layout !== "root_main" && draft.parent_kind === "newreg" && <label>Родительский новорег<input value={draft.newreg_domain} placeholder="new-domain.com" onChange={e => change({ newreg_domain: e.target.value })} /></label>}
      <label>Схема альтернейтов<select value={draft.profile_id} onChange={e => { const t = data.templates.find(x => x.id === e.target.value); change({ profile_id: e.target.value, variant: (t ? Object.keys(t.variants).includes("after") ? "after" : Object.keys(t.variants)[0] : "current") as Config["variant"] }); }}><option value="">Текущая схема проекта</option>{data.templates.map(t => <option key={t.id} value={t.id}>{t.brand} · {t.geo} · {t.project}</option>)}</select></label>
      {template && <label>Версия схемы<select value={draft.variant} onChange={e => change({ variant: e.target.value as Config["variant"] })}>{Object.keys(template.variants).map(v => <option key={v} value={v}>{v === "after" ? "Схема стала" : v === "before" ? "Схема была" : "Предоставленная схема"}</option>)}</select></label>}
      <label>Путь копии главной для языка и GEO<input value={draft.fake_main_path} placeholder="/events/" onChange={e => change({ fake_main_path: e.target.value })} /></label>
    </div>
    {draft.scope === "personal" && <AutomationRules key="personal-rules" value={draft} onChange={change} pool={data.language_pool || []} />}
    {data.next_run_at && <p>Следующий запуск: <b>{new Date(data.next_run_at).toLocaleString("ru-RU")}</b></p>}
    {draft.domain_layout !== "root_main" && <p className="muted">Берём следующий поддомен после текущего Main по порядку сетки, пропуская все бывшие Main. Дополнительные языки сохраняем, их адреса переносим на новый Main. x-default определяется выбранным режимом: в базовой схеме — неиспользованный домен сетки. Пустой путь сохраняет путь выбранного шаблона.</p>}
    <div className="networkActions"><button className="button secondary" disabled={busy || !dirty} onClick={() => void perform(async () => { const saved = await api<Config>(`/auto-reglue/projects/${siteId}`, body("PUT", draft)); setDraft(saved); setPlan(null); await load(); })}>Сохранить настройки</button>
      <button className="button secondary" disabled={busy || dirty || !(data.eligible || draft.scope === "personal") || !draft.enabled || (draft.scope !== "personal" && !data.settings.enabled) || pending} onClick={() => void perform(async () => { const next = await api<Plan>(`/auto-reglue/projects/${siteId}/preview`, { method: "POST" }); setPlan({ ...next, requestId: crypto.randomUUID() }); })}>Подготовить переклей</button></div>
    {plan && <><PlanPreview plan={plan} /><button className="button primary" disabled={busy || dirty || pending} onClick={() => void perform(async () => { const result = await api<{ results: { error?: string }[] }>("/auto-reglue/start", body("POST", { scope: "project", items: [{ site_id: siteId, preview_token: plan.preview_token, request_id: plan.requestId }] })); if (result.results[0]?.error) throw new Error(result.results[0].error); setPlan(null); await load(); })}>Запустить автопереклей проекта</button></>}
    <Runs runs={data.runs} api={api} refresh={load} />
  </div>;
}

export function ProjectAutoReglue({ siteId, api }: { siteId: string; api: Api }) {
  const [expanded, setExpanded] = React.useState(false);
  return <section className="dataPanel"><div className="dataPanelHeader"><h2>Автопереклей проекта</h2><button className="button secondary compact" aria-expanded={expanded} onClick={() => setExpanded(v => !v)}>{expanded ? "Свернуть настройки" : "Настроить автопереклей"}</button></div>{expanded && <div className="dataPanelBody"><ProjectConfigEditor key={siteId} siteId={siteId} api={api} /></div>}</section>;
}

type Overview = { language_pool?: string[]; settings: GlobalConfig; projects: { id: string; name: string; geo: string; next_run_at?: string | null; config: Config }[]; runs: Run[] };
export function AutoReglueView({ api }: { api: Api }) {
  const [data, setData] = React.useState<Overview | null>(null); const [draft, setDraft] = React.useState<GlobalConfig | null>(null);
  const [selected, setSelected] = React.useState<string[]>([]); const [plans, setPlans] = React.useState<Plan[]>([]);
  const [busy, setBusy] = React.useState(false); const [error, setError] = React.useState("");
  const load = React.useCallback(async () => { const next = await api<Overview>("/auto-reglue"); setData(next); setDraft(old => old || next.settings); }, [api]);
  React.useEffect(() => { void load().catch(e => setError(errorText(e))); }, [load]);
  const pending = data?.runs.some(r => active.includes(r.status));
  React.useEffect(() => { if (!pending) return; const timer = setInterval(() => void load().catch(e => setError(errorText(e))), 5000); return () => clearInterval(timer); }, [load, pending]);
  async function perform(fn: () => Promise<void>) { setBusy(true); setError(""); try { await fn(); } catch (e) { setError(errorText(e)); } finally { setBusy(false); } }
  if (!data || !draft) return <p>{error || "Загружаем настройки…"}</p>;
  const value = draft;
  const dirty = JSON.stringify(value) !== JSON.stringify(data.settings);
  return <section className="viewStack"><section className="dataPanel"><div className="dataPanelHeader"><h2>Автопереклей — общие настройки</h2></div><div className="dataPanelBody autoReglueSettings">
    {error && <div className="notice" role="alert">{error}</div>}
    <p>Один запуск — один следующий неиспользованный Main для каждого выбранного проекта. Участвуют только проекты со статусом «Массовые действия» и сохранёнными настройками.</p>
    <label className="checkboxRow"><input type="checkbox" checked={draft.enabled} onChange={e => { setDraft({ ...draft, enabled: e.target.checked }); setPlans([]); }} /> Разрешить запуск автопереклеев</label>
    <AutomationRules value={draft} onChange={patch => { setDraft({ ...draft, ...patch }); setPlans([]); }} pool={data.language_pool || []} />
    <label>Максимум проектов за один запуск<input type="number" min={1} max={100} value={draft.max_projects} onChange={e => { setDraft({ ...draft, max_projects: Number(e.target.value) }); setPlans([]); }} /></label>
    <p className="muted">Массовые правила не применяются к проектам с персональным автопереклеем. Дроп для x-default задаётся в каждом проекте.</p>
    <button className="button secondary" disabled={busy || !dirty} onClick={() => void perform(async () => { const saved = await api<GlobalConfig>("/auto-reglue/settings", body("PUT", value)); setDraft(saved); setPlans([]); await load(); })}>Сохранить общие настройки</button>
    <h3>Проекты</h3>{!data.projects.length && <p>Нет проектов со статусом «Массовые действия». Статус никому не назначается автоматически.</p>}
    <div className="autoReglueProjects">{data.projects.map(site => <label className="checkboxRow" key={site.id}><input type="checkbox" checked={selected.includes(site.id)} disabled={!site.config.enabled || data.runs.some(r => r.site_id === site.id && active.includes(r.status))} onChange={e => { setSelected(v => e.target.checked ? [...v, site.id] : v.filter(id => id !== site.id)); setPlans([]); }} /><a href={`/project-redirects/${encodeURIComponent(site.name)}/`}>{site.name}</a><span>{site.geo || "GEO не задано"} · {site.config.enabled ? "Настроен" : "Нужно настроить в Переклее"}{site.next_run_at ? ` · Следующий запуск: ${new Date(site.next_run_at).toLocaleString("ru-RU")}` : ""}</span></label>)}</div>
    <button className="button secondary" disabled={busy || dirty || !value.enabled || !selected.length} onClick={() => void perform(async () => { setPlans([]); const next: Plan[] = []; for (const id of selected) { const plan = await api<Plan>(`/auto-reglue/projects/${id}/preview`, { method: "POST" }); next.push({ ...plan, requestId: crypto.randomUUID() }); } setPlans(next); })}>Подготовить планы ({selected.length})</button>
    {plans.map(plan => <PlanPreview key={plan.site_id} plan={plan} />)}
    {plans.length > 0 && <button className="button primary" disabled={busy || dirty} onClick={() => void perform(async () => { const result = await api<{ results: { error?: string }[] }>("/auto-reglue/start", body("POST", { items: plans.map(p => ({ site_id: p.site_id, request_id: p.requestId, preview_token: p.preview_token })) })); await load(); const failures = result.results.filter(r => r.error); if (failures.length) throw new Error(failures.map(r => r.error).join("; ")); setPlans([]); })}>Запустить группу ({plans.length})</button>}
    <Runs runs={data.runs} api={api} refresh={load} />
  </div></section></section>;
}
