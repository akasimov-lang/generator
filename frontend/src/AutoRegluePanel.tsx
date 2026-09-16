import React from "react";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type Rules = { schedule_enabled: boolean; interval_days: number; scheme_mode: "preserve" | "add_auxiliary" | "base_only"; auxiliary_hreflangs: string[] };
type Config = Rules & { create_subdomains: boolean; create_fake_main: boolean; use_current_fake_main: boolean; subdomain_add_casino: boolean; subdomain_name_style: "mixed" | "joined" | "hyphen"; domain_layout: "subdomain_main" | "root_main"; scope: "mass" | "personal"; enabled: boolean; drop_domain: string; x_default_use_newreg: boolean; x_default_newreg_domain: string; parent_kind: "drop" | "newreg"; newreg_domain: string; language: string; profile_id: string; variant: "current" | "provided" | "before" | "after"; fake_main_path: string };
type DomainOptions = Pick<Config, "domain_layout" | "parent_kind" | "create_subdomains" | "create_fake_main" | "use_current_fake_main" | "subdomain_add_casino" | "subdomain_name_style" | "x_default_use_newreg">;
const defaultDomainOptions: DomainOptions = { domain_layout: "subdomain_main", parent_kind: "drop", create_subdomains: false, create_fake_main: false, use_current_fake_main: false, subdomain_add_casino: false, subdomain_name_style: "mixed", x_default_use_newreg: false };
type GlobalConfig = Rules & { enabled: boolean; max_projects: number; apply_domain_settings?: boolean; domain_settings?: DomainOptions };
type Template = { id: string; project: string; brand: string; geo: string; variants: Record<string, unknown> };
type Plan = { create_fake_main_path?: string | null; create_subdomain?: string | null; site_id: string; project: string; old_main: string; new_main: string; drop_domain: string; x_default_domain?: string; language_domain?: string; alternateMarkup: string; required_page_urls: string[]; added_hreflang?: string | null; pool_exhausted?: boolean; preview_token: string; requestId: string };
type Run = { id: string; site_id: string; status: string; phase: string; message: string; plan: Plan };
type ScheduleTask = { site_id: string; project: string; enabled: boolean; scope: string; interval_days: number; status: string; next_run_at?: string | null; url: string };
type ProjectData = { task?: ScheduleTask | null; next_run_at?: string | null; language_pool?: string[]; config: Config; settings: GlobalConfig; eligible: boolean; geo: string; templates: Template[]; runs: Run[] };
const active = ["queued", "running", "waiting", "partial"];
const labels: Record<string, string> = { queued: "В очереди", running: "Выполняется", waiting: "Ожидает подтверждения", partial: "Нужна проверка результата", completed: "Завершён", failed: "Ошибка", cancelled: "Остановлен" };
const phases: Record<string, string> = { prepared: "Подготовлен", create_fake_main: "Создание фейковой главной", fake_main_ready: "Проверка фейковой страницы", create_subdomains: "Создание поддомена", subdomain_ready: "Проверка готовности поддомена", reserve: "Сохранение резерва", reglue: "Смена Main", alternates: "Обновление альтернейтов", completed: "Все этапы подтверждены" };
const errorText = (e: unknown) => e instanceof Error ? e.message : "Не удалось выполнить запрос";
const body = (method: string, value: unknown): RequestInit => ({ method, body: JSON.stringify(value) });

function PlanPreview({ plan }: { plan: Plan }) {
  return <div className="autoRegluePlan"><strong>{plan.project}</strong><p>{plan.old_main} → <b>{plan.new_main}</b></p><p>x-default: <b>{plan.x_default_domain || plan.drop_domain}</b></p>
    {plan.create_fake_main_path && <p>Создать фейковую главную для схемы: <b>{plan.create_fake_main_path}</b>. Для этого запуска выбран новый свободный путь.</p>}
    {plan.create_subdomain && <p>Будет создан один поддомен: <b>{plan.create_subdomain}</b>. Смена Main начнётся после готовности HTTPS и страниц схемы.</p>}
    {plan.language_domain && <p>Домен языковых альтернейтов: <b>{plan.language_domain}</b></p>}{plan.added_hreflang && <p>Новый фейковый альтернейт: <b>{plan.added_hreflang}</b></p>}{plan.pool_exhausted && <p>Список языков исчерпан: схема сохраняется.</p>}<pre>{plan.alternateMarkup}</pre>{plan.required_page_urls.length > 0 && <p className="muted">Перед сменой Main будут проверены страницы: {plan.required_page_urls.join(", ")}. {plan.create_fake_main_path ? "Копия главной для языка-GEO будет создана автоматически; остальные страницы схемы должны существовать." : "Содержимое этих страниц нужно подготовить в проекте заранее."}</p>}</div>;
}

function FakeMainOptions({ value, change }: { value: { create_fake_main?: boolean; use_current_fake_main?: boolean }; change: (patch: { create_fake_main: boolean; use_current_fake_main: boolean }) => void }) {
  return <div className="networkSection"><h4>Фейковые внутренние страницы в альтернейтах</h4>
    <label className="checkboxRow"><input type="checkbox" checked={!value.create_fake_main && !value.use_current_fake_main} onChange={() => change({ create_fake_main: false, use_current_fake_main: false })} /> Без фейковых страниц — только URL домена или поддомена</label>
    <label className="checkboxRow"><input type="checkbox" checked={!!value.create_fake_main} onChange={e => change({ create_fake_main: e.target.checked, use_current_fake_main: false })} /> Создавать новый фейковый внутряк при каждом автопереклее</label>
    <label className="checkboxRow"><input type="checkbox" checked={!!value.use_current_fake_main} onChange={e => change({ create_fake_main: false, use_current_fake_main: e.target.checked })} /> Использовать текущий фейковый внутряк при всех автопереклеях</label>
    <p className="muted">Выберите один режим. Без фейковых страниц язык и язык-GEO ведут на одинаковый корневой URL. Новая страница: первый свободный путь /geo/, /geo1/…/geo10/, /geo-lang/. Для брендовых проектов также /бренд-geo/, /бренд-lang/, /бренд-casino-geo/, /бренд-casino-lang/. GEO, язык и бренд берутся из проекта; занятые фейковые и обычные страницы пропускаются. Текущая: используем currentFakeMain из кеша проекта без создания новой страницы.</p>
  </div>;
}

function AutomationRules({ value, onChange, pool }: { value: Rules; onChange: (patch: Partial<Rules>) => void; pool: string[] }) {
  const [languages, setLanguages] = React.useState((value.auxiliary_hreflangs || []).join(", "));
  return <div className="networkSection">
    <label className="checkboxRow"><input type="checkbox" checked={!!value.schedule_enabled} onChange={e => onChange({ schedule_enabled: e.target.checked })} /> Включить расписание автопереклеев</label>
    <label>Периодичность автопереклея<select value={value.interval_days ?? 0} onChange={e => onChange({ interval_days: Number(e.target.value) })}><option value={0}>Однократно</option>{[3, 4, 5, 7, 14].map(days => <option key={days} value={days}>Раз в {days} {days < 5 ? "дня" : "дней"}</option>)}</select></label>
    <p className="muted">В режиме «Однократно» выполняется один запуск без повторов. Повторное сохранение не запускает задачу заново. Сохранение включённого расписания создаёт задачу и сразу ставит первый переклей в очередь. Дальше запуски идут по сохранённому графику. Обновление страницы, перезапуск сервера и повторное сохранение не сбрасывают отсчёт. Изменение периода считается от последнего планового запуска. Незавершённый переклей блокирует следующий.</p>
    <label className="checkboxRow"><input type="checkbox" checked={value.scheme_mode === "add_auxiliary"} onChange={() => onChange({ scheme_mode: "add_auxiliary" })} /> Добавлять новый фейковый альтернейт при каждом переклее</label>
    <label className="checkboxRow"><input type="checkbox" checked={!value.scheme_mode || value.scheme_mode === "preserve"} onChange={() => onChange({ scheme_mode: "preserve" })} /> Сохранять схему: обновлять адреса и дроп в x-default</label>
    <label className="checkboxRow"><input type="checkbox" checked={value.scheme_mode === "base_only"} onChange={() => onChange({ scheme_mode: "base_only" })} /> Только базовые альтернейты — без фейковых языков и GEO</label>
    {value.scheme_mode === "base_only" && <div className="autoRegluePlan">
      <p>При переклее сохраняются ровно три ссылки. Остальные языковые альтернейты удаляются из разметки.</p>
      <ul><li><b>Язык проекта</b>, без GEO (например az) — главная страница языкового домена или поддомена.</li>
        <li><b>Язык-GEO</b> (например az-AZ) — тот же корневой URL. Фейковая страница добавляется только отдельной настройкой.</li>
        <li><b>x-default</b> — корневой дроп. При canonical на языковом домене выбирается неиспользованный дроп сетки; при canonical = x-default используется новый корневой Main. Новорег разрешается отдельным чекбоксом «Использовать новорег в x-default» внутри проекта.</li></ul>
      <p>Базовый пример для языка az и GEO AZ без фейковой страницы:</p>
      <pre>{'<link rel="alternate" hreflang="az" href="https://pinup-casino-az.clubheavenjax.com/" />\n<link rel="alternate" hreflang="az-AZ" href="https://pinup-casino-az.clubheavenjax.com/" />\n<link rel="alternate" hreflang="x-default" href="https://clubheavenjax.com/" />'}</pre>
      <p className="muted">Адреса в примере иллюстративные. Для запуска подставляются язык, GEO и выбранные домены проекта. Путь зависит только от отдельного режима фейковых страниц.</p>
    </div>}
    {value.scheme_mode !== "base_only" && <><label>Языки для новых фейковых альтернейтов<textarea rows={3} value={languages} onChange={e => { setLanguages(e.target.value); onChange({ auxiliary_hreflangs: e.target.value.split(/[\s,;]+/).filter(Boolean) }); }} /></label>
    <button type="button" className="button secondary compact" onClick={() => { setLanguages(pool.join(", ")); onChange({ auxiliary_hreflangs: pool }); }}>Заполнить языками ЕС и СНГ</button>
    <p className="muted">В режиме добавления берём один следующий неиспользованный код. При исчерпании списка сохраняем схему. Адреса ведут на языковой домен выбранной схемы, x-default — на выбранный корневой домен. Без фейковых страниц используются только корневые URL.</p></>}
  </div>;
}

function CommonDomainSettings({ value, change }: { value: GlobalConfig; change: (patch: Partial<GlobalConfig>) => void }) {
  const rules = value.domain_settings || defaultDomainOptions;
  const patch = (next: Partial<DomainOptions>) => change({ domain_settings: { ...rules, ...next } });
  const selectParent = (parent_kind: "drop" | "newreg", create_subdomains: boolean) => patch({ parent_kind, create_subdomains, ...(rules.domain_layout === "root_main" ? { x_default_use_newreg: parent_kind === "newreg" } : {}) });
  return <section className="networkSection"><h3>Общие параметры доменов и поддоменов</h3>
    <label className="checkboxRow"><input type="checkbox" checked={!!value.apply_domain_settings} onChange={e => change({ apply_domain_settings: e.target.checked })} /> Применять общую схему доменов ко всем участникам массового автопереклея</label>
    <p className="muted">При выключенном чекбоксе используются настройки доменов каждого проекта. При включённом — варианты ниже; персональные проекты всегда исключены. Родительские домены, бренд, GEO, язык и путь страницы берутся из проекта.</p>
    <fieldset disabled={!value.apply_domain_settings} className="autoReglueDomainOptions"><legend>Схема доменов</legend>
      <label className="checkboxRow"><input type="radio" name="global-domain-layout" checked={rules.domain_layout === "subdomain_main"} onChange={() => patch({ domain_layout: "subdomain_main" })} /> Canonical = языковые альтернейты; x-default отдельно</label>
      <label className="checkboxRow"><input type="radio" name="global-domain-layout" checked={rules.domain_layout === "root_main"} onChange={() => patch({ domain_layout: "root_main", x_default_use_newreg: rules.parent_kind === "newreg" })} /> Canonical = x-default; языковые альтернейты на поддомене</label>
      <FakeMainOptions value={rules} change={patch} />
      <h4>Источник поддомена</h4>
      <label className="checkboxRow"><input type="checkbox" checked={!rules.create_subdomains && rules.parent_kind === "drop"} onChange={() => selectParent("drop", false)} /> Использовать существующий поддомен дропа</label>
      <label className="checkboxRow"><input type="checkbox" checked={!rules.create_subdomains && rules.parent_kind === "newreg"} onChange={() => selectParent("newreg", false)} /> Использовать существующий поддомен новорега</label>
      <label className="checkboxRow"><input type="checkbox" checked={rules.create_subdomains && rules.parent_kind === "drop"} onChange={() => selectParent("drop", true)} /> Создавать новый поддомен дропа при каждом запуске</label>
      <label className="checkboxRow"><input type="checkbox" checked={rules.create_subdomains && rules.parent_kind === "newreg"} onChange={() => selectParent("newreg", true)} /> Создавать новый поддомен новорега при каждом запуске</label>
      <p className="muted">Выбирается один источник. В схеме Canonical = x-default меняется корневой домен, а поддомен используется в языковых альтернейтах.</p>
      <label className="checkboxRow"><input type="checkbox" checked={rules.x_default_use_newreg} onChange={e => patch({ x_default_use_newreg: e.target.checked, ...(rules.domain_layout === "root_main" ? { parent_kind: e.target.checked ? "newreg" : "drop" } : {}) })} /> Использовать новорег в x-default</label>
      <label className="checkboxRow"><input type="checkbox" disabled={!rules.create_subdomains} checked={rules.subdomain_add_casino} onChange={e => patch({ subdomain_add_casino: e.target.checked })} /> Добавлять casino к известным брендам</label>
      <label>Формат имён<select aria-label="Общий формат имён поддоменов" disabled={!rules.create_subdomains} value={rules.subdomain_name_style} onChange={e => patch({ subdomain_name_style: e.target.value as DomainOptions["subdomain_name_style"] })}><option value="mixed">Чередовать: с дефисами и без</option><option value="joined">Без дефисов</option><option value="hyphen">С дефисами</option></select></label>
      <p className="muted">Бренд: бренд-GEO, бренд-GEO-1…10, бренд-GEO-язык; опционально casino. Общие ключи: online-casino-GEO-язык, casino-online-GEO, casinos-top-GEO. Доступны слитные варианты. Один новый поддомен за запуск; занятые имена и AMP исключены.</p>
    </fieldset>
  </section>;
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

function ProjectConfigEditor({ siteId, api, onTask }: { siteId: string; api: Api; onTask: (task: ScheduleTask | null) => void }) {
  const [data, setData] = React.useState<ProjectData | null>(null); const [draft, setDraft] = React.useState<Config | null>(null);
  const [plan, setPlan] = React.useState<Plan | null>(null); const [busy, setBusy] = React.useState(false); const [error, setError] = React.useState("");
  const load = React.useCallback(async (force = false) => { const next = await api<ProjectData>(`/auto-reglue/projects/${siteId}`, force ? { cache: "no-store" } : undefined); setData(next); setDraft(old => old || next.config); onTask(next.task || null); }, [api, siteId, onTask]);
  React.useEffect(() => { void load().catch(e => setError(errorText(e))); }, [load]);
  const pending = data?.runs.some(r => active.includes(r.status));
  React.useEffect(() => { if (!pending) return; const timer = setInterval(() => void load(true).catch(e => setError(errorText(e))), 5000); return () => clearInterval(timer); }, [load, pending]);
  async function perform(fn: () => Promise<void>) { setBusy(true); setError(""); try { await fn(); } catch (e) { setError(errorText(e)); } finally { setBusy(false); } }
  if (!draft || !data) return <p>{error || "Загружаем настройки…"}</p>;
  const dirty = JSON.stringify(draft) !== JSON.stringify(data.config);
  const change = (patch: Partial<Config>) => {
    const next = { ...draft, ...patch };
    if (patch.scope !== undefined) next.schedule_enabled = patch.scope === "personal";
    next.scope = next.schedule_enabled ? "personal" : "mass";
    setDraft(next); setPlan(null);
  };
  const baseOnly = draft.scheme_mode === "base_only";
  const template = data.templates.find(t => t.id === draft.profile_id);
  return <div className="autoReglueSettings">{error && <div className="notice" role="alert">{error}</div>}
    <p>GEO проекта: <b>{data.geo || "не задано"}</b>. Допуск: {draft.scope === "personal" ? "Персональные настройки" : data.eligible ? "Массовые действия" : "нужен статус «Массовые действия»"}.</p>
    {draft.scope !== "personal" && !data.settings.enabled && <p className="notice">Глобальный автопереклей выключен. Запуск из настроек этого проекта доступен отдельно и использует только его собственные правила.</p>}
    <label className="checkboxRow"><input type="checkbox" checked={draft.scope === "personal"} onChange={e => change({ scope: e.target.checked ? "personal" : "mass" })} /> Персональный автопереклей — исключить проект из массовых запусков</label>
    {draft.scope === "personal" && <p className="notice">Персональное расписание имеет приоритет: проект исключён из глобальных запусков. Выключение персонального расписания после сохранения возвращает проект в массовый запуск при статусе «Массовые действия». Собственные настройки сохраняются.</p>}
    {draft.scope === "personal" ? <label className="checkboxRow"><input type="checkbox" checked={draft.enabled} onChange={e => change({ enabled: e.target.checked })} /> Участвует в автопереклеях</label> : <p className="muted">Участие в массовом запуске разрешает статус «Массовые действия». Отдельное разрешение внутри проекта не требуется.</p>}
    {draft.scope !== "personal" && data.settings.apply_domain_settings && <div className="notice"><p>Для массового запуска схема доменов, источник поддомена и формат имени берутся из общих настроек. Включение и сохранение персонального расписания исключает проект из глобальных запусков. При выключенном персональном расписании проект участвует по общему расписанию; собственные настройки остаются сохранёнными.</p>
      <label>Дроп проекта для общих правил<input value={draft.drop_domain} onChange={e => change({ drop_domain: e.target.value })} /></label>
      <label>Новорег проекта для общих правил<input value={draft.newreg_domain} onChange={e => change({ newreg_domain: e.target.value })} /></label>
      <label>Новорег x-default для общих правил<input value={draft.x_default_newreg_domain || ""} onChange={e => change({ x_default_newreg_domain: e.target.value })} /></label>
      <p>Заполните адреса, которые требуются выбранной общей схеме. Для корневого Main и базового x-default домены выбираются из сетки автоматически.</p>
    </div>}
    <h3>Соотношение canonical и альтернейтов</h3>
    <label className="checkboxRow"><input type="radio" name={`domain-layout-${siteId}`} checked={draft.domain_layout === "root_main"} onChange={() => change({ domain_layout: "root_main" })} /> Canonical = x-default; языковые альтернейты на поддомене</label>
    <label className="checkboxRow"><input type="radio" name={`domain-layout-${siteId}`} checked={draft.domain_layout !== "root_main"} onChange={() => change({ domain_layout: "subdomain_main" })} /> Canonical = домен языковых альтернейтов; x-default отдельно</label>
    <div className="networkSection">
      <h3>Создание поддоменов при автопереклее</h3>
      <label className="checkboxRow"><input type="checkbox" checked={!!draft.create_subdomains && draft.parent_kind === "drop"} onChange={e => change({ create_subdomains: e.target.checked, parent_kind: "drop", ...(draft.domain_layout === "root_main" ? { x_default_use_newreg: false } : {}) })} /> Переклей на поддомен дропа (создание нового поддомена)</label>
      <p className="muted">брендgeo.дроп · брендgeo1…10.дроп · брендgeoязык.дроп. Например: pincoaz.example.com, pincoaz1.example.com, pincoazaz.example.com.</p>
      <label className="checkboxRow"><input type="checkbox" checked={!!draft.create_subdomains && draft.parent_kind === "newreg"} onChange={e => change({ create_subdomains: e.target.checked, parent_kind: "newreg", ...(draft.domain_layout === "root_main" ? { x_default_use_newreg: true } : {}) })} /> Переклей на поддомен новорега (создание нового поддомена)</label>
      <p className="muted">брендgeo.новорег · брендgeo1…10.новорег · брендgeoязык.новорег. Например: pincoaz.new-domain.com, pincoaz1.new-domain.com, pincoazaz.new-domain.com.</p>
      <label className="checkboxRow"><input type="checkbox" disabled={!draft.create_subdomains} checked={!!draft.subdomain_add_casino} onChange={e => change({ subdomain_add_casino: e.target.checked })} /> Добавлять варианты со словом casino для известных брендов: pincocasinoaz.example.com</label>
      <label>Формат имени поддомена<select aria-label="Формат имени поддомена" disabled={!draft.create_subdomains} value={draft.subdomain_name_style || "mixed"} onChange={e => change({ subdomain_name_style: e.target.value as Config["subdomain_name_style"] })}><option value="mixed">Чередовать: с дефисами и без</option><option value="joined">Без дефисов</option><option value="hyphen">С дефисами</option></select></label>
      <p className="muted">С дефисами: pinco-az, pinco-az-1…10, pinco-az-az; с casino: pinco-casino-az, pinco-casino-az-1…10, pinco-casino-az-az. Без дефисов: pincoaz, pincoaz1…10, pincoazaz.</p>
      <p className="muted">Общие ключи: online-casino-geo-lang, casino-online-geo, casinos-top-geo; без дефисов: onlinecasinogeolang, casinoonlinegeo, casinostopgeo. Например: online-casino-az-az.example.com или onlinecasinoazaz.example.com. Шаблон выбирается автоматически по бренду проекта; дополнительная опция casino применяется только к известным брендам.</p>
      <p className="muted">Один запуск создаёт один поддомен существующего корня. GEO и язык берутся из проекта, бренд — из поля «Бренд». Имена проверяются по кешу, актуальной сетке и истории. В смешанном режиме порядок вариантов различается по проектам. Выбранное имя фиксируется в плане и не меняется при повторе задачи. Для «Общих ключей» используются отдельные шаблоны. Если имена закончились, запуск останавливается с объяснением. AMP исключены.</p>
      {draft.domain_layout === "root_main" && draft.create_subdomains && <p>В схеме Canonical = x-default новый поддомен используется для языковых альтернейтов, а Main — следующий корневой домен.</p>}
    </div>
    {baseOnly && draft.domain_layout !== "root_main" && <p className="notice">x-default выбирается по порядку из неиспользованных дропов сетки. Исключаем историю Main, x-default и остальных альтернейтов. Тип домена задаётся во вкладке «Сетка». При разрешении новорега выбираем неиспользованный новорег. Если кандидата нет, переклей не запускается.</p>}
    {draft.domain_layout === "root_main" && <p className="notice">При каждом запуске меняем корневой Main. Берём следующий домен типа «Дроп» (или «Новорег» при включённом чекбоксе ниже), который не был Main, и его неиспользованный поддомен из сетки либо создаём новый при включённой настройке. Типы задаются во вкладке «Сетка».</p>}
    <label className="checkboxRow"><input type="checkbox" checked={!!draft.x_default_use_newreg} onChange={e => change({ x_default_use_newreg: e.target.checked })} /> Использовать новорег в x-default</label>
    <div className="autoReglueFields">
      {!baseOnly && draft.x_default_use_newreg && draft.domain_layout !== "root_main" && <label>Новорег для x-default<input value={draft.x_default_newreg_domain || ""} onChange={e => change({ x_default_newreg_domain: e.target.value })} placeholder="new-domain.com" /></label>}
      {draft.domain_layout !== "root_main" && (!baseOnly || draft.parent_kind === "drop") && <label>{baseOnly ? "Родительский дроп для Main" : "Дроп для x-default"}<input value={draft.drop_domain} placeholder="example.com" onChange={e => change({ drop_domain: e.target.value })} /></label>}
      <label>Язык проекта (если не задан в кэше)<input value={draft.language} placeholder="az" onChange={e => change({ language: e.target.value })} /></label>
      {draft.domain_layout !== "root_main" && <label>Поддомены для нового Main<select value={draft.parent_kind} onChange={e => change({ parent_kind: e.target.value as Config["parent_kind"] })}><option value="drop">Поддомены дропа</option><option value="newreg">Поддомены новорега</option></select></label>}
      {draft.domain_layout !== "root_main" && draft.parent_kind === "newreg" && <label>Родительский новорег<input value={draft.newreg_domain} placeholder="new-domain.com" onChange={e => change({ newreg_domain: e.target.value })} /></label>}
      <label>Схема альтернейтов<select value={draft.profile_id} onChange={e => { const t = data.templates.find(x => x.id === e.target.value); change({ profile_id: e.target.value, variant: (t ? Object.keys(t.variants).includes("after") ? "after" : Object.keys(t.variants)[0] : "current") as Config["variant"] }); }}><option value="">Текущая схема проекта</option>{data.templates.map(t => <option key={t.id} value={t.id}>{t.brand} · {t.geo} · {t.project}</option>)}</select></label>
      {template && <label>Версия схемы<select value={draft.variant} onChange={e => change({ variant: e.target.value as Config["variant"] })}>{Object.keys(template.variants).map(v => <option key={v} value={v}>{v === "after" ? "Схема стала" : v === "before" ? "Схема была" : "Предоставленная схема"}</option>)}</select></label>}
      <FakeMainOptions value={draft} change={change} />
    </div>
    <p className="muted">Расписание ниже — персональное. При его выключении проект со статусом «Массовые действия» возвращается в глобальный автопереклей. Выключение общего расписания не выключает персональное.</p>
    <AutomationRules key="personal-rules" value={draft} onChange={change} pool={data.language_pool || []} />
    {data.next_run_at && <p>Следующий запуск: <b>{new Date(data.next_run_at).toLocaleString("ru-RU")}</b></p>}
    {draft.domain_layout !== "root_main" && !draft.create_subdomains && <p className="muted">Берём следующий поддомен после текущего Main по порядку сетки, пропуская все бывшие Main. Дополнительные языки сохраняем, их адреса переносим на новый Main. x-default определяется выбранным режимом: в базовой схеме — неиспользованный домен сетки. Фейковый путь добавляется только в отдельно выбранном режиме; без него используются корневые URL.</p>}
    <p className="muted">Запуск из настроек проекта выполняет автопереклей по сохранённым правилам этого проекта. Глобальные правила и расписание не применяются; этот запуск не включает расписание.</p>
    <div className="networkActions"><button className="button secondary" disabled={busy || !dirty} onClick={() => void perform(async () => { const saved = await api<Config>(`/auto-reglue/projects/${siteId}`, body("PUT", draft)); setDraft(saved); setPlan(null); await load(); })}>Сохранить настройки</button>
      <button className="button secondary" disabled={busy || dirty || pending} onClick={() => void perform(async () => { const next = await api<Plan>(`/auto-reglue/projects/${siteId}/preview?scope=project`, { method: "POST" }); setPlan({ ...next, requestId: crypto.randomUUID() }); })}>Подготовить переклей</button></div>
    {plan && <><PlanPreview plan={plan} /><button className="button primary" disabled={busy || dirty || pending} onClick={() => void perform(async () => { const result = await api<{ results: { error?: string }[] }>("/auto-reglue/start", body("POST", { scope: "project", items: [{ site_id: siteId, preview_token: plan.preview_token, request_id: plan.requestId }] })); if (result.results[0]?.error) throw new Error(result.results[0].error); setPlan(null); await load(); })}>Запустить автопереклей проекта</button></>}
    <Runs runs={data.runs} api={api} refresh={load} />
  </div>;
}

export function ProjectAutoReglue({ siteId, api }: { siteId: string; api: Api }) {
  const [task, setTask] = React.useState<ScheduleTask | null>(null);
  return <section className="projectAutoReglueCard">
    {task && <div className="notice autoReglueTaskNotice" role="status">Задача автопереклея проекта сохранена. <a href={task.url}>Открыть задачу автопереклея →</a></div>}
    <section className="dataPanel"><div className="dataPanelHeader"><h2>Автопереклей проекта</h2></div><div className="dataPanelBody"><ProjectConfigEditor key={siteId} siteId={siteId} api={api} onTask={setTask} /></div></section>
  </section>;
}

type Overview = { tasks?: ScheduleTask[]; language_pool?: string[]; settings: GlobalConfig; projects: { id: string; name: string; geo: string; next_run_at?: string | null; config: Config }[]; runs: Run[] };
export function AutoReglueView({ api }: { api: Api }) {
  const [data, setData] = React.useState<Overview | null>(null); const [draft, setDraft] = React.useState<GlobalConfig | null>(null);
  const [selected, setSelected] = React.useState<string[]>([]); const [plans, setPlans] = React.useState<Plan[]>([]);
  const [busy, setBusy] = React.useState(false); const [error, setError] = React.useState("");
  const load = React.useCallback(async () => { const projectId = new URLSearchParams(window.location.search).get("project_id"); const next = await api<Overview>(`/auto-reglue${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`); setData(next); setDraft(old => old || next.settings); }, [api]);
  React.useEffect(() => { void load().catch(e => setError(errorText(e))); }, [load]);
  const pending = data?.runs.some(r => active.includes(r.status));
  React.useEffect(() => { if (!pending) return; const timer = setInterval(() => void load().catch(e => setError(errorText(e))), 5000); return () => clearInterval(timer); }, [load, pending]);
  const taskFocused = React.useRef(false);
  React.useEffect(() => {
    if (taskFocused.current || !data?.tasks?.length) return;
    const target = document.getElementById(window.location.hash.slice(1));
    if (target) { target.scrollIntoView({ block: "start" }); taskFocused.current = true; }
  }, [data?.tasks]);
  async function perform(fn: () => Promise<void>) { setBusy(true); setError(""); try { await fn(); } catch (e) { setError(errorText(e)); } finally { setBusy(false); } }
  if (!data || !draft) return <p>{error || "Загружаем настройки…"}</p>;
  const value = draft;
  const dirty = JSON.stringify(value) !== JSON.stringify(data.settings);
  return <section className="viewStack">{!!data.tasks?.length && <section className="dataPanel"><div className="dataPanelBody"><h2>Задачи автопереклея</h2>{data.tasks.map(task => <article className="autoReglueRun autoReglueScheduleTask" id={`auto-task-${task.site_id}`} key={task.site_id}><strong>{task.project}</strong><p>{task.scope === "personal" ? "Персональное расписание" : "Глобальное расписание"} · {task.interval_days === 0 ? "Однократно" : `Раз в ${task.interval_days} дней`}</p><p>{task.status === "disabled" ? "Расписание выключено" : task.status === "completed" ? "Однократный запуск обработан — результат ниже в истории запусков" : "Задача сохранена"}{task.next_run_at ? ` · Следующий запуск: ${new Date(task.next_run_at).toLocaleString("ru-RU")}` : ""}</p><a href={`/project-auto-reglue/${encodeURIComponent(task.project)}/`}>Открыть настройки проекта</a></article>)}</div></section>}<section className="dataPanel"><div className="dataPanelHeader"><h2>Автопереклей — общие настройки</h2></div><div className="dataPanelBody autoReglueSettings">
    {error && <div className="notice" role="alert">{error}</div>}
    <p>Один запуск — один следующий неиспользованный Main для каждого выбранного проекта. Участвуют только проекты со статусом «Массовые действия» и сохранёнными настройками.</p>
    <label className="checkboxRow"><input type="checkbox" checked={draft.enabled} onChange={e => { setDraft({ ...draft, enabled: e.target.checked }); setPlans([]); }} /> Разрешить запуск автопереклеев</label>
    <AutomationRules value={draft} onChange={patch => { setDraft({ ...draft, ...patch }); setPlans([]); }} pool={data.language_pool || []} />
    <CommonDomainSettings value={draft} change={patch => { setDraft({ ...draft, ...patch }); setPlans([]); }} />
    <label className="autoReglueBatchLimit">Максимум проектов за один запуск<input type="number" min={1} max={100} value={draft.max_projects} onChange={e => { setDraft({ ...draft, max_projects: Number(e.target.value) }); setPlans([]); }} /></label>
    {draft.interval_days === 0 && <p className="muted">Однократный автоматический запуск обработает все настроенные проекты со статусом «Массовые действия», кроме проектов с включённым персональным расписанием. Лимит определяет размер порции: остальные проекты будут обработаны следующими порциями, каждый один раз.</p>}
    <p className="muted">Массовые правила не применяются к проектам с персональным автопереклеем. Дроп для x-default задаётся в каждом проекте.</p>
    <button className="button secondary" disabled={busy || !dirty} onClick={() => void perform(async () => { const saved = await api<GlobalConfig>("/auto-reglue/settings", body("PUT", value)); setDraft(saved); setPlans([]); await load(); })}>Сохранить общие настройки</button>
    <h3>Проекты</h3>{!data.projects.length && <p>Нет проектов со статусом «Массовые действия». Статус никому не назначается автоматически.</p>}
    <div className="autoReglueProjects">{data.projects.map(site => <label className="checkboxRow" key={site.id}><input type="checkbox" checked={selected.includes(site.id)} disabled={data.runs.some(r => r.site_id === site.id && active.includes(r.status))} onChange={e => { setSelected(v => e.target.checked ? [...v, site.id] : v.filter(id => id !== site.id)); setPlans([]); }} /><a href={`/project-auto-reglue/${encodeURIComponent(site.name)}/`}>{site.name}</a><span>{site.geo || "GEO не задано"} · Допущен по статусу «Массовые действия»{site.next_run_at ? ` · Следующий запуск: ${new Date(site.next_run_at).toLocaleString("ru-RU")}` : ""}</span></label>)}</div>
    <button className="button secondary" disabled={busy || dirty || !value.enabled || !selected.length} onClick={() => void perform(async () => { setPlans([]); const next: Plan[] = []; for (const id of selected) { const plan = await api<Plan>(`/auto-reglue/projects/${id}/preview`, { method: "POST" }); next.push({ ...plan, requestId: crypto.randomUUID() }); } setPlans(next); })}>Подготовить планы ({selected.length})</button>
    {plans.map(plan => <PlanPreview key={plan.site_id} plan={plan} />)}
    {plans.length > 0 && <button className="button primary" disabled={busy || dirty} onClick={() => void perform(async () => { const result = await api<{ results: { error?: string }[] }>("/auto-reglue/start", body("POST", { items: plans.map(p => ({ site_id: p.site_id, request_id: p.requestId, preview_token: p.preview_token })) })); await load(); const failures = result.results.filter(r => r.error); if (failures.length) throw new Error(failures.map(r => r.error).join("; ")); setPlans([]); })}>Запустить группу ({plans.length})</button>}
    <Runs runs={data.runs} api={api} refresh={load} />
  </div></section></section>;
}
