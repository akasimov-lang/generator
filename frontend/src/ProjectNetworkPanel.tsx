import { SaveIndicator, QueueSaveIndicator } from "./SaveIndicator";
import { fakeSaveFeedback } from "./fakeSaveFeedback";
import { saveMarkupWithRetry } from "./networkMarkupSave";
import { mergeMarkupDraft, mergeCanonicalDraft } from "./networkDrafts";
import { useNetworkEditQueue } from "./useNetworkEditQueue";
import { NetworkEditStatus } from "./NetworkEditStatus";
import { type NetworkEditAction } from "./networkEditQueue";
import { ShowcaseHistory } from "./AutomaticActions";
import React from "react";
import { activeStatuses, networkOperationHistory, fakeQueueStatus } from "./networkOperationHistory";
import { useFakeMainQueue } from "./useFakeMainQueue";
import { fakeQueueActive, normalizedFakePath } from "./fakeMainQueue";
import { TemplateCombobox } from "./TemplateCombobox";
import { readNetworkWithRetry } from "./networkReadRetry";
import { LastReglueSummary, type LastReglue, type RecentNetworkChange } from "./LastReglueSummary";
import { matchesProjectSearch, normalizeDomainQuery } from "./projectSearch";
import { Trash2, X, Search, Check, ExternalLink } from "lucide-react";
import { buildBaseAlternates } from "./standardAlternates";
import { DomainRedirects, domainRedirectTargets, domainRedirectTarget, type DomainRedirect, type RedirectEdit } from "./DomainRedirects";
import { PageRedirects, type PageRedirectGroup, type PageRedirectEdit } from "./PageRedirects";
import { ProjectStructuredData } from "./ProjectStructuredData";
import { projectNotice, projectChanged } from "./projectNotificationEvents";

type AlternatesSnapshot = { markup: string; enabled: boolean };
type NetworkOperation = { id: string; action: "reserve" | "reglue" | "alternates" | "create_domains" | "create_subdomains" | "delete_domain" | "create_fake_main" | "select_fake_main" | "domain_redirect" | "domain_redirects_main" | "page_redirect" | "reglue_redirects" | "indexing" | "structured_data"; page_redirects_before?:PageRedirectGroup[]; page_redirects_after?:PageRedirectGroup[]; redirects_before?: DomainRedirect[]; redirects_after?: DomainRedirect[]; task_id?: string; domains?: string[]; status: string; message: string | null; domain: string | null; source_domain?: string | null; alternates_before?: AlternatesSnapshot | null; alternates_after?: AlternatesSnapshot | null; initiator: string; created_at: string };
type DomainClassification = { is_subdomain: boolean; parent_domain: string | null; parent_type: "drop" | "newreg" | null; unused_as_main: boolean };
type Network = {
  last_reglue_at?: string | null;
  last_reglue?: LastReglue | null;
  recent_network_changes?: RecentNetworkChange[];
  stock_warning?: string | null;
  domain_redirects?: DomainRedirect[]; has_domain_redirects?: boolean;
  page_redirects?: PageRedirectGroup[]; has_page_redirects?:boolean;
  fibery_name?: string | null;
  added_to_system_at?: string;
  domain_bans?: Record<string, boolean>;
  domain_added_at?: Record<string, string>;
  domain_removed_at?: Record<string, string>;
  domain_membership_history?: { domain: string; added_at: string | null; removed_at: string | null }[];
  history_overrides?: Record<string, Record<string, boolean>>;
  fake_main_paths?: string[]; fake_main_current?: string; fake_main_enabled?: boolean;
  amp?: string; prev_amp?: string; amp_domains?: string[];
  domain_classification?: Record<string, DomainClassification>;
  domain_types?: Record<string, "drop" | "newreg" | "amp">;
  canon: string; reserve: string; domains: string[]; revision: string;
  main_history: string[]; x_default_history: string[]; alternate_history: string[];
  alternateMarkup: string; enableAlternates: boolean; has_head: boolean;
  enableCanonical?: boolean; canonicalDefaultMarkup?: string; canonicalFakeMainMarkup?: string;
  alternates: { hreflang: string; href: string; domain: string }[];
  operations: NetworkOperation[];
};
type BrandNetwork = { id: string; name: string; main: string; domainCount: number; geoLabel: string };
type Props = {
  networks?: BrandNetwork[]; brand?: string; onSelectNetwork?: (name: string) => void;
  site: { id: string; name: string; added_to_system_at?: string | null; fibery_name?: string | null; cache_language?: string | null; cache_geo?: string | null }; mode: "network" | "redirects"; username: string;
  api: <T>(path: string, options?: RequestInit) => Promise<T>; onChanged: () => void; refreshToken?: number;
};
type MarkupSection = "canonical" | "alternates" | "dynamic";
const markupSignatures = (next: Network) => ({ canonical: JSON.stringify([next.canonicalDefaultMarkup ?? "", next.canonicalFakeMainMarkup ?? "", next.enableCanonical ?? null]), alternates: JSON.stringify([next.alternateMarkup, next.enableAlternates]), dynamic: JSON.stringify([!!next.fake_main_enabled, next.fake_main_paths || [], next.fake_main_current || ""]) });
type Draft = { markup: string; enabled: boolean; originalMarkup: string; originalEnabled: boolean };
const sameMarkup = (a: string, b: string) => a.trim().replace(/>\s+</g, "><") === b.trim().replace(/>\s+</g, "><");
const actionLabels = { structured_data: "Микроразметка", domain_redirects_main: "Все доменные редиректы на текущий Main", page_redirect: "Постраничные редиректы", reglue_redirects: "Цели редиректов после переклея", domain_redirect: "Доменные редиректы", create_domains: "Добавление доменов", select_fake_main: "Настройки фейковых страниц", indexing: "Индексация проекта", create_fake_main: "Создание фейковой главной", delete_domain: "Удаление домена", create_subdomains: "Создание поддоменов", reserve: "Сохранение резерва", reglue: "Ручной переклей", alternates: "Альтернейты" };
const statusLabels: Record<string, string> = { index_queued: "В очереди", index_submitting: "Отправляется", index_submitted: "Задача создана", index_unknown: "Отправка не подтверждена", confirmed: "Подтверждено", pending: "Ожидает подтверждения", unknown: "Результат пока неизвестен", failed: "Ошибка" };
const errorText = (error: unknown) => error instanceof Error ? error.message : "Не удалось выполнить запрос";

export function ProjectNetworkPanel({ site, mode, username, api, onChanged, refreshToken = 0, networks = [], brand, onSelectNetwork }: Props) {
  const [structuredDataRevision, setStructuredDataRevision] = React.useState(0);
  const draftKey = `network-alternates:${username}:${site.id}`;
  const [data, setData] = React.useState<Network | null>(null);
  const dataRef = React.useRef<Network | null>(null);
  const fiberyNameRef = React.useRef(site.fibery_name); fiberyNameRef.current = site.fibery_name;
  const [draft, setDraft] = React.useState<Draft | null>(() => {
    try {
      const value = JSON.parse(sessionStorage.getItem(draftKey) || "null");
      return value && typeof value.markup === "string" && typeof value.originalMarkup === "string" && typeof value.enabled === "boolean" && typeof value.originalEnabled === "boolean" ? value : null;
    } catch { return null; }
  });
  const canonicalKey = `network-canonical:${username}:${site.id}`;
  const [canonicalDraft, setCanonicalDraft] = React.useState<{ standard: string; fake: string; originalStandard: string; originalFake: string } | null>(()=>{
    try {const value=JSON.parse(sessionStorage.getItem(canonicalKey)||"null");return value&&["standard","fake","originalStandard","originalFake"].every(key=>typeof value[key]==="string")?value:null;}catch{return null;}
  });
  const filterKey = `network-domain-filter:${username}:${site.id}`;
  const [savedFilter, setSavedFilter] = React.useState(() => sessionStorage.getItem(filterKey) || "");
  const [domainQuery, setDomainQuery] = React.useState(savedFilter);
  function commitDomainFilter(value: string) {
    const query = value.trim();
    setSavedFilter(query); setDomainQuery(query);
    if (query) sessionStorage.setItem(filterKey, query); else sessionStorage.removeItem(filterKey);
  }
  const canonicalDirty = Boolean(canonicalDraft && (canonicalDraft.standard !== canonicalDraft.originalStandard || canonicalDraft.fake !== canonicalDraft.originalFake));
  const canonicalConflict = Boolean(data && canonicalDraft && canonicalDirty && (canonicalDraft.originalStandard !== (data.canonicalDefaultMarkup ?? "") || canonicalDraft.originalFake !== (data.canonicalFakeMainMarkup ?? "")));
  const [reserve, setReserve] = React.useState("");
  const [networkView, setNetworkView] = React.useState<"main" | "amp">("main");
  const [showDomainList, setShowDomainList] = React.useState(false);
  const [showNetworkHistory, setShowNetworkHistory] = React.useState(false);
  const domainListRef = React.useRef<HTMLTextAreaElement>(null);
  React.useEffect(() => { if (showDomainList) { domainListRef.current?.focus(); domainListRef.current?.select(); } }, [showDomainList]);
  const [busy, setBusy] = React.useState("");
  const busyRef = React.useRef(false);
  const loadController = React.useRef<AbortController | null>(null);
  const [error, setError] = React.useState("");
  const [message, setMessage] = React.useState("");
  const [savedMarkup, setSavedMarkup] = React.useState<Partial<Record<MarkupSection, string>>>({});
  const [markupErrors, setMarkupErrors] = React.useState<Partial<Record<MarkupSection, string>>>({});
  const [pendingMarkupSections, setPendingMarkupSections] = React.useState<MarkupSection[]>([]);
  const pendingMarkupSave = React.useRef<{ id: string; sections: MarkupSection[] } | null>(null);
  const [fakeMainInput, setFakeMainInput] = React.useState("");
  const [subdomainsInput, setSubdomainsInput] = React.useState("");
  const [removeDomainInput, setRemoveDomainInput] = React.useState("");
  const [submittingDeletion, setSubmittingDeletion] = React.useState<string[]>([]);
  const mounted = React.useRef(true);
  const historySite = React.useRef(site.id); historySite.current = site.id;
  const historySaving = React.useRef(new Set<string>());
  const [historyStatus, setHistoryStatus] = React.useState<Record<string, {saving:boolean; checked?:boolean; message:string; error?:boolean}>>({});
  const fakeQueue = useFakeMainQueue<Network>(site.id, api, !!busy);
  const editQueue = useNetworkEditQueue<Network>(site.id, api, !!busy);
  const queueOperationIds = new Set([...fakeQueue.items.flatMap(item => item.operation_ids), ...editQueue.items.map(item => item.id)]);
  const appliedEditNetwork = React.useRef<Network | null>(null);
  React.useEffect(() => {
    const next = editQueue.server.network;
    if (!next || next === appliedEditNetwork.current || busyRef.current) return;
    appliedEditNetwork.current = next;
    if (next.revision !== dataRef.current?.revision || JSON.stringify(next.operations) !== JSON.stringify(dataRef.current?.operations)) {
      accept(next); onChanged();
    }
  }, [editQueue.server.network, busy]);
  function enqueueEdit(action: NetworkEditAction, settings: Record<string, unknown> = {}) {
    if (!data) return false;
    let expected: Record<string, unknown>;
    if (action === "reserve" || action === "reglue") expected = {canon: data.canon, reserve: data.reserve};
    else if (action === "domain_redirects_main") expected = {canon: data.canon, rows: data.domain_redirects || []};
    else if (action === "domain_redirect") expected = {rows: (data.domain_redirects || []).filter(row => row.url === (settings.redirect_original_source || settings.redirect_source))};
    else expected = {rows: (data.page_redirects || []).filter(group => group.domain === (settings.page_redirect_original_domain || settings.page_redirect_domain)).flatMap(group => group.redirects.filter(row => row.url === (settings.page_redirect_original_source || settings.page_redirect_source)))};
    return editQueue.enqueue({action, revision: data.revision, ...settings, expected: (settings.expected as Record<string, unknown>) || expected});
  }
  const uncertain = data?.operations.some((op) => ["pending", "unknown"].includes(op.status) && !queueOperationIds.has(op.id)) || false;
  const appliedQueueNetwork = React.useRef<Network | null>(null);
  React.useEffect(() => {
    const next = fakeQueue.server.network;
    if (!next || next === appliedQueueNetwork.current) return;
    if (busyRef.current) { appliedQueueNetwork.current = next; return; }
    appliedQueueNetwork.current = next;
    if (next.revision !== dataRef.current?.revision || JSON.stringify(next.operations) !== JSON.stringify(dataRef.current?.operations)) {
      accept(next); setStructuredDataRevision(value => value + 1);
    }
  }, [fakeQueue.server.network, busy]);
  const alternatesDirty = Boolean(draft && (draft.markup !== draft.originalMarkup || draft.enabled !== draft.originalEnabled));
  const dirty = canonicalDirty || alternatesDirty;
  const conflict = canonicalConflict || Boolean(data && draft && dirty && (data.alternateMarkup !== draft.originalMarkup || data.enableAlternates !== draft.originalEnabled));

  function accept(next: Network, replaceReserve = false) {
    if (!mounted.current) return;
    const previous = dataRef.current;
    dataRef.current = next;
    setData(next);
    const receipt = pendingMarkupSave.current;
    const operation = receipt && next.operations.find(op => op.id === receipt.id);
    if (receipt && operation && ["confirmed", "failed"].includes(operation.status)) {
      setMarkupErrors(current => ({ ...current, ...Object.fromEntries(receipt.sections.map(section =>
        [section, operation.status === "failed" ? operation.message || "Webdev сообщил об ошибке." : ""])) }));
      if (operation.status === "confirmed") {
        const signatures = markupSignatures(next);
        setSavedMarkup(current => ({ ...current, ...Object.fromEntries(receipt.sections.map(section => [section, signatures[section]])) }));
      }
      pendingMarkupSave.current = null;
      setPendingMarkupSections([]);
    }
    setCanonicalDraft(old => mergeCanonicalDraft(old, next.canonicalDefaultMarkup ?? "", next.canonicalFakeMainMarkup ?? ""));
    setReserve((old) => !replaceReserve && old !== previous?.reserve && old && next.domains.includes(old) && old !== next.canon ? old : (next.reserve === next.canon ? "" : next.reserve));
    setDraft(old => mergeMarkupDraft(old, next.alternateMarkup, next.enableAlternates));
  }
  async function load(force = true, replaceReserve = false) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy("refresh"); setError("");
    const controller = new AbortController();
    loadController.current = controller;
    try {
      const next = await readNetworkWithRetry(
        () => api<Network>(`/sites/${site.id}/network${force ? "?refresh=true" : ""}`, { cache: "no-store", signal: controller.signal }),
        controller.signal,
        () => { if (mounted.current) setMessage("Сетка занята другим запросом. Повторяем загрузку автоматически…"); });
      if (controller.signal.aborted) return;
      const previous = dataRef.current;
      accept(next, replaceReserve);
      if (mounted.current) setStructuredDataRevision(value => value + 1);
      const fiberyChanged = next.fibery_name !== undefined && next.fibery_name !== fiberyNameRef.current;
      if (mounted.current && (fiberyChanged || previous && (previous.revision !== next.revision || JSON.stringify(previous.operations) !== JSON.stringify(next.operations)))) onChanged();
    }
    catch (err) { if (mounted.current && !controller.signal.aborted) setError(errorText(err)); }
    finally {
      if (loadController.current === controller) {
        loadController.current = null; busyRef.current = false;
        if (mounted.current) { setBusy(""); setMessage(current => current.startsWith("Сетка занята другим запросом.") ? "" : current); }
      }
    }
  }
  React.useEffect(() => {
    mounted.current = true;
    setNetworkView("main"); setShowNetworkHistory(false);
    historySaving.current.clear(); setHistoryStatus({});
    void load(false);
    return () => { mounted.current = false; loadController.current?.abort(); loadController.current = null; busyRef.current = false; };
  }, [site.id]);
  const appliedRefresh = React.useRef(refreshToken);
  React.useEffect(() => {
    if (appliedRefresh.current === refreshToken || busy) return;
    appliedRefresh.current = refreshToken;
    void load(true, true);
  }, [refreshToken, busy]);
  React.useEffect(() => {
    try {if (draft) sessionStorage.setItem(draftKey, JSON.stringify(draft));}
    catch {projectNotice({siteId:site.id,key:"draft-storage",code:"DRAFT_STORAGE",message:"Браузер не сохранил локальную копию правок. Сохраните разметку в Webdev перед закрытием страницы.",severity:"warning",active:true,persist:true});}
  }, [draft, draftKey]);
  React.useEffect(() => {
    projectNotice({siteId:site.id,key:"markup-draft",code:conflict?"MARKUP_CONFLICT":uncertain?"MARKUP_PENDING":"MARKUP_DRAFT",severity:conflict?"warning":"info",active:dirty,
      message:conflict?"Сохраним выбранные в PagePilot значения разметки поверх обновлённых данных Webdev.":uncertain?"Сохранение отправлено. Проверяем результат Webdev без повторной записи.":"В форме есть правки разметки. Кликните вне полей для сохранения. Переклей также сохранит их перед запуском.",context:"Сетка → Каноникл и альтернейты"});
  },[site.id,dirty,conflict,uncertain]);
  React.useEffect(() => {
    projectNotice({siteId:site.id,key:"network-form",code:"NETWORK_FORM",message:error||"Ошибка формы устранена.",severity:"error",active:!!error});
  },[site.id,error]);
  React.useEffect(()=>{
    try {if(canonicalDraft&&canonicalDirty)sessionStorage.setItem(canonicalKey,JSON.stringify(canonicalDraft));else sessionStorage.removeItem(canonicalKey);}
    catch {projectNotice({siteId:site.id,key:"draft-storage",code:"DRAFT_STORAGE",message:"Браузер не сохранил копию правок canonical. Сохраните разметку перед закрытием страницы.",severity:"warning",active:true,persist:true});}
  },[canonicalDraft,canonicalDirty,canonicalKey,site.id]);
  React.useEffect(() => {
    if (!uncertain) return;
    const timer = window.setInterval(() => { void load(); }, 10000);
    return () => window.clearInterval(timer);
  }, [uncertain]);

  const indexingPending = data?.operations.some(op => ["index_queued", "index_submitting"].includes(op.status));
  React.useEffect(() => {
    if (!indexingPending) return;
    let alive = true, fetching = false;
    const timer = window.setInterval(async () => {
      if (fetching) return;
      fetching = true;
      try {
        const operations = await api<NetworkOperation[]>(`/sites/${site.id}/network/operations`);
        if (alive && mounted.current && dataRef.current) {
          const next = { ...dataRef.current, operations };
          dataRef.current = next; setData(next);
        }
      } catch { /* Keep the saved history; retry only the local database read. */ }
      finally { fetching = false; }
    }, 5000);
    return () => { alive = false; window.clearInterval(timer); };
  }, [indexingPending, site.id, api]);

  const subdomains = [...new Set(subdomainsInput.toLowerCase().split(/[\s,;]+/).map((value) => value.trim().replace(/\.$/, "")).filter(Boolean))];
  const subdomainErrors = subdomains.flatMap((domain) => {
    if (!domain.includes(".") || domain.length > 253 || !domain.split(".").every((label) => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) return [domain + ": некорректное имя"];
    if (data?.domains.includes(domain)) return [domain + ": уже есть в сетке"];
    return [];
  });
  async function mutate(action: Exclude<NetworkOperation["action"], "indexing" | "reglue_redirects" | "structured_data">, targetDomain?: string, markupDraft = draft, settings?: { fake_main_path?: string; delete_fake_main?: boolean; enable_canonical?: boolean; enable_dynamic_routes?: boolean } & Partial<RedirectEdit & PageRedirectEdit>, revision?: string): Promise<boolean> {
    if (!data || !markupDraft || busyRef.current) return false;
    if(action === "alternates") {
      let problem="";
      if(canonicalDirty&&canonicalDraft&&[canonicalDraft.standard,canonicalDraft.fake].some(value=>value.trim()&&!/^<link\s+rel=["']canonical["']\s+href=["']https?:\/\/[^"'<>\s]+["']\s*\/?>$/i.test(value.trim())))problem='Canonical должен содержать одну ссылку <link rel="canonical" href="https://…" />.';
      const parsed=new DOMParser().parseFromString(markupDraft.markup,"text/html");
      if(parsed.body.textContent?.trim()||[...parsed.querySelectorAll("head > *, body *")].some(node=>node.tagName!=="LINK"||!node.getAttribute("rel")?.toLowerCase().split(/\s+/).includes("alternate")||!/^https?:\/\//.test(node.getAttribute("href")||"")||!/^[A-Za-z0-9-]+$/.test(node.getAttribute("hreflang")||"")||[...node.attributes].some(attr=>/^on/i.test(attr.name))))problem="В альтернейтах допустимы только link rel=alternate с href и hreflang. Проверьте разметку.";
      projectNotice({siteId:site.id,key:"markup-validation",code:"MARKUP_INVALID",message:problem||"Разметка прошла проверку.",severity:"error",active:!!problem,persist:true});
      if(problem)return false;
    }
    busyRef.current = true; setBusy(action); setError(""); setMessage("");
    const payload = { action, ...settings, ...(action === "create_fake_main" ? { activate_fake_main: true } : {}), fake_main_path: action === "select_fake_main" ? settings?.fake_main_path ?? "" : action === "create_fake_main" ? fakeMainInput : "", ...(action === "alternates" && canonicalDirty && canonicalDraft ? { canonical_default_markup: canonicalDraft.standard, canonical_fake_main_markup: canonicalDraft.fake } : {}), revision: revision || dataRef.current?.revision || data.revision, domain: action === "delete_domain" ? targetDomain || "" : targetDomain || reserve, alternate_markup: markupDraft.markup, enable_alternates: markupDraft.enabled, ...(action === "delete_domain" ? { domains: targetDomain ? [targetDomain] : removeDomains } : {}), ...((action === "create_subdomains" || action === "create_domains") ? { domains: subdomains } : {}) };
    if (action === "delete_domain") setSubmittingDeletion(payload.domains || []);
    const receiptKey = `network-request:${username}:${site.id}`;
    let requestId = crypto.randomUUID();
    try {
      const previous = JSON.parse(sessionStorage.getItem(receiptKey) || "null");
      if (previous?.fingerprint === JSON.stringify(payload)) requestId = previous.id;
    } catch { /* An invalid draft receipt can safely be replaced. */ }
    sessionStorage.setItem(receiptKey, JSON.stringify({ id: requestId, fingerprint: JSON.stringify(payload) }));
    const sections: MarkupSection[] = action === "alternates" ? [
      ...(canonicalDirty || settings?.enable_canonical !== undefined ? ["canonical" as const] : []),
      ...(markupDraft.markup !== data.alternateMarkup || markupDraft.enabled !== data.enableAlternates ? ["alternates" as const] : []),
    ] : action === "create_fake_main" || action === "select_fake_main" ? ["dynamic"] : [];
    if (sections.length) {
      pendingMarkupSave.current = { id: requestId, sections }; setPendingMarkupSections(sections);
      setMarkupErrors(current => ({...current, ...Object.fromEntries(sections.map(section => [section, ""]))}));
    }
    try {
      const submit = async () => {
        if (action === "alternates") {
          if (!mounted.current || historySite.current !== site.id) throw new Error("Проект закрыт до отправки разметки.");
          const fresh = await api<Network>(`/sites/${site.id}/network?refresh=true`, {cache: "no-store"});
          if (!mounted.current || historySite.current !== site.id) throw new Error("Проект закрыт до отправки разметки.");
          const merged = mergeMarkupDraft(markupDraft, fresh.alternateMarkup, fresh.enableAlternates);
          const canonical = mergeCanonicalDraft(canonicalDraft, fresh.canonicalDefaultMarkup ?? "", fresh.canonicalFakeMainMarkup ?? "");
          payload.revision = fresh.revision;
          payload.alternate_markup = merged.markup;
          payload.enable_alternates = merged.enabled;
          if (payload.canonical_default_markup !== undefined) payload.canonical_default_markup = canonical.standard;
          if (payload.canonical_fake_main_markup !== undefined) payload.canonical_fake_main_markup = canonical.fake;
        }
        return api<Network>(`/sites/${site.id}/network/operations`, { method: "POST", body: JSON.stringify({ ...payload, request_id: requestId }) });
      };
      const next = action === "alternates"
        ? await saveMarkupWithRetry(submit, () => { if (mounted.current && historySite.current === site.id) setMessage("Сохраняем значения PagePilot. Ожидаем освобождения сетки…"); })
        : await submit();
      if (!mounted.current) return false;
      const operation = next.operations.find((op) => op.id === requestId);
      accept(next, action === "reglue" || action === "reserve" && operation?.status === "confirmed");
      if ((action === "create_subdomains" || action === "create_domains") && operation && operation.status !== "failed") setSubdomainsInput("");
      if (action === "delete_domain" && operation && operation.status !== "failed") setRemoveDomainInput("");
      if (operation?.status === "confirmed") {

        projectChanged(site.id);
        setMessage(`${actionLabels[action]}: подтверждено.`);
        sessionStorage.removeItem(receiptKey);
        onChanged();
        return true;
      } else if (operation?.status === "failed") { setError(operation.message || "Webdev сообщил об ошибке."); sessionStorage.removeItem(receiptKey); }
      else setMessage(operation?.message || "Запрос отправлен. Ожидается подтверждение.");

    } catch (err) {
      if (mounted.current) {
        setError(`${errorText(err)} Обновите данные перед повторной отправкой.`);
        setMarkupErrors(current => ({...current, ...Object.fromEntries(sections.map(section => [section, errorText(err)]))}));
        const statusCode = (err as { statusCode?: number })?.statusCode;
        if (statusCode && statusCode < 500) { pendingMarkupSave.current = null; setPendingMarkupSections([]); }
      }
    }
    finally { busyRef.current = false; if (mounted.current) { setBusy(""); setSubmittingDeletion([]); } }
    return false;
  }
  async function saveHistory(domain: string, field: string, checked: boolean) {
    const requestSite = site.id;
    const key = `${domain}:${field}`;
    if (!dataRef.current || historySaving.current.has(key)) return;
    historySaving.current.add(key);
    setHistoryStatus(old => ({...old, [key]: {saving: true, checked, message: "Сохраняем…"}}));
    try {
      const saved = await api<Network>(`/sites/${site.id}/network/domain-history`, {
        method: "PATCH", body: JSON.stringify({ domain, field, checked }),
      });
      if (!mounted.current || historySite.current !== requestSite || !dataRef.current) return;
      const next = {...dataRef.current};
      if (field === "ban") next.domain_bans = {...next.domain_bans, [domain]: !!saved.domain_bans?.[domain]};
      else {
        const property = ({main:"main_history",alternate:"alternate_history",x_default:"x_default_history"} as const)[field as "main"|"alternate"|"x_default"];
        next[property] = [...next[property].filter(value => value !== domain), ...(saved[property].includes(domain) ? [domain] : [])];
      }
      dataRef.current = next; setData(next);
      setHistoryStatus(old => ({...old, [key]: {saving:false, message:"Сохранено"}}));
      projectChanged(site.id);
    } catch (err) {
      if (mounted.current && historySite.current === requestSite) setHistoryStatus(old => ({...old, [key]: {saving:false, message:errorText(err), error:true}}));
    } finally { historySaving.current.delete(key); }
  }
  function historyCheckbox(domain: string, field: string, checked: boolean, label: string) {
    const status = historyStatus[`${domain}:${field}`];
    return <><input type="checkbox" className="networkHistoryCheck" disabled={!!status?.saving}
      checked={status?.saving ? !!status.checked : checked} aria-label={`${domain}: ${label}`}
      onChange={event => void saveHistory(domain, field, event.target.checked)} />
      {status && <small role={status.error ? "alert" : "status"}>{status.message}</small>}</>;
  }
  async function saveDomainType(domain: string, domainType: string) {
    if (!data || busyRef.current) return;
    busyRef.current = true; setBusy("domain-type"); setError("");
    try {
      const saved = await api<{ domain_types: Record<string, "drop" | "newreg">; domain_classification?: Record<string, DomainClassification> }>(`/sites/${site.id}/network/domain-type`, {
        method: "PATCH", body: JSON.stringify({ domain, domain_type: domainType }),
      });
      if (!mounted.current) return;
      const next = { ...dataRef.current!, domain_types: saved.domain_types, domain_classification: saved.domain_classification };
      dataRef.current = next; setData(next);
    } catch (err) { if (mounted.current) setError(errorText(err)); }
    finally { busyRef.current = false; if (mounted.current) setBusy(""); }
  }
  const known = data ? [...new Set([...data.domains, ...(data.amp_domains || []), data.canon, ...data.main_history, ...data.alternate_history, ...data.x_default_history, ...Object.keys(data.history_overrides || {}), ...Object.keys(data.domain_added_at || {}), ...Object.keys(data.domain_removed_at || {}), ...(data.domain_membership_history || []).map(period => period.domain)])].filter(Boolean) : [];
  const ampDomains = new Set([...(data?.amp_domains || []), ...Object.entries(data?.domain_types || {}).filter(([, type]) => type === "amp").map(([domain]) => domain)]);
  const currentDomains = new Set([...(data?.domains || []), ...(data?.amp_domains || []), data?.canon || ""]);
  const redirectTargets = domainRedirectTargets(data?.domain_redirects || [], !!data?.has_domain_redirects);
  const domainPosition = (domain: string) => networkView === "amp" ? 0 : domain === data?.canon ? 2 : domain === data?.reserve ? 1 : 0;
  const visibleDomains = known.filter(domain => showNetworkHistory || currentDomains.has(domain)).filter((domain) => networkView === "amp" ? ampDomains.has(domain) : !ampDomains.has(domain)).filter(domain => matchesProjectSearch(domain, normalizeDomainQuery(domainQuery))).sort((left, right) => domainPosition(left) - domainPosition(right));
  const deletingDomains = new Set([...submittingDeletion, ...(data?.operations || []).filter(op => op.action === "delete_domain" && ["pending", "unknown"].includes(op.status)).flatMap(op => op.domains?.length ? op.domains : op.domain ? [op.domain] : [])]);
  const disabled = Boolean(busy) || uncertain;
  const canSaveMarkup = !disabled && dirty && !!data?.has_head;
  React.useEffect(()=>{
    if(!canSaveMarkup)return;
    const outside=(event:MouseEvent)=>{
      if(!mounted.current||busyRef.current)return;
      if(event.target instanceof Element && event.target.closest("[data-markup-editor]"))return;
      void mutate("alternates");
    };
    document.addEventListener("click",outside);
    return()=>document.removeEventListener("click",outside);
  },[canSaveMarkup,draft,canonicalDraft,site.id]);
  function saveFakeMain(rawPath: string) {
    if (!rawPath.trim() || dataRef.current?.fake_main_paths?.includes(normalizedFakePath(rawPath))) return;
    if (fakeQueue.enqueue("create", rawPath)) setFakeMainInput(current => current === rawPath ? "" : current);
  }
  function saveFakeMainOnEnter(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    if (!event.repeat) saveFakeMain(event.currentTarget.value);
  }
  function saveMarkupOnEnter(event: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    if (!event.repeat && canSaveMarkup) void mutate("alternates");
  }
  function saveMarkupOnBlur(event: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) {
    const target=event.relatedTarget;
    if(target instanceof Element && target.closest("[data-markup-editor]"))return;
    if(!canSaveMarkup)return;
    window.setTimeout(()=>{
      const latest=dataRef.current;
      if(!mounted.current||busyRef.current||!latest||!draft)return;
      if(sameMarkup(draft.markup,latest.alternateMarkup)&&draft.enabled===latest.enableAlternates&&canonicalDraft&&sameMarkup(canonicalDraft.standard,latest.canonicalDefaultMarkup??"")&&sameMarkup(canonicalDraft.fake,latest.canonicalFakeMainMarkup??"")) {useSavedMarkup();return;}
      void mutate("alternates");
    },0);
  }
  async function startReglue() {
    if(dirty && !await mutate("alternates"))return;
    enqueueEdit("reglue", {domain: reserve});
  }
  function useSavedMarkup() {
    if (!data) return;
    setDraft({ markup: data.alternateMarkup, enabled: data.enableAlternates, originalMarkup: data.alternateMarkup, originalEnabled: data.enableAlternates });
    setCanonicalDraft({ standard: data.canonicalDefaultMarkup ?? "", fake: data.canonicalFakeMainMarkup ?? "", originalStandard: data.canonicalDefaultMarkup ?? "", originalFake: data.canonicalFakeMainMarkup ?? "" });
  }
  function addedDateCell(domain: string) {
    const membershipDate = data?.domain_added_at?.[domain];
    const projectDate = domain === site.name ? data?.added_to_system_at || site.added_to_system_at : undefined;
    const date = membershipDate || projectDate;
    const title = membershipDate ? "Добавление в сетку зафиксировано системой (МСК)"
      : projectDate ? "Дата добавления проекта в систему (МСК)" : "Дата добавления не сохранена";
    return <td data-label="Дата добавления" className="networkAddedAt" title={title}>{date ? new Date(date).toLocaleString("ru-RU", {
      timeZone: "Europe/Moscow", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
    }) : "—"}</td>;
  }
  function markupStatus(section: MarkupSection) {
    if (!data) return null;
    const signatures = markupSignatures(data);
    const current = section === "canonical" ? JSON.stringify([canonicalDraft?.standard ?? "", canonicalDraft?.fake ?? "", data.enableCanonical ?? null])
      : section === "alternates" ? JSON.stringify([draft?.markup ?? "", !!draft?.enabled]) : signatures.dynamic;
    const path = normalizedFakePath(fakeMainInput);
    const edited = section === "canonical" ? canonicalDirty : section === "alternates" ? alternatesDirty
      : !!fakeMainInput.trim() && !data.fake_main_paths?.includes(path);
    const fake = section === "dynamic" ? fakeSaveFeedback(fakeQueue.items, data) : undefined;
    const saving = pendingMarkupSections.includes(section) || fake?.state === "saving";
    const saved = !edited && savedMarkup[section] === current || fake?.state === "saved";
    const problem = markupErrors[section] || (fake?.state === "error" ? fake.error : "");
    return <SaveIndicator state={problem || fake?.state === "error" ? "error" : saving ? "saving" : saved ? "saved" : "idle"} error={problem}
      version={fake?.version || savedMarkup[section] || ""} label={section === "canonical" ? "Каноникл" : section === "alternates" ? "Альтернейты" : "Динамические страницы"} />;
  }
  const removeDomains = [...new Set(removeDomainInput.toLowerCase().split(/[\s,;]+/).map(value => value.trim().replace(/\.$/, "")).filter(Boolean))];
  const protectedDomains = [data?.canon, data?.reserve, site.name, data?.amp, ...(data?.amp_domains || [])].filter(Boolean).map(value => value!.replace(/^www\./, ""));
  const removeErrors = removeDomains.flatMap(domain => !data?.domains.includes(domain) ? [domain + ": домен отсутствует в сетке."] : protectedDomains.includes(domain.replace(/^www\./, "")) ? [domain + ": домен проекта, Main, AMP или резерв защищён от удаления."] : data.alternates.some(link => link.domain.replace(/^www\./, "") === domain.replace(/^www\./, "")) ? [domain + ": используется в альтернейтах."] : []);
  const reserveValid = Boolean(data && reserve && reserve !== data.canon && data.domains.includes(reserve) && !ampDomains.has(reserve));
  const reglueBlockedReason = editQueue.busy("reglue") ? "Переклей отправлен на сервер."
    : editQueue.busy("reserve") ? "Ожидаем сохранения резерва."
    : busy && dirty ? "Ожидаем сохранения разметки."
    : !reserveValid ? "Выберите резервный домен из текущей сетки."
    : reserve !== data?.reserve ? "Сначала сохраните выбранный резерв." : "";
  const topControls = data && (<div className="networkTopControls">
        {mode === "network" && networkView === "amp" ? <p>Текущий AMP: <strong>{data.amp || "не задан"}</strong> · Предыдущий AMP: <strong>{data.prev_amp || "не задан"}</strong></p> : <div className="networkMainReserveRow">
          <div className="networkCurrentDomains"><span>Текущий Main: <strong>{data.canon || "не задан"}</strong></span><span>Текущий резерв: <strong>{data.reserve && data.reserve !== data.canon ? data.reserve : "не выбран"}</strong></span><span>Фейковый внутряк: <strong>{data.fake_main_current || "не выбран"}</strong></span></div>
          <fieldset className="networkReserveField networkReserveInline" disabled={editQueue.busy("reserve")}><TemplateCombobox label="Резервный домен" value={reserve} placeholder="Выберите резерв" onChange={value => { if (!editQueue.busy("reserve")) setReserve(value); }} options={[{ value: "", label: "Выберите резерв" }, ...data.domains.filter(domain => !ampDomains.has(domain) && domain !== data.canon).map(domain => ({ value: domain, label: domain }))]} /></fieldset>
          <div className="networkReserveSave">
            <button type="button" className="button secondary compact" disabled={editQueue.busy("reserve") || !reserveValid || reserve === data.reserve} onClick={() => enqueueEdit("reserve", {domain: reserve})}>Сохранить резерв</button>
            <QueueSaveIndicator items={editQueue.items.filter(item => item.request.action === "reserve")} label="Резерв" />
            <div className="networkButtonCaption"><NetworkEditStatus item={editQueue.latest("reserve")} retry={id => editQueue.retry(id)} /></div>
          </div>
          <div className="networkReserveSave networkReglueSave"><button type="button" className="button primary compact networkReglueButton" disabled={!!reglueBlockedReason} title={reglueBlockedReason || (dirty?"Сохранить разметку и запустить переклей на резерв":"Ручной переклей на резервный домен")} onClick={() => void startReglue()}>Переклей</button>
            <QueueSaveIndicator items={editQueue.items.filter(item => item.request.action === "reglue")} label="Переклей" />
            <div className="networkButtonCaption"><NetworkEditStatus item={editQueue.latest("reglue")} retry={id => editQueue.retry(id)} />
            {!editQueue.latest("reglue") && reglueBlockedReason && <small className="networkEditStatus" title={reglueBlockedReason}>{reglueBlockedReason}</small>}</div>
          </div>
        </div>}
        </div>);
  return <section className="dataPanel projectNetworkPanel">
    <div className="panelHeader"><div className="networkPanelHeading"><h2>{mode === "network" ? "Сетка проекта" : "Переклей"}</h2>        {data && mode === "network" && <div className="networkViewSwitch" role="group" aria-label="Вид сетки">
          <button type="button" aria-pressed={networkView === "main"} onClick={() => setNetworkView("main")}>Основная сетка</button>
          <button type="button" aria-pressed={networkView === "amp"} onClick={() => setNetworkView("amp")}>Ампы</button>
        </div>}</div>
      <div className="networkRefreshStatus"><button type="button" className="button secondary compact" disabled={Boolean(busy)} onClick={() => void load(true, true)}>{busy === "refresh" ? "Обновляем…" : "Обновить данные"}</button>{message && message !== "Ручной переклей: подтверждено." && <small role="status">{message}</small>}
        {mode !== "network" && <LastReglueSummary last={data?.last_reglue} recent={data?.recent_network_changes} observedAt={data?.last_reglue_at} />}
      </div>
    </div>
    <div className="dataPanelBody">
      {error && <p role="alert" className="error">{error}</p>}
      {!data && <p>{busy ? "Загружаем сетку проекта…" : "Данные сетки недоступны. Повторите загрузку."}</p>}
      {data && <>
        {data.stock_warning&&<p role="alert" className="notice">⚠ {data.stock_warning}</p>}

        {editQueue.error && <p role="alert" className="notice">{editQueue.error}</p>}
        {mode !== "network" && topControls}
        {mode === "network" && <>
          {showDomainList && <div className="networkDomainList"><label>Домены — по одному в строке<textarea ref={domainListRef} readOnly aria-label="Домены для копирования" value={visibleDomains.join("\n")} rows={Math.min(12, Math.max(3, visibleDomains.length))} /></label><small>Ctrl+C / ⌘C — скопировать. Можно выделить только нужные строки.</small><button type="button" className="secondary compact" onClick={() => setShowDomainList(false)}>Скрыть список</button></div>}
          <div className="networkWithNavigation networkWorkspace"><div className="networkMembership">
          {topControls}
          <div className="networkTableWrap" tabIndex={0} role="region" aria-label="Домены сетки"><label className="networkHistoryToggle"><input type="checkbox" checked={showNetworkHistory} onChange={event => setShowNetworkHistory(event.target.checked)} />Показать историю</label><table className="networkTable"><thead><tr><th scope="col"><div className="networkDomainSearch"><Search size={14} aria-hidden="true" /><input aria-label="Поиск по доменам сетки" placeholder="Домены" value={domainQuery} onChange={event => setDomainQuery(event.target.value)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); commitDomainFilter(domainQuery); } if (event.key === "Escape") setDomainQuery(savedFilter); }} />{(savedFilter || domainQuery) && <button type="button" aria-label="Сбросить фильтр доменов" title="Сбросить фильтр" onClick={() => commitDomainFilter("")}><X size={15} /></button>}<button type="button" className="networkSelectDomains" aria-expanded={showDomainList} onClick={() => setShowDomainList(value => !value)}>Выделить</button></div></th><th scope="col">Тип домена</th><th scope="col">Поддомен</th><th scope="col">Статус</th><th scope="col">Был Main</th><th scope="col">Был в альтернейтах</th><th scope="col">x-default</th><th scope="col">БАН</th><th scope="col">Действия</th><th scope="col">Дата добавления</th><th scope="col">Дата исключения</th></tr></thead>
            <tbody>{visibleDomains.map((domain) => <tr key={domain} className={currentDomains.has(domain) ? undefined : "networkHistoricalDomain"}><td data-label="Домен">{domain === data.canon || domain === data.reserve || domain === site.name ? <strong>{domain}</strong> : domain}</td><td data-label="Тип домена">{ampDomains.has(domain) ? <span className="networkAmpType">AMP</span> : data.domain_classification?.[domain]?.is_subdomain ? <span title="Тип задаётся у родительского домена">{data.domain_classification[domain].parent_type === "drop" ? "Дроп (родитель)" : data.domain_classification[domain].parent_type === "newreg" ? "Новорег (родитель)" : "Не указан у родителя"}</span> : <select className="networkDomainType" aria-label={`Тип домена ${domain}`} value={data.domain_types?.[domain] || ""} disabled={Boolean(busy)} onChange={(event) => void saveDomainType(domain, event.target.value)}><option value="" disabled>Не указан</option><option value="drop">Дроп</option><option value="newreg">Новорег</option></select>}</td><td data-label="Поддомен">
                <span className="networkSubdomain"><input type="checkbox" className="networkHistoryCheck" disabled checked={!!data.domain_classification?.[domain]?.is_subdomain} aria-label={domain + ": поддомен"} />
                {data.domain_classification?.[domain]?.is_subdomain && <span title={"Родитель: " + data.domain_classification[domain].parent_domain}>
                  {data.domain_classification[domain].parent_type === "drop" ? "Поддомен дропа" : data.domain_classification[domain].parent_type === "newreg" ? "Поддомен новорега" : "Тип родителя не указан"}
                  {data.domain_classification[domain].unused_as_main && <small>Не был Main</small>}
                </span>}</span>
              </td><td data-label="Статус">{deletingDomains.has(domain) ? <span className="networkDeletionStatus" role="status">Удаление</span> : domainRedirectTarget(domain, redirectTargets) ? <span title={`301 → ${domainRedirectTarget(domain, redirectTargets)}`}>301</span> : networkView === "amp" && domain === data.amp ? "Текущий AMP" : networkView === "amp" && domain === data.prev_amp ? "Предыдущий AMP" : domain === data.canon ? <strong>Main</strong> : domain === data.reserve ? <strong>Резерв</strong> : data.domains.includes(domain) ? "В сетке" : "В истории"}</td>
              {[data.main_history, data.alternate_history, data.x_default_history].map((history, i) => <td key={i} data-label={["Был Main", "Был в альтернейтах", "x-default"][i]}>{historyCheckbox(domain, ["main", "alternate", "x_default"][i], history.includes(domain), ["был Main", "был в альтернейтах", "x-default"][i])}</td>)}
              <td data-label="БАН">{historyCheckbox(domain, "ban", Boolean(data.domain_bans?.[domain]), "БАН")}</td>
              <td data-label="Действия"><button type="button" className="networkDeleteButton" aria-label={`Удалить ${domain} из сетки`}
                title={domain === data.canon || domain === data.reserve || domain === site.name || domain === data.amp ? "Домен проекта, Main, AMP и резерв защищены от удаления" : "Удалить домен из сетки"}
                disabled={disabled || !data.domains.includes(domain) || [data.canon, data.reserve, site.name, data.amp].includes(domain)}
                onClick={() => void mutate("delete_domain", domain)}><Trash2 size={15} /></button></td>
              {addedDateCell(domain)}
              <td data-label="Дата исключения" className="networkAddedAt" title={!currentDomains.has(domain) && data.domain_removed_at?.[domain] ? "Исключение из сетки зафиксировано системой (МСК)" : "Дата исключения не сохранена"}>{!currentDomains.has(domain) && data.domain_removed_at?.[domain] ? new Date(data.domain_removed_at[domain]).toLocaleString("ru-RU", { timeZone: "Europe/Moscow", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}</td>
            </tr>)}</tbody>
          </table></div>
          {!visibleDomains.length && <p>{domainQuery.trim() ? "Домены не найдены." : networkView === "amp" ? "В кеше проекта AMP-домены не указаны." : "В основной сетке нет доменов."}</p>}
          {networkView === "main" && <><DomainRedirects key={site.id} canon={data.canon} onRetargetMain={async () => enqueueEdit("domain_redirects_main")} queue={editQueue} redirects={data.domain_redirects || []} revision={data.revision} available={!!data.has_domain_redirects} disabled={disabled} onSave={async edit => enqueueEdit("domain_redirect", edit)} /><PageRedirects key={`pages:${site.id}`} groups={data.page_redirects||[]} domains={data.domains} canon={data.canon} revision={data.revision} available={!!data.has_page_redirects} disabled={disabled} queue={editQueue} onSave={async edit => enqueueEdit("page_redirect", edit)}/></>}
          </div><aside className="networkSidebar"><LastReglueSummary last={data?.last_reglue} recent={data?.recent_network_changes} observedAt={data?.last_reglue_at} />{mode === "network" && !!networks.length && <nav className="networkBrandNavigation" aria-label="Навигация по сеткам бренда">
            <div className="networkBrandNavigationHeading"><strong>Сетки бренда</strong><small>{brand} · {networks.length}</small></div>
            <ul>{networks.map(peer => { const current = peer.id === site.id; return <li key={peer.id}><a href={`/project-network/${encodeURIComponent(peer.name)}/`} aria-current={current ? "page" : undefined} aria-label={`Открыть сетку ${peer.name}`} onClick={event => { if (!onSelectNetwork || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return; event.preventDefault(); onSelectNetwork(peer.name); }}>
              <span className="networkBrandNavigationText"><span className="networkBrandNavigationName" title={peer.name}>{peer.name}</span><small><span>{peer.geoLabel}</span><span title={current ? data.canon : peer.main}>{current ? data.canon : peer.main || "Main не задан"}</span></small></span>
              <span className="networkBrandNavigationCount" title="Доменов в сетке">{current ? data.domains.length : peer.domainCount}</span>
            </a></li>; })}</ul>
          </nav>}</aside></div>

          {networkView === "main" && <div className="networkDomainManagement"><div className="networkSection networkSubdomains">
            <h3>Добавление в сетку</h3>
            <p>Укажите домены и поддомены через запятую, пробел или новую строку.</p>
            <label className="networkSubdomainsField">Домены и поддомены<textarea aria-label="Домены и поддомены" rows={2} value={subdomainsInput} disabled={disabled} placeholder="example.com, test.example.com" onChange={(event) => setSubdomainsInput(event.target.value)} /></label>
            {subdomains.length > 0 && <><p>Будет создано: {subdomains.length}</p><ul>{subdomains.map((domain) => <li key={domain}>{domain}</li>)}</ul></>}
            {!!subdomainErrors.length && <div className="notice" role="alert">{subdomainErrors.map((text) => <p key={text}>{text}</p>)}</div>}
            {subdomains.length > 100 && <p role="alert">За один запуск можно создать до 100 доменов.</p>}
            <div className="networkActions"><button type="button" className="button compact" disabled={disabled || !subdomains.length || subdomains.length > 100 || !!subdomainErrors.length} onClick={() => void mutate("create_domains")}>{busy === "create_domains" ? "Добавляем…" : "Добавить в сетку"}</button></div>
            <p className="muted">Перед запуском сервер проверит домены по нашей базе и актуальной сетке Webdev. Домены добавятся в сетку автоматически; появление в списке ещё не подтверждает готовность HTTPS.</p>
          </div><div className="networkSection networkRemoveDomains">
            <h3>Удаление из сетки</h3>
            <p>Укажите домены и поддомены через запятую, пробел или новую строку — до 100 за один запрос.</p>
            <label className="networkSubdomainsField">Домен для удаления<textarea aria-label="Домен для удаления" rows={2} value={removeDomainInput} disabled={disabled} placeholder="test.example.com" onChange={event => setRemoveDomainInput(event.target.value)} /></label>
            {removeErrors.length > 0 && <p role="alert">{removeErrors.join(" ")}</p>}
            <div className="networkActions"><button type="button" className="button secondary compact" disabled={disabled || !removeDomains.length || removeDomains.length > 100 || !!removeErrors.length} onClick={() => void mutate("delete_domain")}>{busy === "delete_domain" ? "Удаляем…" : "Удалить из сетки"}</button></div>
            <p className="muted">Домен проекта, Main, AMP и резерв защищены от удаления.</p>
          </div></div>}
        </>}

        {(mode !== "network" || networkView === "main") && <div className="networkSection networkCanonical" data-markup-editor>
          <div className="networkMarkupHeading"><h3>Каноникл</h3>
            <button type="button" role="switch" className="networkMarkupSwitch" aria-label="Каноникл" aria-checked={!!data.enableCanonical}
              title={data.enableCanonical ? "Выключить каноникл" : "Включить каноникл"} disabled={disabled || !data.has_head || typeof data.enableCanonical !== "boolean"}
              onClick={() => void mutate("alternates", undefined, draft, { enable_canonical: !data.enableCanonical })}><span aria-hidden="true" /></button>
            {markupStatus("canonical")}
          </div>
          <label>Каноникл всех страниц<input type="text" aria-label="Каноникл всех страниц" className="networkMarkup" onKeyDown={saveMarkupOnEnter} onBlur={saveMarkupOnBlur} spellCheck={false} disabled={disabled || !data.has_head || !canonicalDraft} value={canonicalDraft?.standard ?? ""} onChange={event => canonicalDraft && setCanonicalDraft({ ...canonicalDraft, standard: event.target.value })} placeholder={data.canonicalDefaultMarkup === undefined ? "Нет сохранённых данных" : "Не задан"} /></label>
          <label><span className="networkMarkupHeading">Каноникл главной и фейковых внутренних страниц
            {data.canon && data.fake_main_current && <a className="iconButton" href={`https://${data.canon}/${data.fake_main_current.replace(/^\/+/, "")}`} target="_blank" rel="noopener noreferrer" aria-label="Открыть текущую фейковую страницу на Main в новой вкладке" title="Открыть текущую фейковую страницу на Main в новой вкладке"><ExternalLink size={18} aria-hidden="true" /></a>}
          </span><input type="text" aria-label="Каноникл главной и фейковых внутренних страниц" className="networkMarkup" onKeyDown={saveMarkupOnEnter} onBlur={saveMarkupOnBlur} spellCheck={false} disabled={disabled || !data.has_head || !canonicalDraft} value={canonicalDraft?.fake ?? ""} onChange={event => canonicalDraft && setCanonicalDraft({ ...canonicalDraft, fake: event.target.value })} placeholder={data.canonicalFakeMainMarkup === undefined ? "Нет сохранённых данных" : "Не задан"} /></label>
          <p className="muted">Клик вне полей или Enter — сохранить изменения в Webdev.</p>
          {dirty && <div className="networkActions"><button type="button" className="button secondary compact" disabled={!canSaveMarkup} onClick={()=>void mutate("alternates")}>Сохранить разметку</button><button type="button" className="button secondary compact" disabled={disabled} onClick={useSavedMarkup}>Использовать сохранённую разметку</button></div>}
          {data.fake_main_current && <p className="muted">Текущая фейковая внутренняя страница: {data.fake_main_current}</p>}
        </div>}
        {draft && (mode !== "network" || networkView === "main") && <div className="networkSection" data-markup-editor>
          <div className="networkMarkupHeading"><h3>Альтернейты</h3>
            <button type="button" role="switch" className="networkMarkupSwitch" aria-label="Альтернейты" aria-checked={draft.enabled}
              title={draft.enabled ? "Выключить альтернейты" : "Включить альтернейты"} disabled={disabled || !data.has_head}
              onClick={() => {
                const next = { ...draft, enabled: !draft.enabled };
                setDraft(next);
                void mutate("alternates", undefined, next);
              }}><span aria-hidden="true" /></button>
            {markupStatus("alternates")}
            <button type="button" className="button secondary compact" disabled={disabled || !data.has_head} onClick={() => {
              try {
                if (!data.fake_main_enabled) throw new Error("Сначала включите и сохраните фейковую внутреннюю страницу.");
                const markup = buildBaseAlternates(site.cache_language, site.cache_geo, data.fake_main_current, draft.markup);
                const next = { ...draft, markup, enabled: true };
                setDraft(next);
                void mutate("alternates", undefined, next);
              } catch (err) { setError(errorText(err)); }
            }}>Добавить Alternate</button>
          </div>
          <label>Альтернейты<textarea aria-label="Альтернейты" className="networkMarkup" onKeyDown={saveMarkupOnEnter} onBlur={saveMarkupOnBlur} rows={8} spellCheck={false} value={draft.markup} disabled={disabled || !data.has_head} onChange={(event) => setDraft({ ...draft, markup: event.target.value })} placeholder={'<link rel="alternate" hreflang="x-default" href="https://example.com/" />'} /></label>
          <p className="muted">Клик вне полей или Enter — сохранить. Shift+Enter — новая строка.</p>
          {!data.has_head && <p>Настройки head не получены. Редактирование недоступно.</p>}
          {conflict && <button type="button" className="button secondary" disabled={Boolean(busy)} onClick={() => { setDraft({ markup: data.alternateMarkup, enabled: data.enableAlternates, originalMarkup: data.alternateMarkup, originalEnabled: data.enableAlternates }); setCanonicalDraft({ standard: data.canonicalDefaultMarkup ?? "", fake: data.canonicalFakeMainMarkup ?? "", originalStandard: data.canonicalDefaultMarkup ?? "", originalFake: data.canonicalFakeMainMarkup ?? "" }); }}>Загрузить актуальную разметку</button>}
        </div>}
        {(mode !== "network" || networkView === "main") && <div className="networkSection"><div className="networkMarkupHeading"><h3>Фейковые внутренние страницы</h3>
            <button type="button" role="switch" className="networkMarkupSwitch" aria-label="Динамические страницы" aria-checked={!!data.fake_main_enabled}
              title={data.fake_main_enabled ? "Выключить динамические страницы" : "Включить динамические страницы"} disabled={disabled}
              onClick={() => void mutate("select_fake_main", undefined, draft, { enable_dynamic_routes: !data.fake_main_enabled })}><span aria-hidden="true" /></button>
            {markupStatus("dynamic")}
          </div>
          <div className="networkFakeForms"><div>
            <label className="networkFakePath">Путь фейковой главной<input aria-label="Путь фейковой главной" aria-describedby="fake-main-save-hint" value={fakeMainInput} onChange={e => setFakeMainInput(e.target.value)} onKeyDown={saveFakeMainOnEnter} onBlur={event => saveFakeMain(event.currentTarget.value)} placeholder="/events, /events/ или /index.php" /></label>
            <small id="fake-main-save-hint" className="muted">Клик вне поля или Enter — создать и назначить.</small>
          </div></div>
          {!!data.fake_main_paths?.length ? <div className="networkFakeColumns">{Array.from({length: Math.ceil(data.fake_main_paths.length / 3)}, (_, column) => <ul className="networkFakePages" key={column}>{data.fake_main_paths!.slice(column * 3, column * 3 + 3).map(path => {
            const current = path === data.fake_main_current;
            return <li key={path}>
              <a href={`https://${data.canon}${path}`} title={path} target="_blank" rel="noreferrer">{current ? <strong>{path}</strong> : path}</a>
              <button type="button" className={`networkFakeButton select${current ? " selected" : ""}`} aria-label={`Назначить ${path}`} aria-pressed={current} title={current ? "Текущая страница" : "Назначить текущей"} disabled={disabled || current || fakeQueue.busyPath(path)} onClick={() => fakeQueue.enqueue("select", path)}><Check size={18} aria-hidden="true" /></button>
              <button type="button" className="networkFakeButton delete" aria-label={`Удалить ${path}`} title={current ? "Перед удалением назначьте другую страницу" : "Удалить страницу"} disabled={current || fakeQueue.busyPath(path) || fakeQueue.count >= 10} onClick={() => fakeQueue.enqueue("delete", path)}><X size={18} aria-hidden="true" /></button>
              {fakeQueue.items.filter(item => item.path === path && fakeQueueActive(item)).map(item => <small key={item.id} role="status">{item.message}</small>)}
            </li>;
          })}</ul>)}</div> : <p className="muted">В кеше нет фейковых внутренних страниц.</p>}

        </div>}
        {mode === "network" && networkView === "main" && <ProjectStructuredData key={site.id} siteId={site.id} api={api} refreshKey={refreshToken} backgroundRefreshKey={`${structuredDataRevision}:${data.revision}`}/>}
        <ShowcaseHistory siteId={site.id} api={api} refreshKey={refreshToken}/>
        {(data.operations.some(op => op.action !== "indexing") || !!fakeQueue.items.length || !!fakeQueue.error) && <div className="networkSection"><h3>История операций{fakeQueue.count > 0 ? ` · Фейковые страницы в работе: ${fakeQueue.count}` : ""}</h3>
          {fakeQueue.error && <p role="alert">Не удалось обновить статус: {fakeQueue.error}</p>}
          {[true,false].map(activeOnly => {
          const entries = networkOperationHistory(data.operations, fakeQueue.items).filter(entry => activeStatuses.has(entry.item.status) === activeOnly);
          if (!entries.length) return null;
          const list = <ul className="networkOperations">{entries.map(entry => {
            if (entry.kind === "queue") {
              const item = entry.item;
              return <li key={item.id}>
                <strong>{item.action === "delete" ? "Удаление фейковой страницы" : item.action === "select" ? "Назначение фейковой страницы" : "Создание и назначение фейковой страницы"}: {item.path}</strong> — <span role="status">{fakeQueueStatus[item.status] || item.status}</span>
                {item.created_at && <small>{new Date(item.created_at).toLocaleString("ru-RU", {timeZone:"Europe/Moscow"})} · МСК</small>}
                {fakeQueueActive(item) && <progress aria-label={`Выполнение: ${item.path}`} />}
                <p>{item.message}</p>
                {item.status === "unconfirmed" && <button type="button" className="button secondary compact" onClick={() => fakeQueue.retry(item.id)}>Проверить отправку</button>}
                {fakeQueueActive(item) && <button type="button" className="button danger compact" disabled={item.status === "cancelling"} onClick={() => void fakeQueue.cancel(item.id)}>Удалить отправку</button>}
              </li>;
            }
            const operation = entry.item;
            return <li key={operation.id}>
          <strong>{actionLabels[operation.action]}{operation.action === "reglue" && operation.domain ? `: ${operation.source_domain || "Исходный домен не сохранён"} -> ${operation.domain}` : operation.domain ? `: ${operation.domain}` : ""}</strong> — {statusLabels[operation.status] || operation.status}
          <small>{new Date(operation.created_at).toLocaleString("ru-RU")} · {operation.initiator}</small><p>{operation.message}</p>
          {operation.action === "alternates" && <details className="networkAlternatesHistory">
            <summary>Альтернейты: было / {operation.status === "confirmed" ? "стало" : "запрошено"}</summary>
            <div className="networkAlternatesComparison">
              <div><strong>Было</strong>{operation.alternates_before ? <>
                <pre>{operation.alternates_before.markup || "Разметка пустая"}</pre>
              </> : <p className="muted">Исходные альтернейты не сохранены.</p>}</div>
              <div><strong>{operation.status === "confirmed" ? "Стало" : "Запрошено"}</strong>{operation.alternates_after ? <>
                <pre>{operation.alternates_after.markup || "Разметка пустая"}</pre>
              </> : <p className="muted">Данные не сохранены.</p>}</div>
            </div>
          </details>}
          {(operation.action === "domain_redirect" || operation.action === "domain_redirects_main" || operation.action === "reglue_redirects" || operation.action === "reglue" && operation.redirects_before) && <details className="networkAlternatesHistory"><summary>Редиректы: было / {operation.status === "confirmed" ? "стало" : "запрошено"}</summary><div className="networkAlternatesComparison">{[operation.redirects_before,operation.redirects_after].map((rows,index)=><div key={index}><strong>{index?"Стало / запрошено":"Было"}</strong>{rows?.map((row,i)=><p key={i}>{row.url} → {row.value}</p>)}</div>)}</div></details>}
          {operation.action === "indexing" && <>{operation.task_id && <p>Номер задачи: <strong>{operation.task_id}</strong></p>}<details><summary>Домены для индексации ({operation.domains?.length || 0})</summary><ul>{operation.domains?.map(domain => <li key={domain}>{domain}</li>)}</ul></details></>}
          {operation.action === 'page_redirect' && <details className="networkAlternatesHistory"><summary>Постраничные редиректы: было / {operation.status==='confirmed'?'стало':'запрошено'}</summary><div className="networkAlternatesComparison">{[operation.page_redirects_before,operation.page_redirects_after].map((groups,i)=><div key={i}><strong>{i?'Стало / запрошено':'Было'}</strong>{groups?.flatMap(g=>g.redirects.map((r,j)=><p key={`${g.domain}:${j}`}>{g.domain}{r.url} → {r.value}</p>))}</div>)}</div></details>}
        </li>;})}</ul>;
          return activeOnly ? <div key="active">{list}</div> : <details key="history"><summary>Завершённые операции ({entries.length})</summary>{list}</details>;
          })}</div>}
      </>}
      {(data?.added_to_system_at || site.added_to_system_at) && <p className="networkSystemAdded">Добавлен в систему: <time dateTime={data?.added_to_system_at || site.added_to_system_at || undefined}>{new Date((data?.added_to_system_at || site.added_to_system_at)!).toLocaleDateString("ru-RU", { timeZone: "Europe/Moscow" })}</time></p>}
    </div>
  </section>;
}
