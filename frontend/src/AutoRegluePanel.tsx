import React from "react";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type Config = { enabled: boolean; drop_domain: string; parent_kind: "drop" | "newreg"; newreg_domain: string; language: string; profile_id: string; variant: "current" | "provided" | "before" | "after"; fake_main_path: string };
type GlobalConfig = { enabled: boolean; auxiliary_hreflangs: string[]; max_projects: number };
type Template = { id: string; project: string; brand: string; geo: string; variants: Record<string, unknown> };
type Plan = { site_id: string; project: string; old_main: string; new_main: string; drop_domain: string; alternateMarkup: string; required_page_urls: string[]; preview_token: string; requestId: string };
type Run = { id: string; site_id: string; status: string; phase: string; message: string; plan: Plan };
type ProjectData = { config: Config; settings: GlobalConfig; eligible: boolean; geo: string; templates: Template[]; runs: Run[] };
const active = ["queued", "running", "waiting", "partial"];
const labels: Record<string, string> = { queued: "В очереди", running: "Выполняется", waiting: "Ожидает подтверждения", partial: "Нужна проверка результата", completed: "Завершён", failed: "Ошибка", cancelled: "Остановлен" };
const phases: Record<string, string> = { prepared: "Подготовлен", reserve: "Сохранение резерва", reglue: "Смена Main", alternates: "Обновление альтернейтов", completed: "Все этапы подтверждены" };
const errorText = (e: unknown) => e instanceof Error ? e.message : "Не удалось выполнить запрос";
const body = (method: string, value: unknown): RequestInit => ({ method, body: JSON.stringify(value) });

function PlanPreview({ plan }: { plan: Plan }) {
  return <div className="autoRegluePlan"><strong>{plan.project}</strong><p>{plan.old_main} → <b>{plan.new_main}</b></p><p>x-default: <b>{plan.drop_domain}</b></p>
    <pre>{plan.alternateMarkup}</pre>{plan.required_page_urls.length > 0 && <p className="muted">Перед сменой Main будут проверены страницы: {plan.required_page_urls.join(", ")}. Их нужно создать заранее.</p>}</div>;
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
  const template = data.templates.find(t => t.id === draft.profile_id);
  return <div className="autoReglueSettings">{error && <div className="notice" role="alert">{error}</div>}
    <p>GEO проекта: <b>{data.geo || "не задано"}</b>. Допуск: {data.eligible ? "Массовые действия" : "нужен статус «Массовые действия»"}.</p>
    {!data.settings.enabled && <p className="notice">Включите общие настройки в разделе «Автопереклей».</p>}
    <label className="checkboxRow"><input type="checkbox" checked={draft.enabled} onChange={e => change({ enabled: e.target.checked })} /> Участвует в автопереклеях</label>
    <div className="autoReglueFields">
      <label>Дроп для x-default<input value={draft.drop_domain} placeholder="example.com" onChange={e => change({ drop_domain: e.target.value })} /></label>
      <label>Язык проекта<input value={draft.language} placeholder="az" onChange={e => change({ language: e.target.value })} /></label>
      <label>Поддомены для нового Main<select value={draft.parent_kind} onChange={e => change({ parent_kind: e.target.value as Config["parent_kind"] })}><option value="drop">Поддомены дропа</option><option value="newreg">Поддомены новорега</option></select></label>
      {draft.parent_kind === "newreg" && <label>Родительский новорег<input value={draft.newreg_domain} placeholder="new-domain.com" onChange={e => change({ newreg_domain: e.target.value })} /></label>}
      <label>Схема альтернейтов<select value={draft.profile_id} onChange={e => { const t = data.templates.find(x => x.id === e.target.value); change({ profile_id: e.target.value, variant: (t ? Object.keys(t.variants).includes("after") ? "after" : Object.keys(t.variants)[0] : "current") as Config["variant"] }); }}><option value="">Текущая схема проекта</option>{data.templates.map(t => <option key={t.id} value={t.id}>{t.brand} · {t.geo} · {t.project}</option>)}</select></label>
      {template && <label>Версия схемы<select value={draft.variant} onChange={e => change({ variant: e.target.value as Config["variant"] })}>{Object.keys(template.variants).map(v => <option key={v} value={v}>{v === "after" ? "Схема стала" : v === "before" ? "Схема была" : "Предоставленная схема"}</option>)}</select></label>}
      <label>Путь копии главной для языка и GEO<input value={draft.fake_main_path} placeholder="/events/ — необязательно" onChange={e => change({ fake_main_path: e.target.value })} /></label>
    </div>
    <p className="muted">Берём следующий поддомен после текущего Main по порядку сетки, пропуская все бывшие Main. Дополнительные языки сохраняем, их адреса переносим на новый Main. x-default всегда ведёт на указанный дроп. Пустой путь сохраняет путь выбранного шаблона.</p>
    <div className="networkActions"><button className="button secondary" disabled={busy || !dirty} onClick={() => void perform(async () => { const saved = await api<Config>(`/auto-reglue/projects/${siteId}`, body("PUT", draft)); setDraft(saved); setPlan(null); await load(); })}>Сохранить настройки</button>
      <button className="button secondary" disabled={busy || dirty || !data.eligible || !draft.enabled || !data.settings.enabled || pending} onClick={() => void perform(async () => { const next = await api<Plan>(`/auto-reglue/projects/${siteId}/preview`, { method: "POST" }); setPlan({ ...next, requestId: crypto.randomUUID() }); })}>Подготовить переклей</button></div>
    {plan && <><PlanPreview plan={plan} /><button className="button primary" disabled={busy || dirty || pending} onClick={() => void perform(async () => { const result = await api<{ results: { error?: string }[] }>("/auto-reglue/start", body("POST", { items: [{ site_id: siteId, preview_token: plan.preview_token, request_id: plan.requestId }] })); if (result.results[0]?.error) throw new Error(result.results[0].error); setPlan(null); await load(); })}>Запустить автопереклей проекта</button></>}
    <Runs runs={data.runs} api={api} refresh={load} />
  </div>;
}

export function ProjectAutoReglue({ siteId, api }: { siteId: string; api: Api }) {
  const [expanded, setExpanded] = React.useState(false);
  return <section className="dataPanel"><div className="dataPanelHeader"><h2>Автопереклей проекта</h2><button className="button secondary compact" aria-expanded={expanded} onClick={() => setExpanded(v => !v)}>{expanded ? "Свернуть настройки" : "Настроить автопереклей"}</button></div>{expanded && <div className="dataPanelBody"><ProjectConfigEditor key={siteId} siteId={siteId} api={api} /></div>}</section>;
}

type Overview = { settings: GlobalConfig; projects: { id: string; name: string; geo: string; config: Config }[]; runs: Run[] };
export function AutoReglueView({ api }: { api: Api }) {
  const [data, setData] = React.useState<Overview | null>(null); const [draft, setDraft] = React.useState<GlobalConfig | null>(null);
  const [extras, setExtras] = React.useState(""); const [selected, setSelected] = React.useState<string[]>([]); const [plans, setPlans] = React.useState<Plan[]>([]);
  const [busy, setBusy] = React.useState(false); const [error, setError] = React.useState("");
  const load = React.useCallback(async () => { const next = await api<Overview>("/auto-reglue"); setData(next); setDraft(old => { if (!old) setExtras(next.settings.auxiliary_hreflangs.join(", ")); return old || next.settings; }); }, [api]);
  React.useEffect(() => { void load().catch(e => setError(errorText(e))); }, [load]);
  const pending = data?.runs.some(r => active.includes(r.status));
  React.useEffect(() => { if (!pending) return; const timer = setInterval(() => void load().catch(e => setError(errorText(e))), 5000); return () => clearInterval(timer); }, [load, pending]);
  async function perform(fn: () => Promise<void>) { setBusy(true); setError(""); try { await fn(); } catch (e) { setError(errorText(e)); } finally { setBusy(false); } }
  if (!data || !draft) return <p>{error || "Загружаем настройки…"}</p>;
  const value = { ...draft, auxiliary_hreflangs: extras.split(/[\s,;]+/).filter(Boolean) };
  const dirty = JSON.stringify(value) !== JSON.stringify(data.settings);
  return <section className="viewStack"><section className="dataPanel"><div className="dataPanelHeader"><h2>Автопереклей — общие настройки</h2></div><div className="dataPanelBody autoReglueSettings">
    {error && <div className="notice" role="alert">{error}</div>}
    <p>Один запуск — один следующий неиспользованный Main для каждого выбранного проекта. Участвуют только проекты со статусом «Массовые действия» и сохранёнными настройками.</p>
    <label className="checkboxRow"><input type="checkbox" checked={draft.enabled} onChange={e => { setDraft({ ...draft, enabled: e.target.checked }); setPlans([]); }} /> Разрешить запуск автопереклеев</label>
    <div className="autoReglueFields"><label>Дополнительные языки для всех проектов<input placeholder="en, tr, fr-AZ" value={extras} onChange={e => { setExtras(e.target.value); setPlans([]); }} /></label><label>Максимум проектов за один запуск<input type="number" min={1} max={100} value={draft.max_projects} onChange={e => { setDraft({ ...draft, max_projects: Number(e.target.value) }); setPlans([]); }} /></label></div>
    <p className="muted">Коды добавляются буквально, без подстановки GEO. Существующие дополнительные языки сохраняются. x-default задаётся отдельно для каждого проекта. Расписание не включено: запуск выполняется кнопкой.</p>
    <button className="button secondary" disabled={busy || !dirty} onClick={() => void perform(async () => { const saved = await api<GlobalConfig>("/auto-reglue/settings", body("PUT", value)); setDraft(saved); setExtras(saved.auxiliary_hreflangs.join(", ")); setPlans([]); await load(); })}>Сохранить общие настройки</button>
    <h3>Проекты</h3>{!data.projects.length && <p>Нет проектов со статусом «Массовые действия». Статус никому не назначается автоматически.</p>}
    <div className="autoReglueProjects">{data.projects.map(site => <label className="checkboxRow" key={site.id}><input type="checkbox" checked={selected.includes(site.id)} disabled={!site.config.enabled || data.runs.some(r => r.site_id === site.id && active.includes(r.status))} onChange={e => { setSelected(v => e.target.checked ? [...v, site.id] : v.filter(id => id !== site.id)); setPlans([]); }} /><a href={`/project-redirects/${encodeURIComponent(site.name)}/`}>{site.name}</a><span>{site.geo || "GEO не задано"} · {site.config.enabled ? "Настроен" : "Нужно настроить в Переклее"}</span></label>)}</div>
    <button className="button secondary" disabled={busy || dirty || !value.enabled || !selected.length} onClick={() => void perform(async () => { setPlans([]); const next: Plan[] = []; for (const id of selected) { const plan = await api<Plan>(`/auto-reglue/projects/${id}/preview`, { method: "POST" }); next.push({ ...plan, requestId: crypto.randomUUID() }); } setPlans(next); })}>Подготовить планы ({selected.length})</button>
    {plans.map(plan => <PlanPreview key={plan.site_id} plan={plan} />)}
    {plans.length > 0 && <button className="button primary" disabled={busy || dirty} onClick={() => void perform(async () => { const result = await api<{ results: { error?: string }[] }>("/auto-reglue/start", body("POST", { items: plans.map(p => ({ site_id: p.site_id, request_id: p.requestId, preview_token: p.preview_token })) })); await load(); const failures = result.results.filter(r => r.error); if (failures.length) throw new Error(failures.map(r => r.error).join("; ")); setPlans([]); })}>Запустить группу ({plans.length})</button>}
    <Runs runs={data.runs} api={api} refresh={load} />
  </div></section></section>;
}
