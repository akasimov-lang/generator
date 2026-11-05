import { AutomaticActions } from "./AutomaticActions";
import { Bot, Scissors, AlignLeft, ArrowLeftRight, Globe2, ListChecks, WandSparkles } from "lucide-react";
import React from "react";
import {TransferProgress} from "./TransferProgress";
import { TemplateCombobox } from "./TemplateCombobox";
import type { MassActionFilter, MassActionSelection } from "./massActionScope";
import { MASS_ACTION_GEOS } from "./massActionScope";
import { createVisiblePoll, createCoalescedLoader } from "./visiblePoll";
import { MassReglueReports } from "./MassReglueReports";
import { contentLabels, contentActionDescription, contentBatchPayload, contentPending, headingActionOptions, type ContentAction, type HeadingAction } from "./contentActions";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type Rules = { schedule_enabled: boolean; interval_days: number; scheme_mode: "preserve" | "add_auxiliary" | "base_only" | "clean" | "locale_base"; auxiliary_hreflangs: string[] };
type Config = Rules & { create_subdomains: boolean; create_fake_main: boolean; use_current_fake_main: boolean; subdomain_add_casino: boolean; subdomain_name_style: "mixed" | "joined" | "hyphen"; domain_layout: "subdomain_main" | "root_main"; scope: "mass" | "personal"; enabled: boolean; drop_domain: string; x_default_use_newreg: boolean; x_default_newreg_domain: string; parent_kind: "drop" | "newreg"; newreg_domain: string; language: string; profile_id: string; variant: "current" | "provided" | "before" | "after"; fake_main_path: string };
type DomainOptions = Pick<Config, "domain_layout" | "parent_kind" | "create_subdomains" | "create_fake_main" | "use_current_fake_main" | "subdomain_add_casino" | "subdomain_name_style" | "x_default_use_newreg">;
const defaultDomainOptions: DomainOptions = { domain_layout: "subdomain_main", parent_kind: "drop", create_subdomains: false, create_fake_main: false, use_current_fake_main: false, subdomain_add_casino: false, subdomain_name_style: "mixed", x_default_use_newreg: false };
type MainTargetMode = "legacy" | "newreg" | "drop" | "mixed";
type GlobalConfig = Rules & { title_h1_rewrite_percent?:number; main_target_mode?: MainTargetMode; newreg_subdomain_share?: boolean; drop_subdomain_share?: boolean; selection_filter?: MassActionFilter | null; execution_mode?: "within_network" | "cross_network" | "transfer_only"; enabled: boolean; max_projects: number; apply_domain_settings?: boolean; domain_settings?: DomainOptions };
type Template = { id: string; project: string; brand: string; geo: string; variants: Record<string, unknown> };
type Plan = { reserve_pool_id?:string; main_target_kind?:string; parent_domain?:string; fallback_reason?:string; local_target?:boolean; use_selected_reserve?: boolean; manual_action?:string; brand?:string; domain_errors?:import("./TransferProgress").TransferRun["plan"]["domain_errors"]; replacement_pending?:boolean; geo?: string; execution_mode?: string; rollback_of?: string; rollback_run_id?: string; rolled_back_at?: string; domains?: { domain: string; domain_type: string }[]; source_before?: { domains: string[] }; source_after?: { domains: string[] }; target_before?: { domains: string[] }; target_after?: { domains: string[] }; transfer_not_before?: string; batch_id?: string; source_count?: number; target_count?: number; balance_mode?: string; source_project?: string; added_at?: string; elapsed_seconds?: number; alternates_before?: { markup: string; enabled: boolean }; alternates_after?: { markup: string; enabled: boolean }; canonicalFakeMainMarkup?: string | null; create_fake_main_path?: string | null; create_subdomain?: string | null; site_id: string; project: string; old_main: string; new_main: string; drop_domain: string; x_default_domain?: string; language_domain?: string; alternateMarkup: string; required_page_urls: string[]; added_hreflang?: string | null; pool_exhausted?: boolean; preview_token: string; requestId: string };
type Run = { domain_progress?: import("./TransferProgress").TransferRun["domain_progress"]; id: string; site_id: string; status: string; phase: string; message: string; plan: Plan };
type ScheduleTask = { site_id: string; project: string; enabled: boolean; scope: string; interval_days: number; status: string; next_run_at?: string | null; url: string };
type ProjectData = { participation: boolean; task?: ScheduleTask | null; next_run_at?: string | null; language_pool?: string[]; config: Config; settings: GlobalConfig; eligible: boolean; geo: string; templates: Template[]; runs: Run[] };
const active = ["planned", "queued", "running", "waiting", "partial"];
const labels: Record<string, string> = { planned: "Запланирован в группе", queued: "В очереди", running: "Выполняется", waiting: "Ожидает подтверждения", partial: "Нужна проверка результата", completed: "Завершён", failed: "Ошибка", cancelled: "Остановлен" };
const phases: Record<string, string> = { cross_create_fake_main: "Создание фейкового внутряка", cross_delete_domain: "Извлечение из исходной сетки", cross_create_domains: "Добавление в новую сетку", cross_reserve: "Сохранение резерва", cross_reglue: "Смена Main", cross_alternates: "Обновление альтернейтов", transfer_delete: "Извлечение доменов", transfer_create: "Добавление доменов", prepared: "Подготовлен", create_fake_main: "Создание фейковой главной", fake_main_ready: "Проверка фейковой страницы", create_subdomains: "Создание поддомена", subdomain_ready: "Проверка готовности поддомена", reserve: "Сохранение резерва", reglue: "Смена Main", alternates: "Обновление альтернейтов", completed: "Все этапы подтверждены" };
const errorText = (e: unknown) => e instanceof Error ? e.message : "Не удалось выполнить запрос";
const body = (method: string, value: unknown): RequestInit => ({ method, body: JSON.stringify(value) });

function PlanPreview({ plan }: { plan: Plan }) {
  if (plan.execution_mode === "transfer_only") return <div className="autoRegluePlan"><strong>{plan.rollback_of ? "Откат переноса" : "Перенос без переклея"}</strong><p>{plan.source_project} → {plan.project}</p><ul>{plan.domains?.map(item => <li key={item.domain}><b>{item.domain}</b> · {item.domain_type === "drop" ? "Дроп" : "Новорег"}</li>)}</ul>{plan.source_after && <p>Источник: {plan.source_before?.domains.length} → {plan.source_after.domains.length} доменов. Получатель: {plan.target_before?.domains.length} → {plan.target_after?.domains.length}.</p>}{plan.rolled_back_at && <p>Откат выполнен: {new Date(plan.rolled_back_at).toLocaleString("ru-RU")}</p>}</div>;
  return <div className="autoRegluePlan"><strong>{plan.project}</strong><p>{plan.old_main} → <b>{plan.new_main}</b></p>{(plan.x_default_domain || plan.drop_domain) && <p>x-default: <b>{plan.x_default_domain || plan.drop_domain}</b></p>}{plan.reserve_pool_id && <p>Домен из общей базы резервов будет добавлен в сетку и назначен Main.</p>}{plan.use_selected_reserve && <p>Переклей на выбранный резерв своей сетки. Перенос из другой сетки не требуется.</p>}{!plan.use_selected_reserve && !plan.local_target && plan.source_project && <p>Перенос из сетки <b>{plan.source_project}</b> → <b>{plan.project}</b>; домен станет Main. {plan.source_count !== undefined && <>Размеры сеток: {plan.source_count} → {plan.target_count}. {plan.balance_mode === "peer_exchange" ? "Обмен между сетками со свободными доменами." : "Из большей сетки в меньшую."}</>}</p>}{plan.added_at && <p>{plan.use_selected_reserve ? "Резерв в сетке с" : "Добавлен в сетку"}: {new Date(plan.added_at).toLocaleString("ru-RU")}</p>}{plan.transfer_not_before && <p>Повторный перенос не раньше: {new Date(plan.transfer_not_before).toLocaleString("ru-RU")}</p>}{plan.elapsed_seconds !== undefined && <p>Время переноса и переклея: {Math.round(plan.elapsed_seconds)} сек.</p>}{plan.alternates_before && <details><summary>Альтернейты: было / {plan.alternates_after ? "стало" : "планируется"}</summary><p>Было · {plan.alternates_before.enabled ? "включены" : "выключены"}</p><pre>{plan.alternates_before.markup || "Пусто"}</pre><p>{plan.alternates_after ? "Стало · " + (plan.alternates_after.enabled ? "включены" : "выключены") : "Планируется"}</p><pre>{(plan.alternates_after?.markup ?? plan.alternateMarkup) || "Пусто"}</pre></details>}
    {plan.main_target_kind && <p>Тип Main: <b>{({newreg:"Новорег",drop:"Дроп",sub_newreg:"Поддомен новорега",sub_drop:"Поддомен дропа"} as Record<string,string>)[plan.main_target_kind]}</b>{plan.parent_domain && <> · Родитель: {plan.parent_domain}</>}</p>}
    {plan.fallback_reason && <p role="note">{plan.fallback_reason}</p>}
    {plan.create_fake_main_path && <p>Создать и выбрать действующий фейковый внутряк: <b>{plan.create_fake_main_path}</b>. Для этого запуска выбран новый свободный путь.</p>}
    {plan.canonicalFakeMainMarkup && <p>Canonical главной и фейк-внутряка: <code>{plan.canonicalFakeMainMarkup.replace("{{settings.canon}}", plan.new_main)}</code></p>}
    {plan.create_subdomain && <p>Будет создан один поддомен: <b>{plan.create_subdomain}</b>. Смена Main начнётся после готовности HTTPS и страниц схемы.</p>}
    {plan.language_domain && <p>Домен языковых альтернейтов: <b>{plan.language_domain}</b></p>}{plan.added_hreflang && <p>Новый фейковый альтернейт: <b>{plan.added_hreflang}</b></p>}{plan.pool_exhausted && <p>Список языков исчерпан: схема сохраняется.</p>}<pre>{plan.alternateMarkup || "Альтернейты пустые"}</pre>{(plan.required_page_urls || []).length > 0 && <p className="muted">Перед сменой Main будут проверены страницы: {plan.required_page_urls.join(", ")}. {plan.create_fake_main_path ? "Копия главной для языка-GEO будет создана автоматически; остальные страницы схемы должны существовать." : "Содержимое этих страниц нужно подготовить в проекте заранее."}</p>}</div>;
}

function FakeMainOptions({ value, change }: { value: { create_fake_main?: boolean; use_current_fake_main?: boolean }; change: (patch: { create_fake_main: boolean; use_current_fake_main: boolean }) => void }) {
  return <div className="networkSection"><h4>Фейковые внутренние страницы в альтернейтах</h4>
    <label className="checkboxRow"><input type="checkbox" checked={!value.create_fake_main && !value.use_current_fake_main} onChange={() => change({ create_fake_main: false, use_current_fake_main: false })} /> Без фейковых страниц — только URL домена или поддомена</label>
    <label className="checkboxRow"><input type="checkbox" checked={!!value.create_fake_main} onChange={e => change({ create_fake_main: e.target.checked, use_current_fake_main: false })} /> Создавать новый фейковый внутряк при каждом автопереклее</label>
    <label className="checkboxRow"><input type="checkbox" checked={!!value.use_current_fake_main} onChange={e => change({ create_fake_main: false, use_current_fake_main: e.target.checked })} /> Использовать текущий фейковый внутряк при всех автопереклеях</label>
    <p className="muted">Выберите один режим. Для новой внутренней страницы подбираем свободный путь по бренду, языку и GEO без цифр. Цифры разрешены только когда в текущей сетке уже больше десяти различных внутренних путей с цифрами. Занятые и ранее использованные адреса пропускаются. При одной ссылке alternate она ведёт на новый внутряк, canonical — на корень Main. Режим текущей страницы использует уже выбранный внутряк без создания нового.</p>
  </div>;
}

function AutomationRules({ value, onChange, pool, cross = false, mass = false }: { cross?: boolean; mass?: boolean; value: Rules; onChange: (patch: Partial<Rules>) => void; pool: string[] }) {
  const [languages, setLanguages] = React.useState((value.auxiliary_hreflangs || []).join(", "));
  return <div className="networkSection">
    <label className="checkboxRow"><input type="checkbox" checked={!!value.schedule_enabled} onChange={e => onChange({ schedule_enabled: e.target.checked })} /> Включить расписание автопереклеев</label>
    <label>Периодичность автопереклея<select value={value.interval_days ?? 0} onChange={e => onChange({ interval_days: Number(e.target.value) })}><option value={0}>Однократно</option>{[3, 4, 5, 7, 14].map(days => <option key={days} value={days}>Раз в {days} {days < 5 ? "дня" : "дней"}</option>)}</select></label>
    <p className="muted">В режиме «Однократно» выполняется один запуск без повторов. Повторное сохранение не запускает задачу заново. Сохранение включённого расписания создаёт задачу и сразу ставит первый переклей в очередь. Дальше запуски идут по сохранённому графику. Обновление страницы, перезапуск сервера и повторное сохранение не сбрасывают отсчёт. Изменение периода считается от последнего планового запуска. Незавершённый переклей блокирует следующий.</p>
    <label className="checkboxRow"><input type="checkbox" checked={value.scheme_mode === "clean"} onChange={() => onChange({ scheme_mode: "clean" })} /> Чистый альтернейт — очистить альтернейты при переклее</label>
    {mass && <label className="checkboxRow"><input type="checkbox" checked={value.scheme_mode === "locale_base"} onChange={e => onChange({ scheme_mode: e.target.checked ? "locale_base" : "preserve" })} /> Базовый Alternate по языку и GEO — с новым фейковым внутряком</label>}
    {mass && value.scheme_mode === "locale_base" && <p className="muted">Полностью заменяем разметку тремя ссылками: язык проекта и x-default → корень нового Main, язык-GEO → новый свободный фейковый внутряк. Для PL: pl / pl-PL; для CZ: cs / cs-CZ; для остальных GEO используем язык проекта. Новый внутряк становится текущим; canonical обновляется. История хранит альтернейты и внутряк «было → стало».</p>}
    {!cross && <label className="checkboxRow"><input type="checkbox" checked={value.scheme_mode === "add_auxiliary"} onChange={() => onChange({ scheme_mode: "add_auxiliary" })} /> Добавлять новый фейковый альтернейт при каждом переклее</label>}
    <label className="checkboxRow"><input type="checkbox" checked={!value.scheme_mode || value.scheme_mode === "preserve"} onChange={() => onChange({ scheme_mode: "preserve" })} /> {cross ? "Сохранять схему: заменить адрес прежнего Main новым" : "Сохранять схему: обновлять адреса и дроп в x-default"}</label>
    {!cross && <label className="checkboxRow"><input type="checkbox" checked={value.scheme_mode === "base_only"} onChange={() => onChange({ scheme_mode: "base_only" })} /> Только базовые альтернейты — без фейковых языков и GEO</label>}
    {value.scheme_mode === "base_only" && <div className="autoRegluePlan">
      <p>При переклее сохраняются ровно три ссылки. Остальные языковые альтернейты удаляются из разметки.</p>
      <ul><li><b>Язык проекта</b>, без GEO (например az) — главная страница языкового домена или поддомена.</li>
        <li><b>Язык-GEO</b> (например az-AZ) — тот же корневой URL. Фейковая страница добавляется только отдельной настройкой.</li>
        <li><b>x-default</b> — корневой дроп. При canonical на языковом домене выбирается неиспользованный дроп сетки; при canonical = x-default используется новый корневой Main. Новорег разрешается отдельным чекбоксом «Использовать новорег в x-default» внутри проекта.</li></ul>
      <p>Базовый пример для языка az и GEO AZ без фейковой страницы:</p>
      <pre>{'<link rel="alternate" hreflang="az" href="https://pinup-casino-az.clubheavenjax.com/" />\n<link rel="alternate" hreflang="az-AZ" href="https://pinup-casino-az.clubheavenjax.com/" />\n<link rel="alternate" hreflang="x-default" href="https://clubheavenjax.com/" />'}</pre>
      <p className="muted">Адреса в примере иллюстративные. Для запуска подставляются язык, GEO и выбранные домены проекта. Путь зависит только от отдельного режима фейковых страниц.</p>
    </div>}
    {!cross && value.scheme_mode !== "base_only" && value.scheme_mode !== "clean" && value.scheme_mode !== "locale_base" && <><label>Языки для новых фейковых альтернейтов<textarea rows={3} value={languages} onChange={e => { setLanguages(e.target.value); onChange({ auxiliary_hreflangs: e.target.value.split(/[\s,;]+/).filter(Boolean) }); }} /></label>
    <button type="button" className="button secondary compact" onClick={() => { setLanguages(pool.join(", ")); onChange({ auxiliary_hreflangs: pool }); }}>Заполнить языками ЕС и СНГ</button>
    <p className="muted">В режиме добавления берём один следующий неиспользованный код. При исчерпании списка сохраняем схему. Адреса ведут на языковой домен выбранной схемы, x-default — на выбранный корневой домен. Без фейковых страниц используются только корневые URL.</p></>}
  </div>;
}

function MainTargetSettings({value,change,count}:{value:GlobalConfig;change:(patch:Partial<GlobalConfig>)=>void;count:number}) {
 const mode=value.main_target_mode||"legacy";
 const newreg=mode==="mixed"?Math.round(count/2):mode==="newreg"?count:0;
 const drop=count-newreg;
 const subNew=value.newreg_subdomain_share?Math.min(newreg,Math.round(count/10)):0;
 const subDrop=value.drop_subdomain_share?Math.min(drop,Math.round(count/10)):0;
 return <section className="networkSection" aria-label="Типы Main в массовом цикле"><h3>На какие домены переклеивать</h3>
  <TemplateCombobox label="Тип доменов для переклея" value={mode} options={[{value:"legacy",label:"Текущие правила — выбранный резерв или свободный новорег"},{value:"newreg",label:"Только новореги"},{value:"drop",label:"Только дропы"},{value:"mixed",label:"Смешанный цикл — 50% новореги / 50% дропы"}]} onChange={next=>change({main_target_mode:next as MainTargetMode,newreg_subdomain_share:next!=="legacy"&&next!=="drop"&&!!value.newreg_subdomain_share,drop_subdomain_share:next!=="legacy"&&next!=="newreg"&&!!value.drop_subdomain_share})}/>
  <label className="checkboxRow"><input type="checkbox" checked={!!value.newreg_subdomain_share} disabled={mode==="legacy"||mode==="drop"} onChange={e=>change({newreg_subdomain_share:e.target.checked})}/>10% переклеев — на поддомен новорега</label>
  <label className="checkboxRow"><input type="checkbox" checked={!!value.drop_subdomain_share} disabled={mode==="legacy"||mode==="newreg"} onChange={e=>change({drop_subdomain_share:e.target.checked})}/>10% переклеев — на поддомен дропа</label>
  {mode!=="legacy"&&<p role="status">План для {count} проектов: новореги — {newreg-subNew}, дропы — {drop-subDrop}, поддомены новорегов — {subNew}, поддомены дропов — {subDrop}.</p>}
  <label>Переписывать Title и H1, %<input type="number" min={0} max={100} step={1} value={value.title_h1_rewrite_percent??20} onChange={e=>change({title_h1_rewrite_percent:Number(e.target.value)})}/></label>
  <p className="muted">Доли считаются от числа проектов в цикле и округляются по математическим правилам: 0,5 вверх. Поддомены входят в долю своего типа. Для них выбирается свободное имя на подходящем родителе своей сетки. Если подходящего домена нет — свободный новорег из большей сетки того же бренда и GEO; замена отмечается в плане. Выбранный резерв сохраняет приоритет, если соответствует доле; несовместимый резерв нужно изменить или снять.</p>
 </section>;
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
      <p className="muted">Чередуем варианты бренд-GEO, GEO-бренд, бренд-язык и бренд с casino. Для общих ключей используем варианты casino и online-casino с языком и GEO. Имена — без цифр, пока в сетке не станет больше десяти различных поддоменов с цифрами. Занятые имена и AMP исключены.</p>
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
    {runs.map(run => <div className="autoReglueRun" key={run.id}><strong>{run.plan.project} · {labels[run.status] || run.status}</strong><span>{phases[run.phase] || run.phase}</span><p>{run.message}</p>{(run.plan.new_main || run.plan.domains?.length) && <details><summary>Результат и история изменений</summary><PlanPreview plan={run.plan} /></details>}
      {run.status === "completed" && run.plan.execution_mode === "transfer_only" && !run.plan.rollback_of && !run.plan.rolled_back_at && <button className="button secondary compact" disabled={!!busy || !!run.plan.rollback_run_id} onClick={() => void control(run.id, "rollback")}>{run.plan.rollback_run_id ? "Откат запущен" : "Откатить перенос"}</button>}
      {active.includes(run.status) && <div className="networkActions"><button className="button secondary compact" disabled={!!busy} onClick={() => void control(run.id, "resume")}>Проверить результат и продолжить</button><button className="button secondary compact" disabled={!!busy} onClick={() => void control(run.id, "cancel")}>Остановить</button></div>}
    </div>)}{runs.some(r => active.includes(r.status)) && <p className="muted">Остановка не отменяет уже подтверждённую смену Main. При неизвестном результате повторная запись не отправляется.</p>}</section>;
}

function ProjectConfigEditor({ siteId, api, onTask }: { siteId: string; api: Api; onTask: (task: ScheduleTask | null) => void }) {
  const [data, setData] = React.useState<ProjectData | null>(null); const [draft, setDraft] = React.useState<Config | null>(null);
  const [plan, setPlan] = React.useState<Plan | null>(null); const [busy, setBusy] = React.useState(false); const [error, setError] = React.useState("");
  const load = React.useCallback(async (force = false) => { const next = await api<ProjectData>(`/auto-reglue/projects/${siteId}`, force ? { cache: "no-store" } : undefined); setData(next); setDraft(old => old || next.config); onTask(next.task || null); }, [api, siteId, onTask]);
  React.useEffect(() => { void load().catch(e => setError(errorText(e))); }, [load]);
  const pending = data?.runs.some(r => active.includes(r.status)||r.plan.replacement_pending);
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
    <div className="networkMarkupHeading"><h3>Участие в массовых и автоматических действиях</h3>
      <button type="button" role="switch" className="networkMarkupSwitch" aria-label="Участие в массовых и автоматических действиях" aria-checked={data.participation !== false} disabled={busy}
        onClick={() => void perform(async () => {
          const saved = await api<{reglue_participation: boolean}>(`/auto-reglue/projects/${siteId}/participation`, {method: "PATCH", headers: {"Content-Type": "application/json"}, body: JSON.stringify({enabled: data.participation === false})});
          setData(current => current ? {...current, participation: saved.reglue_participation} : current);
        })}><span aria-hidden="true" /></button><span>{data.participation !== false ? "Включено" : "Выключено"}</span>
    </div>
    <details><summary>Настройки автопереклея</summary>
    <p>GEO проекта: <b>{data.geo || "не задано"}</b>. Допуск: {draft.scope === "personal" ? "Персональные настройки" : data.eligible ? "Массовые действия" : "нужен статус «Массовые действия»"}.</p>
    {draft.scope !== "personal" && !data.settings.enabled && <p className="notice">Глобальный автопереклей выключен. Запуск из настроек этого проекта доступен отдельно и использует только его собственные правила.</p>}
    <label className="checkboxRow"><input type="checkbox" checked={draft.scope === "personal"} onChange={e => change({ scope: e.target.checked ? "personal" : "mass" })} /> Персональный автопереклей — исключить проект из массовых запусков</label>
    {draft.scope === "personal" && <p className="notice">Персональное расписание имеет приоритет: проект исключён из глобальных запусков. Выключение персонального расписания после сохранения возвращает проект в массовый запуск при статусе «Массовые действия». Собственные настройки сохраняются.</p>}
    {draft.scope === "personal" ? <label className="checkboxRow"><input type="checkbox" checked={draft.enabled} onChange={e => change({ enabled: e.target.checked })} /> Участвует в автопереклеях</label> : <p className="muted">Для массового запуска необходимы статус «Массовые действия» и включённый переключатель участия в автодействиях.</p>}
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
      <p className="muted">Поддомен дропа: например pincoaz.example.com, azpinco.example.com или pinco-casino.example.com.</p>
      <label className="checkboxRow"><input type="checkbox" checked={!!draft.create_subdomains && draft.parent_kind === "newreg"} onChange={e => change({ create_subdomains: e.target.checked, parent_kind: "newreg", ...(draft.domain_layout === "root_main" ? { x_default_use_newreg: true } : {}) })} /> Переклей на поддомен новорега (создание нового поддомена)</label>
      <p className="muted">Поддомен новорега: например pincoaz.new-domain.com, azpinco.new-domain.com или pinco-casino.new-domain.com.</p>
      <label className="checkboxRow"><input type="checkbox" disabled={!draft.create_subdomains} checked={!!draft.subdomain_add_casino} onChange={e => change({ subdomain_add_casino: e.target.checked })} /> Добавлять варианты со словом casino для известных брендов: pincocasinoaz.example.com</label>
      <label>Формат имени поддомена<select aria-label="Формат имени поддомена" disabled={!draft.create_subdomains} value={draft.subdomain_name_style || "mixed"} onChange={e => change({ subdomain_name_style: e.target.value as Config["subdomain_name_style"] })}><option value="mixed">Чередовать: с дефисами и без</option><option value="joined">Без дефисов</option><option value="hyphen">С дефисами</option></select></label>
      <p className="muted">С дефисами: pinco-az, az-pinco, pinco-casino-az. Без дефисов: pincoaz, azpinco, pincocasino. Цифры разрешены только при наличии больше десяти разных поддоменов с цифрами в текущей сетке.</p>
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
    <Runs runs={data.runs} api={api} refresh={load} /></details>
  </div>;
}

export function ProjectAutoReglue({ siteId, api }: { siteId: string; api: Api }) {
  const [task, setTask] = React.useState<ScheduleTask | null>(null);
  return <section className="projectAutoReglueCard">
    {task && <div className="notice autoReglueTaskNotice" role="status">Задача автопереклея проекта сохранена. <a href={task.url}>Открыть задачу автопереклея →</a></div>}
    <section className="dataPanel"><div className="dataPanelHeader"><h2>Автодействия</h2></div><div className="dataPanelBody"><AutomaticActions siteId={siteId} api={api}/><ProjectConfigEditor key={siteId} siteId={siteId} api={api} onTask={setTask} /></div></section>
  </section>;
}

type Overview = { tasks?: ScheduleTask[]; language_pool?: string[]; settings: GlobalConfig; projects: { id: string; name: string; geo: string; next_run_at?: string | null; config: Config }[]; runs: Run[] };
export function AutoReglueView({ api, renderReport, onNetworksChanged, refreshToken = 0 }: { api: Api; refreshToken?:number; onNetworksChanged?: () => Promise<void>; renderReport?: (onScopeChange: (selection: MassActionSelection) => void, selected: string[], onSelection: (ids: string[]) => void, moveActions: React.ReactNode, headerContainer:HTMLElement|null) => React.ReactNode }) {
  const [headerContainer,setHeaderContainer]=React.useState<HTMLElement|null>(null);
  const [controlsOpen, setControlsOpen] = React.useState(!renderReport);
  const [contentAction, setContentAction] = React.useState<ContentAction | null>(null);
  const [reportScope, setReportScope] = React.useState<MassActionSelection>({ filter: null, site_ids: [] });
  const scopeRef = React.useRef(reportScope);
  const selectScope = React.useCallback((selection: MassActionSelection) => {
    const changed = JSON.stringify(scopeRef.current.filter) !== JSON.stringify(selection.filter);
    scopeRef.current = selection;
    setReportScope(previous => JSON.stringify(previous) === JSON.stringify(selection) ? previous : selection);
    setSelected(previous => changed ? selection.site_ids : previous.filter(id => selection.site_ids.includes(id)));
    setPlans([]); setSkipped([]);
  }, []);
  const selectFromReport = React.useCallback((ids: string[]) => {
    const next = ids.filter(id => scopeRef.current.site_ids.includes(id));
    setSelected(previous => JSON.stringify(previous) === JSON.stringify(next) ? previous : next);
  }, []);
  const [data, setData] = React.useState<Overview | null>(null); const [draft, setDraft] = React.useState<GlobalConfig | null>(null);
  const [selected, setSelected] = React.useState<string[]>([]); const [plans, setPlans] = React.useState<Plan[]>([]);
  const [busy, setBusy] = React.useState(false); const [error, setError] = React.useState("");
  const [skipped, setSkipped] = React.useState<{ project: string; error: string }[]>([]);
  const [moveResult, setMoveResult] = React.useState<Run | null>(null);
  const [moveRuns,setMoveRuns]=React.useState<Run[]>([]);
  const moveReceipt = React.useRef<{ signature: string; id: string } | null>(null);
  const observedRuns = React.useRef<Map<string,string>|null>(null);
  React.useEffect(() => {
    if (!data) return;
    const previous = observedRuns.current;
    const next = new Map(data.runs.map(run => [run.id, JSON.stringify([run.status,run.phase,run.domain_progress?.map(domain=>domain.stage)])]));
    observedRuns.current = next;
    // Initial history and changing the selection do not change the site inventory.
    if (previous && data.runs.some(run => reportScope.site_ids.includes(run.site_id) && previous.get(run.id) !== next.get(run.id))) {
      void onNetworksChanged?.().catch(error=>setError(errorText(error)));
    }
  },[data,reportScope.site_ids,onNetworksChanged]);
  const selectedSignature = JSON.stringify(selected);
  const selectedRef = React.useRef(selectedSignature); selectedRef.current = selectedSignature;
  React.useEffect(() => { setPlans([]); setSkipped([]); }, [selectedSignature]);
  const load = React.useMemo(() => createCoalescedLoader(async () => { const projectId = new URLSearchParams(window.location.search).get("project_id"); const next = await api<Overview>(`/auto-reglue${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`); setData(next); setDraft(old => old || next.settings); }), [api]);
  React.useEffect(() => { void load().catch(e => setError(errorText(e))); }, [load]);
  const lastRefreshToken = React.useRef(refreshToken);
  React.useEffect(() => {
    if (lastRefreshToken.current === refreshToken) return;
    lastRefreshToken.current = refreshToken;
    void load(true).catch(e => setError(errorText(e)));
  }, [load,refreshToken]);
  const pollingPending = data?.runs.some(run => ["planned","queued","running","waiting"].includes(run.status));
  React.useEffect(() => createVisiblePoll({load:()=>load(),intervalMs:pollingPending?2000:30000,onError:e=>setError(errorText(e))}), [load,pollingPending]);
  const taskFocused = React.useRef(false);
  React.useEffect(() => {
    if (taskFocused.current || !data?.tasks?.length) return;
    const target = document.getElementById(window.location.hash.slice(1));
    if (target) { target.scrollIntoView({ block: "start" }); taskFocused.current = true; }
  }, [data?.tasks]);
  async function movePlus2(count: 1 | 2) {
    if (!reportScope.filter || selected.length < 2) return;
    setMoveResult(null);
    const payload = { filter: reportScope.filter, site_ids: selected, count };
    const signature = JSON.stringify(payload);
    if (!moveReceipt.current || moveReceipt.current.signature !== signature) moveReceipt.current = { signature, id: crypto.randomUUID() };
    await perform(async () => {
      const run = await api<Run & {runs?:Run[]}>("/auto-reglue/move-plus2", body("POST", { ...payload, request_id: moveReceipt.current!.id }));
      setMoveResult(run);setMoveRuns(run.runs||[run]); moveReceipt.current = null;
      await load(true);
    });
  }
  async function perform(fn: () => Promise<void>) { setBusy(true); setError(""); try { await fn(); } catch (e) { setError(errorText(e)); } finally { setBusy(false); } }
  if (!data || !draft) return <p>{error || "Загружаем настройки…"}</p>;
  const value = draft;
  const filter = reportScope.filter;
  const dirty = JSON.stringify(value) !== JSON.stringify(data.settings);
  const scopeKey = JSON.stringify(filter);
  const filterDirty = JSON.stringify(value.selection_filter || null) !== scopeKey;
  const visibleProjectIds = new Set(data.projects.filter(site => MASS_ACTION_GEOS.includes((site.geo || "").toUpperCase().split(/[-_]/).at(-1) || "")).map(site => site.id));
  const visibleTasks = data.tasks?.filter(task => visibleProjectIds.has(task.site_id) && (!filter || reportScope.site_ids.includes(task.site_id))) || [];
  const visibleRuns = data.runs.filter(run => filter ? reportScope.site_ids.includes(run.site_id) : visibleProjectIds.has(run.site_id) || MASS_ACTION_GEOS.includes(run.plan.geo || ""));
  const latestTransfer=filter ? visibleRuns.find(r=>r.plan.manual_action==="move_plus2" || r.plan.execution_mode==="transfer_only") : undefined;
  const liveRoot=latestTransfer?.plan.batch_id || latestTransfer?.id;
  const liveTransfers=liveRoot ? visibleRuns.filter(r=>r.id===liveRoot || r.plan.batch_id===liveRoot) : [];
  const moveButtons = <span style={{ display: "inline-flex", gap: 6 }} aria-label="Перенос новорегов">{([2, 1] as const).map(count => <button key={count} type="button" className="button secondary compact" title={`Перенести ${count} новорега из большей сетки в меньшую без смены Main`} disabled={busy || !filter || selected.length < 2 || visibleRuns.some(run => active.includes(run.status))} onClick={() => void movePlus2(count)}>Move +{count}</button>)}</span>;
  return <section className="viewStack"><div ref={setHeaderContainer}/><div className="autoReglueActionBar" aria-label="Массовые действия"><button type="button" onClick={()=>window.location.assign("/auto-reglue/pilot")}><Bot size={18}/><span>Auto Pilot</span></button><button type="button" aria-pressed={!contentAction && draft.execution_mode === "cross_network"} onClick={() => { setContentAction(null); setControlsOpen(true); setDraft({ ...draft, execution_mode: "cross_network", scheme_mode: ["clean", "locale_base"].includes(draft.scheme_mode) ? draft.scheme_mode : "preserve" }); setPlans([]); }}><Globe2 size={18} /><span>Перекрёстный автопереклей</span></button><button type="button" aria-pressed={!contentAction && draft.execution_mode === "transfer_only"} onClick={() => { setContentAction(null); setControlsOpen(true); setDraft({ ...draft, execution_mode: "transfer_only", schedule_enabled: false }); setPlans([]); }}><ArrowLeftRight size={18} /><span>Обменять домены между сетками</span></button><button type="button" aria-pressed={contentAction === "meta_headings"} onClick={() => setContentAction("meta_headings")}><WandSparkles size={18} /><span>Переписать мета и заголовки</span></button><button type="button" aria-pressed={contentAction === "paragraphs"} onClick={() => setContentAction("paragraphs")}><AlignLeft size={18} /><span>Переписать абзацы</span></button><button type="button" aria-pressed={contentAction === "trim_50"} onClick={() => setContentAction("trim_50")}><Scissors size={18} /><span>Обрезать 50% контента</span></button><button type="button" aria-pressed={contentAction === "trim_99"} onClick={() => setContentAction("trim_99")}><Scissors size={18} /><span>Обрезать 99% контента</span></button><small><ListChecks size={16} />Выбрано: {selected.length}</small></div>{!renderReport && moveButtons}{error && <p role="alert">{error}</p>}{!!liveTransfers.length && <TransferProgress runs={liveTransfers} />}{contentAction ? <BulkContentDrafts key={`${scopeKey}:${contentAction}`} api={api} action={contentAction} selected={selected} filter={filter} /> : null}<details className="autoReglueControlDetails" open={controlsOpen} onToggle={event => setControlsOpen(event.currentTarget.open)} hidden={!!contentAction}><summary>Настройки, планы и история запусков</summary>{!!visibleTasks.length && <section className="dataPanel"><div className="dataPanelBody"><h2>Задачи автопереклея</h2>{visibleTasks.map(task => <article className="autoReglueRun autoReglueScheduleTask" id={`auto-task-${task.site_id}`} key={task.site_id}><strong>{task.project}</strong><p>{task.scope === "personal" ? "Персональное расписание" : "Глобальное расписание"} · {task.interval_days === 0 ? "Однократно" : `Раз в ${task.interval_days} дней`}</p><p>{task.status === "disabled" ? "Расписание выключено" : task.status === "completed" ? "Однократный запуск обработан — результат ниже в истории запусков" : "Задача сохранена"}{task.next_run_at ? ` · Следующий запуск: ${new Date(task.next_run_at).toLocaleString("ru-RU")}` : ""}</p><a href={`/project-auto-reglue/${encodeURIComponent(task.project)}/`}>Открыть настройки проекта</a></article>)}</div></section>}<section className="dataPanel"><div className="dataPanelHeader"><h2>Автопереклей — общие настройки</h2></div><div className="dataPanelBody autoReglueSettings">
    <p>Один запуск — один следующий неиспользованный Main для каждого выбранного проекта. Участвуют только проекты со статусом «Массовые действия» и сохранёнными настройками.</p>
    <label className="checkboxRow"><input type="checkbox" checked={draft.enabled} onChange={e => { setDraft({ ...draft, enabled: e.target.checked }); setPlans([]); }} /> Разрешить запуск автопереклеев</label>
    <TemplateCombobox label="Режим массового переклея" value={draft.execution_mode || "within_network"} options={[{ value: "within_network", label: "Внутри сетки" }, { value: "cross_network", label: "Перекрёстный — между сетками бренда и GEO" }, { value: "transfer_only", label: "Обменять домены между сетками — без переклея" }]} onChange={value => { setDraft({ ...draft, execution_mode: value as GlobalConfig["execution_mode"], scheme_mode: value === "cross_network" && !["clean", "locale_base"].includes(draft.scheme_mode) ? "preserve" : draft.scheme_mode, schedule_enabled: value === "transfer_only" ? false : draft.schedule_enabled }); setPlans([]); }} />
    {draft.execution_mode === "cross_network" && <p>Только проекты одного бренда и GEO со статусом «Массовые действия». Если выбран разрешённый резерв, сетка переклеивается на него. Если резерв в БАН, выбирается разрешённый новорег из другой сетки того же бренда и GEO независимо от её размера. Если резерва нет, тип домена определяется настройкой цикла ниже. В текущих правилах переносится доступный новорег. Резервные домены не извлекаются. Из больших сеток новореги распределяются в меньшие; крупные сетки также получают по одному домену через обмен, когда у мелких нет свободных доменов. Встречный перенос A → B и B → A запрещён. При трёх и более сетках возможна передача по кругу; сетка без свободных доменов только получает. За массовый запуск: до 10 извлечений из сетки и не более одного добавления в сетку. Main, имена проектов Webdev, AMP и домены с БАН исключены из переноса. Поддомены создаются отдельно по включённым долям. Месячное ограничение относится только к текущему Main; остальные свободные домены не блокируются по дате добавления или переноса. Сначала подтверждаются извлечения группы, затем добавление и смена Main.</p>}
    {draft.execution_mode === "transfer_only" && <p>Выберите одну принимающую сетку. Из более крупной сетки того же бренда и GEO переносится до двух свободных доменов: один дроп и один новорег. Если одного типа не хватает — используем другой. Main и альтернейты сохраняются. История и откат доступны в запуске.</p>}
    {draft.execution_mode === "cross_network" && <MainTargetSettings value={draft} count={selected.length} change={patch=>{setDraft({...draft,...patch});setPlans([]);}}/>}
    {draft.execution_mode !== "transfer_only" && <AutomationRules mass cross={draft.execution_mode === "cross_network"} value={draft} onChange={patch => { setDraft({ ...draft, ...patch }); setPlans([]); }} pool={data.language_pool || []} />}
    {(draft.execution_mode || "within_network") === "within_network" && <CommonDomainSettings value={draft} change={patch => { setDraft({ ...draft, ...patch }); setPlans([]); }} />}
    {draft.execution_mode !== "transfer_only" && <label className="autoReglueBatchLimit">Максимум проектов за один запуск<input type="number" min={1} max={100} value={draft.max_projects} onChange={e => { setDraft({ ...draft, max_projects: Number(e.target.value) }); setPlans([]); }} /></label>}
    {draft.execution_mode !== "transfer_only" && draft.interval_days === 0 && <p className="muted">Однократный автоматический запуск обработает только настроенные проекты сохранённого фильтра «Бренд + GEO», кроме проектов с включённым персональным расписанием. Лимит определяет размер порции: остальные проекты будут обработаны следующими порциями, каждый один раз.</p>}
    <p className="muted">Массовые правила не применяются к проектам с персональным автопереклеем. {draft.scheme_mode === "locale_base" ? "Базовый Alternate использует новый Main в x-default и создаёт новый внутряк независимо от настройки текущей фейковой страницы." : "Дроп для x-default задаётся в каждом проекте."}</p>
    <button className="button secondary" disabled={busy || !dirty && !filterDirty || value.enabled && value.schedule_enabled && !filter} onClick={() => void perform(async () => { const saved = await api<GlobalConfig>("/auto-reglue/settings", body("PUT", { ...value, selection_filter: filter })); setDraft(saved); setPlans([]); await load(true); })}>Сохранить общие настройки</button>
    <h3>Проекты</h3>{!data.projects.length && <p>Нет проектов со статусом «Массовые действия». Статус никому не назначается автоматически.</p>}
    {!renderReport && <div className="autoReglueProjects">{data.projects.map(site => <label className="checkboxRow" key={site.id}><input type="checkbox" checked={selected.includes(site.id)} disabled={data.runs.some(r => r.site_id === site.id && active.includes(r.status))} onChange={e => { setSelected(v => e.target.checked ? draft.execution_mode === "transfer_only" ? [site.id] : [...v, site.id] : v.filter(id => id !== site.id)); setPlans([]); }} /><a href={`/project-auto-reglue/${encodeURIComponent(site.name)}/`}>{site.name}</a><span>{site.geo || "GEO не задано"} · Допущен по статусу «Массовые действия»{site.next_run_at ? ` · Следующий запуск: ${new Date(site.next_run_at).toLocaleString("ru-RU")}` : ""}</span></label>)}</div>}
    <button className="button secondary" disabled={busy || dirty || !value.enabled || !selected.length || !filter} onClick={() => void perform(async () => { setPlans([]); setSkipped([]); if (!filter) throw new Error("Выберите бренд и GEO."); if (value.execution_mode === "transfer_only" && selected.length !== 1) throw new Error("Выберите одну принимающую сетку: не более двух доменов за нажатие."); if (value.execution_mode === "cross_network") { const batch = await api<{ batch_id: string; plans: Plan[]; skipped: { project: string; error: string }[] }>("/auto-reglue/preview-batch", body("POST", { site_ids: selected, filter })); if (JSON.stringify(scopeRef.current.filter) !== scopeKey || selectedRef.current !== selectedSignature) throw new Error("Фильтр изменился. Подготовьте планы заново."); setPlans(batch.plans.map(plan => ({ ...plan, requestId: crypto.randomUUID() }))); setSkipped(batch.skipped); return; } const next: Plan[] = []; for (const id of selected) { const plan = await api<Plan>(`/auto-reglue/projects/${id}/preview`, body("POST", { filter })); next.push({ ...plan, requestId: crypto.randomUUID() }); } if (JSON.stringify(scopeRef.current.filter) !== scopeKey || selectedRef.current !== selectedSignature) throw new Error("Фильтр изменился. Подготовьте планы заново."); setPlans(next); })}>Подготовить планы ({selected.length})</button>
    {skipped.length > 0 && <details><summary>Пропущено проектов: {skipped.length}</summary>{skipped.map(item => <p key={item.project}><b>{item.project}</b>: {item.error}</p>)}</details>}
    {plans.some(plan=>plan.main_target_kind)&&<p role="status">Фактически подготовлено: {plans.length}. Новореги — {plans.filter(p=>p.main_target_kind==="newreg").length}, дропы — {plans.filter(p=>p.main_target_kind==="drop").length}, поддомены новорегов — {plans.filter(p=>p.main_target_kind==="sub_newreg").length}, поддомены дропов — {plans.filter(p=>p.main_target_kind==="sub_drop").length}. Замен из-за нехватки или БАН — {plans.filter(p=>p.fallback_reason).length}.</p>}
    {plans.map(plan => <PlanPreview key={plan.site_id} plan={plan} />)}
    {plans.length > 0 && <button className="button primary" disabled={busy || dirty || !filter || plans.some(plan => !selected.includes(plan.site_id))} onClick={() => void perform(async () => { const result = await api<{ results: { error?: string }[] }>("/auto-reglue/start", body("POST", { filter, report_id: plans[0]?.requestId, batch_id: plans[0]?.batch_id, items: plans.map(p => ({ site_id: p.site_id, request_id: p.requestId, preview_token: p.preview_token })) })); await load(true); const failures = result.results.filter(r => r.error); if (failures.length) throw new Error(failures.map(r => r.error).join("; ")); setPlans([]); })}>Запустить группу ({plans.length})</button>}
    <Runs runs={visibleRuns} api={api} refresh={()=>load(true)} />
  </div></section></details>{renderReport?.(selectScope, selected, selectFromReport, moveButtons,headerContainer)}<MassReglueReports api={api} filter={filter} onChanged={onNetworksChanged} revision={JSON.stringify(data.runs.map(run => [run.id, run.status, run.phase]))} /></section>;
}


type ContentResult = { site_id: string; project: string; draft_id?: string; status?: string; error?: string; url?: string };
export function BulkContentDrafts({ api, action, selected, filter }: { api: Api; action: ContentAction; selected: string[]; filter: MassActionFilter | null }) {
  const trimming = action.startsWith("trim_");
  const [headingAction, setHeadingAction] = React.useState<HeadingAction>("meta_headings");
  const [providers, setProviders] = React.useState<{ id: string; name: string }[]>([]);
  const [provider, setProvider] = React.useState("");
  const [results, setResults] = React.useState<ContentResult[]>([]);
  const [busy, setBusy] = React.useState(false); const [error, setError] = React.useState("");
  const receipt = React.useRef<{ id: string; signature: string } | null>(null);
  const starting = React.useRef(false);
  React.useEffect(() => { setResults([]); setError(""); receipt.current = null; }, [action]);
  React.useEffect(() => { if(trimming)return;let live = true; void api<{ id: string; name: string; provider_type: string; is_active: boolean }[]>("/ai-providers").then(rows => { if (!live) return; const available = rows.filter(p => p.provider_type === "gemini" && p.is_active); setProviders(available); setProvider(available[0]?.id || ""); }).catch(e => { if (live) setError(errorText(e)); }); return () => { live = false; }; }, [api, trimming]);
  const pending = results.some(r => contentPending(r.status));
  React.useEffect(() => { if (!pending || !receipt.current) return; let live=true;const id = receipt.current.id; const timer = setInterval(() => void api<{ results: ContentResult[] }>(`/auto-reglue/content-drafts/${id}`).then(data => {if(live)setResults(data.results);}).catch(e => {if(live)setError(errorText(e));}), 4000); return () => {live=false;clearInterval(timer);}; }, [pending, api]);
  async function start() {
    if(starting.current||pending)return;
    starting.current=true;
    setBusy(true); setError("");
    try {
      const payload = contentBatchPayload(action, headingAction, filter, selected, provider);
      const signature = JSON.stringify(payload);
      if (receipt.current?.signature !== signature || results.length>0&&!pending) receipt.current = { id: crypto.randomUUID(), signature };
      setResults([]);
      const response = await api<{ results: ContentResult[] }>("/auto-reglue/content-drafts", body("POST", { ...payload, request_id: receipt.current.id }));
      setResults(response.results);
    } catch (e) { setError(errorText(e)); } finally { starting.current=false;setBusy(false); }
  }
  return <section className="dataPanel"><div className="dataPanelHeader"><h2>{contentLabels[action]}</h2></div><div className="dataPanelBody autoReglueContentBatch"><p>{contentActionDescription(action,headingAction)} Результаты сохраняются как черновики. Откройте редактор для сравнения и сохранения на сайте.</p>{action==="meta_headings"&&<fieldset disabled={busy||pending} style={{border:0,padding:0,margin:0}}><TemplateCombobox label="Режим переписывания" value={headingAction} options={headingActionOptions} onChange={value=>setHeadingAction(value as HeadingAction)}/><p className="muted">Title начинается с бренда, кроме проектов на общих ключах. Половину H1 в группе делаем короткими — 2–4 слова.</p></fieldset>}{!trimming && <fieldset disabled={busy||pending} style={{border:0,padding:0,margin:0}}><TemplateCombobox label="Gemini для массовой обработки" value={provider} options={providers.map(p => ({ value: p.id, label: p.name }))} onChange={setProvider} /></fieldset>}{error && <p role="alert">{error}</p>}<button type="button" className="button primary" disabled={busy || pending || !filter || !selected.length || selected.length > 100 || !trimming && !provider} onClick={() => void start()}>{busy ? "Создаём задачи…" : pending ? "Обработка продолжается…" : `Создать черновики (${selected.length})`}</button>{results.length > 0 && <div className="autoReglueContentResults">{results.map(result => <div key={result.site_id}><strong>{result.project}</strong><span>{result.error || ({ queued: "В очереди", generating: "Обработка", ready: "Черновик готов", failed: "Ошибка" }[result.status || ""] || result.status)}</span>{result.url && <a href={result.url}>Открыть редактор</a>}</div>)}</div>}</div></section>;
}
