import { openDetailPage } from "./detailNavigation";
import { PageContentTools } from "./PageContentTools";
import React from "react";
import { ArrowLeft, ArrowDown, ArrowUp, Check, ChevronRight, Copy, ExternalLink, FileText, Home, Link2, Plus, RefreshCcw, Save, Search, Trash2, X } from "lucide-react";
import { TemplateCombobox } from "./TemplateCombobox";
import { ShortcodeSidebar, type ShortcodeInfo } from "./ShortcodeSidebar";
import { clearPageDraft, editablePageFingerprint, newestPageDraft, pageDraftStorageKey, persistPageDraft, preparePageDraft, readPageDraft, recoverPageSave, writePageDraft, type SavedPageDraft } from "./pageEditorDraft";
import "./styles/project-pages.css";

type Api = <T>(path: string, init?: RequestInit) => Promise<T>;
type Value = string | number | boolean | null | Value[] | { [key: string]: Value };
type Block = { id?: string; type: string; data: Value; [key: string]: unknown };
export type PageRow = { key: string; title: string; slug: string; is_home: boolean; created_at?: string | number | null; created_at_source?: string; published_at?: string | number | null; updated_at?: string | number | null };
type Page = PageRow & { shortcodes?:ShortcodeInfo[]; source?: string; warning?: string; description: string; content: { blocks: Block[]; [key: string]: unknown }; revision: string };
type AutolinkEntry = PageRow & { status: string; message: string; paragraph: string; block_index: number | null; block_id?: string | null };
type AutolinkReport = { id: string; status: string; error?: string | null; entries: AutolinkEntry[] };
type Result = { id: string; status: string; background?: boolean; error?: string; page?: Page };
type ServerPageDraft = {id:string;revision:string;title:string;description:string;content:Page["content"];created_at:string;updated_at:string;operation?:Result|null};
const errorText = (e: unknown) => e instanceof Error ? e.message : "Не удалось выполнить запрос";
const browserDraftStorage = () => {try{return window.localStorage;}catch{return null;}};
const blockNames: Record<string, string> = { paragraph: "Абзац", header: "Заголовок", list: "Список", table: "Таблица", faq: "Вопросы и ответы", image: "Изображение", button: "Кнопка", shortcode: "Шорткод", raw: "HTML", quote: "Цитата", delimiter: "Разделитель" };
const fieldNames: Record<string, string> = { text: "Текст", level: "Уровень заголовка", items: "Пункты", content: "Содержимое", question: "Вопрос", answer: "Ответ", caption: "Подпись", url: "Адрес", file: "Файл", button: "Текст кнопки", shortcode: "Шорткод", html: "HTML-код", style: "Вид списка", withBorder: "Рамка", withBackground: "Фон", stretched: "На всю ширину", withHeadings: "Строка заголовков", alignment: "Выравнивание", checked: "Отмечено", title: "Заголовок", link: "Ссылка", meta: "Настройки" };
const defaults: Record<string, Value> = { paragraph: { text: "" }, header: { text: "", level: 2 }, list: { style: "unordered", items: [""] }, table: { withHeadings: true, content: [["", ""], ["", ""]] }, faq: [{ question: "", answer: "" }], image: { file: { url: "" }, caption: "", withBorder: false, withBackground: false, stretched: false }, button: { button: "" }, shortcode: { shortcode: "" }, raw: { html: "" }, quote: { text: "", caption: "" } };

function pageDate(value: unknown) {
  if (typeof value !== "string" && typeof value !== "number") return "—";
  if (typeof value === "string" && !value.trim()) return "—";
  const plain = typeof value === "string" && value.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::\d{2})?)?$/);
  if (plain) return `${plain[3]}.${plain[2]}.${plain[1]}${plain[4] ? `, ${plain[4]}:${plain[5]}` : ""}`;
  // Webdev's older pages use Unix milliseconds; some imports use seconds or numeric strings.
  const timestamp = typeof value === "number" ? value : /^-?\d+(?:\.\d+)?$/.test(value.trim()) ? Number(value) : null;
  const date = timestamp === null ? new Date(value) : new Date(Math.abs(timestamp) < 1e11 ? timestamp * 1000 : timestamp);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function PageTimestamps({ page }: { page: Pick<PageRow, "published_at" | "updated_at"> }) {
  return <div className="pp-page-timestamps"><span>Дата публикации: <time>{pageDate(page.published_at)}</time></span><span>Обновление контента: <time>{pageDate(page.updated_at)}</time></span></div>;
}

export function PageEditorFields({ locked, children }: {locked:boolean;children:React.ReactNode}) {
  return <fieldset disabled={locked} inert={locked} className="pp-editor-fields">{children}</fieldset>;
}

export function ProjectPages({ siteId, api, onCount }: { siteId: string; api: Api; onCount?: (siteId: string, count: number) => void }) {
  const [rows, setRows] = React.useState<PageRow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [source, setSource] = React.useState("");
  const [warning, setWarning] = React.useState("");
  const [query, setQuery] = React.useState("");
  const [selected, setSelected] = React.useState<PageRow | null>(null);
  const [linkReport, setLinkReport] = React.useState<AutolinkReport | null>(null);
  const [linkBusy, setLinkBusy] = React.useState(false);
  const [linkError, setLinkError] = React.useState("");
  const linkRequest = React.useRef<string | null>(null);
  const refreshedLinks = React.useRef("");
  const reportPath = `/sites/${siteId}/autolink-pages`;
  const linkPending = !!linkReport && (["queued", "running"].includes(linkReport.status) || linkReport.entries.some(entry => ["pending", "unknown"].includes(entry.status)));
  const loadLinkReport = React.useCallback(async () => {
    const report = await api<AutolinkReport | null>(reportPath, { cache: "no-store" });
    setLinkReport(report && !Array.isArray(report) && Array.isArray(report.entries) ? report : null);
  }, [api, reportPath]);
  React.useEffect(() => { void loadLinkReport().catch(e => setLinkError(errorText(e))); }, [loadLinkReport]);
  React.useEffect(() => { if (!linkPending) return; const timer = setInterval(() => void loadLinkReport().catch(e => setLinkError(errorText(e))), 3000); return () => clearInterval(timer); }, [linkPending, loadLinkReport]);
  async function autolink() {
    setLinkBusy(true); setLinkError("");
    const storageKey = `page-autolink-request:${siteId}`;
    const id = linkRequest.current || sessionStorage.getItem(storageKey) || crypto.randomUUID();
    linkRequest.current = id; sessionStorage.setItem(storageKey, id);
    try {
      const report = await api<AutolinkReport>(reportPath, { method: "POST", body: JSON.stringify({ request_id: id }) });
      setLinkReport(report); linkRequest.current = null; sessionStorage.removeItem(storageKey);
    } catch (e) { setLinkError(errorText(e)); }
    finally { setLinkBusy(false); }
  }

  const load = React.useCallback(async (refresh = false) => {
    setLoading(true); setError("");
    try { const result = await api<{ pages: PageRow[]; source?: string; warning?: string }>(`/sites/${siteId}/pages${refresh ? "?refresh=true" : ""}`); setSource(result.source || "webdev"); setWarning(result.warning || ""); setRows(result.pages); onCount?.(siteId, result.pages.length); }
    catch (e) { setError(errorText(e)); }
    finally { setLoading(false); }
  }, [siteId, api, onCount]);
  React.useEffect(() => { void load(); }, [load]);
  React.useEffect(() => {
    if (linkReport?.status === "completed" && !linkPending && refreshedLinks.current !== linkReport.id) {
      refreshedLinks.current = linkReport.id; void load(true);
    }
  }, [linkReport?.id, linkReport?.status, linkPending, load]);
  const linkedCount = linkReport?.entries.filter(entry => ["confirmed", "already_linked"].includes(entry.status)).length || 0;
  const failedCount = linkReport?.entries.filter(entry => entry.status === "failed").length || 0;
  const filtered = [...rows].sort((a, b) => Number(b.is_home) - Number(a.is_home)).filter(row => `${row.title} ${row.slug} ${row.is_home ? "главная" : ""}`.toLowerCase().includes(query.toLowerCase()));
  return <section className="pp-pages"><header><div><h2>Все страницы <small>{loading ? "" : rows.length}</small></h2><p>{source === "cache" ? "Страницы из серверного кеша." : "Страницы из Webdev."} Нажмите на заголовок, чтобы открыть редактор.</p></div><div className="pp-page-list-actions"><div className="pp-autolink-action"><button className="button secondary" disabled={loading || linkBusy || linkPending} onClick={() => void autolink()}><Link2 size={16} />{linkBusy || linkPending ? "Перелинковка…" : "Автоперелинковка"}</button>{linkReport && <small role="status">Удача — {linkedCount} · Неудача — {failedCount}{linkPending ? " · Обработка…" : ""}</small>}</div><button className="button secondary" disabled={loading} onClick={() => void load(true)}><RefreshCcw size={16} />Обновить список</button></div></header>
    <label className="pp-page-search"><Search size={18} /><input aria-label="Поиск страниц" placeholder="Заголовок или адрес страницы" value={query} onChange={e => setQuery(e.target.value)} /></label>
    {linkError && <p className="pp-page-error" role="alert">{linkError}</p>}
    {linkReport?.error && <p className="pp-page-error" role="alert">{linkReport.error}</p>}
    {warning && <p role="status">{warning}</p>}
    {error && <p className="pp-page-error" role="alert">{error}</p>}
    {loading ? <p role="status">Загружаем страницы из Webdev…</p> : (!error || rows.length > 0) && <div className="pp-page-list">{filtered.map(row => <button key={row.key} className="pp-page-row" onClick={() => setSelected(row)}>{row.is_home ? <Home size={21} /> : <FileText size={21} />}<span className="pp-page-title"><strong>{row.title}</strong><small>{row.is_home && <b>Главная</b>}{row.slug}</small></span><span className="pp-page-date" title={row.created_at_source === "publishedTime" ? "Дата публикации из Webdev: отдельная дата создания не передана" : "Дата создания из Webdev"}><small>Дата создания</small><time>{pageDate(row.created_at)}</time></span><span className="pp-page-date"><small>Дата обновления</small><time>{pageDate(row.updated_at)}</time></span><ChevronRight size={18} /></button>)}{!filtered.length && <p>{rows.length ? "Страницы не найдены. Измените запрос." : "В Webdev пока нет страниц этого проекта."}</p>}</div>}
    {!!linkReport?.entries.length && <section className="pp-autolink-report" aria-label="Отчёт по автоперелинковке"><h3>Перелинковка</h3>{linkReport.entries.map(entry => <article className="pp-autolink-entry" key={entry.key}><header><div><strong>{entry.title}</strong><small>{entry.slug} · {["confirmed", "already_linked"].includes(entry.status) ? "Удача" : ["pending", "unknown"].includes(entry.status) ? "Проверяем" : "Неудача"}</small></div><button type="button" className="button secondary compact" onClick={() => openDetailPage(`/page-editor/${encodeURIComponent(siteId)}/${encodeURIComponent(entry.key)}/`, entry.block_id != null || entry.block_index != null ? { block: entry.block_id || String(entry.block_index) } : {})}>Редактировать</button></header><div className="pp-autolink-paragraph" onClick={event => { if ((event.target as HTMLElement).closest("a")) event.preventDefault(); }} dangerouslySetInnerHTML={{ __html: inlineHTML(entry.paragraph) }} /><small>{entry.message || "Абзац для ручного добавления ссылки."}</small></article>)}</section>}
    {selected && <PageEditor key={selected.key} siteId={siteId} row={selected} api={api} onClose={() => setSelected(null)} onSaved={page => setRows(current => current.map(row => row.key === page.key ? page : row))} />}
  </section>;
}

// Preview only safe inline formatting. The original stored HTML is kept until the user edits it.
function inlineHTML(value: string) {
  const doc = document.createElement("template"); doc.innerHTML = value;
  const visit = (node: Node): string => {
    if (node.nodeType === Node.TEXT_NODE) return (node.textContent || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    if (!(node instanceof Element)) return "";
    if (["SCRIPT", "STYLE", "IFRAME", "OBJECT", "SVG", "MATH", "IMG"].includes(node.tagName)) return "";
    const children = Array.from(node.childNodes).map(visit).join("");
    if (node.tagName === "A") {
      const href = node.getAttribute("href") || "";
      if (/^(https?:\/\/|\/(?!\/)|#|mailto:)/i.test(href)) return `<a href="${href.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;")}">${children}</a>`;
    }
    if (node.tagName === "BR") return "<br>";
    if (["B", "STRONG", "I", "EM", "U", "S", "SUB", "SUP"].includes(node.tagName)) return `<${node.tagName.toLowerCase()}>${children}</${node.tagName.toLowerCase()}>`;
    return children + (["DIV", "P", "LI"].includes(node.tagName) ? "<br>" : "");
  };
  return Array.from(doc.content.childNodes).map(visit).join("");
}

function TextField({ label, value, onChange, rich = false }: { label: string; value: string; onChange: (value: string) => void; rich?: boolean }) {
  const [source, setSource] = React.useState(false);
  const editor = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => { if (editor.current && document.activeElement !== editor.current) editor.current.innerHTML = inlineHTML(value); }, [value, source]);
  if (!rich && label==='Шорткод' && !value.includes('\n')) return <label className="pp-shortcode-field">{label}<input aria-label={label} spellCheck={false} value={value} onChange={e=>onChange(e.target.value)}/></label>;
  if (!rich) return <label>{label}<textarea aria-label={label} rows={value.length > 150 || value.includes("\n") ? 4 : 2} value={value} onChange={e => onChange(e.target.value)} /></label>;
  return <div className="pp-text-field"><div className="pp-text-toolbar"><span>{label}</span><button type="button" onClick={() => setSource(!source)}>{source ? "Визуальный режим" : "HTML текста"}</button>{!source && <><button type="button" aria-label={`Жирный: ${label}`} onMouseDown={e => { e.preventDefault(); editor.current?.focus(); document.execCommand("bold"); if (editor.current) onChange(editor.current.innerHTML); }}><b>B</b></button><button type="button" aria-label={`Курсив: ${label}`} onMouseDown={e => { e.preventDefault(); editor.current?.focus(); document.execCommand("italic"); if (editor.current) onChange(editor.current.innerHTML); }}><i>I</i></button><button type="button" aria-label={`Добавить ссылку: ${label}`} onMouseDown={e => { e.preventDefault(); const selection = window.getSelection(); const range = selection?.rangeCount ? selection.getRangeAt(0).cloneRange() : null; const url = window.prompt("Адрес ссылки (https:// или /путь/)"); if (!url) return; if (!/^(https?:\/\/|\/(?!\/)|#|mailto:)/i.test(url.trim())) { window.alert("Укажите безопасный адрес ссылки."); return; } editor.current?.focus(); if (range && selection) { selection.removeAllRanges(); selection.addRange(range); } document.execCommand("createLink", false, url.trim()); if (editor.current) onChange(editor.current.innerHTML); }}>Ссылка</button></>}</div>
    {source ? <textarea aria-label={`${label}: HTML`} rows={5} value={value} onChange={e => onChange(e.target.value)} /> : <div ref={editor} role="textbox" aria-label={label} aria-multiline="true" className="pp-rich-text" contentEditable suppressContentEditableWarning onInput={e => onChange(e.currentTarget.innerHTML)} onPaste={e => { e.preventDefault(); document.execCommand("insertText", false, e.clipboardData.getData("text/plain")); }} />}
  </div>;
}
function emptyLike(value: Value): Value {
  if (typeof value === "string") return "";
  if (Array.isArray(value)) return value.map(emptyLike);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, emptyLike(v)]));
  return value;
}
function Fields({ value, label, onChange, name = "" }: { value: Value; label: string; onChange: (value: Value) => void; name?: string }) {
  if (typeof value === "string") {
    if (name === "style" && ["ordered", "unordered", "checklist"].includes(value)) return <TemplateCombobox label={label} value={value} options={[{ value: "unordered", label: "Маркированный" }, { value: "ordered", label: "Нумерованный" }, { value: "checklist", label: "Чек-лист" }]} onChange={onChange} />;
    return <TextField label={label} value={value} onChange={onChange} rich={["text", "question", "answer", "caption", "items", "content"].includes(name)} />;
  }
  if (typeof value === "boolean") return <label className="pp-checkbox"><input type="checkbox" checked={value} onChange={e => onChange(e.target.checked)} />{label}</label>;
  if (typeof value === "number") return <label>{label}<input type="number" aria-label={label} value={value} onChange={e => { if (e.target.value !== "") onChange(Number(e.target.value)); }} /></label>;
  if (Array.isArray(value)) return <div className="pp-nested"><strong>{label}</strong>{value.map((item, i) => <div key={i} className="pp-array-item"><Fields value={item} label={`${label} ${i + 1}`} name={name} onChange={next => onChange(value.map((old, j) => i === j ? next : old))} /><button className="pp-icon" type="button" title="Удалить элемент" aria-label={`Удалить ${label} ${i + 1}`} onClick={() => onChange(value.filter((_, j) => i !== j))}><Trash2 size={15} /></button></div>)}<button type="button" className="button secondary compact" onClick={() => onChange([...value, value.length ? emptyLike(value[value.length - 1]) : name === "faq" ? { question: "", answer: "" } : name === "content" ? [""] : ""])}><Plus size={14} />Добавить элемент</button></div>;
  if (value && typeof value === "object") return <div className="pp-field-group">{Object.entries(value).map(([key, field]) => <Fields key={key} value={field} name={key} label={fieldNames[key] || key} onChange={next => onChange({ ...value, [key]: next })} />)}</div>;
  return <small>{label}: не задано</small>;
}

export function DocumentBlock({ block, onChange }: { block: Block; onChange: (data: Value) => void }) {
  const data = block.data;
  if (data && !Array.isArray(data) && typeof data === "object") {
    if (block.type === "button" && typeof data.button === "string") return <div className="pp-document-button"><input type="text" className="pp-document-button-input" aria-label="Текст кнопки" title="Редактировать текст кнопки" placeholder="Текст кнопки" size={Math.min(80, Math.max(12, Array.from(data.button).length + 2))} value={data.button} onChange={event => onChange({ ...data, button: event.target.value })} /></div>;
    if(block.type==='shortcode' && typeof data.shortcode==='string') return <TextField label="Шорткод" value={data.shortcode} onChange={shortcode=>onChange({...data,shortcode})}/>;
    if (["paragraph", "header", "quote"].includes(block.type) && typeof data.text === "string") {
      return <div className={`pp-document-text pp-document-${block.type}`} data-level={Number(data.level) || 2}><TextField label="Текст" value={data.text} rich onChange={text => onChange({ ...data, text })} />{block.type === "quote" && typeof data.caption === "string" ? <TextField label="Подпись" value={data.caption} rich onChange={caption => onChange({ ...data, caption })} /> : null}</div>;
    }
    if (block.type === "table" && Array.isArray(data.content) && data.content.every(row => Array.isArray(row) && row.every(cell => typeof cell === "string"))) {
      const rows = data.content as string[][];
      return <div className="pp-document-table"><table><tbody>{rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j} className={data.withHeadings && i === 0 ? "pp-document-th" : ""}><TextField label={`Ячейка ${i + 1}, ${j + 1}`} value={cell} rich onChange={text => onChange({ ...data, content: rows.map((r, ri) => ri === i ? r.map((c, ci) => ci === j ? text : c) : r) })} /></td>)}</tr>)}</tbody></table></div>;
    }
    if (block.type === "list" && Array.isArray(data.items)) {
      const items = data.items;
      return <DocumentList items={items} ordered={data.style === "ordered"} onChange={next => onChange({ ...data, items: next })} />;
    }
  }
  if (block.type === "faq" && Array.isArray(data) && data.every(item => item && !Array.isArray(item) && typeof item === "object" && typeof item.question === "string" && typeof item.answer === "string")) {
    return <div className="pp-document-faq">{data.map((item, i) => {
      const entry = item as Record<string, Value>;
      return <div key={i}><TextField label={`Вопрос ${i + 1}`} value={entry.question as string} rich onChange={question => onChange(data.map((old, j) => i === j ? { ...entry, question } : old))} /><TextField label={`Ответ ${i + 1}`} value={entry.answer as string} rich onChange={answer => onChange(data.map((old, j) => i === j ? { ...entry, answer } : old))} /></div>;
    })}</div>;
  }
  return <Fields value={data} label={blockNames[block.type] || block.type} name={block.type} onChange={onChange} />;
}

function DocumentList({ items, ordered, onChange }: { items: Value[]; ordered: boolean; onChange: (items: Value[]) => void }) {
  const Tag = ordered ? "ol" : "ul";
  return <Tag className="pp-document-list">{items.map((item, index) => <li key={index}>{typeof item === "string" ? <TextField label={`Пункт ${index + 1}`} value={item} rich onChange={text => onChange(items.map((old, i) => i === index ? text : old))} /> : item && !Array.isArray(item) && typeof item === "object" && typeof item.content === "string" ? <><TextField label={`Пункт ${index + 1}`} value={item.content} rich onChange={content => onChange(items.map((old, i) => i === index ? { ...item, content } : old))} />{Array.isArray(item.items) && item.items.length > 0 ? <DocumentList items={item.items} ordered={ordered} onChange={children => onChange(items.map((old, i) => i === index ? { ...item, items: children } : old))} /> : null}</> : <Fields value={item} label={`Пункт ${index + 1}`} onChange={next => onChange(items.map((old, i) => i === index ? next : old))} />}</li>)}</Tag>;
}

export function PageEditor({ siteId, row, api, onClose, onSaved, breadcrumbs, returnPosition, fullPage = false, draftActorId }: { draftActorId?:string; fullPage?: boolean; siteId: string; row: PageRow; api: Api; onClose: () => void; onSaved: (page: Page) => void; breadcrumbs?: { label: string; onClick: () => void }[]; returnPosition?: { left: number; top: number } }) {
  const [page, setPage] = React.useState<Page | null>(null);
  const [original, setOriginal] = React.useState("");
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const [operation, setOperation] = React.useState<Result | null>(null);
  const [message, setMessage] = React.useState("");
  const [documentMode, setDocumentMode] = React.useState(true);
  const [settingsBlock, setSettingsBlock] = React.useState<number | null>(null);
  const [shortcodes,setShortcodes] = React.useState<ShortcodeInfo[]>([]);
  const [newType, setNewType] = React.useState("paragraph");
  const dialog = React.useRef<HTMLDivElement>(null);
  const routeExitApproved = React.useRef(false);
  const actorId = React.useRef<string|null>(draftActorId||null);
  const draftKey = React.useRef<string|null>(null);
  const savedDraft = React.useRef<SavedPageDraft|null>(null);
  const loadSequence = React.useRef(0);
  const initialRow = React.useRef(row);initialRow.current=row;
  const [durableFingerprint,setDurableFingerprint] = React.useState("");
  const [draftLocation,setDraftLocation] = React.useState("");
  const fingerprint=page?editablePageFingerprint(page):"";
  const isHome=page?.is_home??row.is_home;
  const slug=page?.slug||row.slug;
  const [siteBaseUrl, setSiteBaseUrl] = React.useState("");
  React.useEffect(() => {
    let active = true;
    setSiteBaseUrl("");
    void api<{cache_canon?: string | null; base_url: string; name: string}>(`/sites/lookup?site_id=${encodeURIComponent(siteId)}`).then(site => {
      const base = (site.cache_canon || site.base_url || site.name).trim();
      const url = new URL(/^https?:\/\//i.test(base) ? base : `https://${base}`);
      if (active) setSiteBaseUrl(url.origin);
    }).catch(() => { /* The editor remains usable if the site address is unavailable. */ });
    return () => { active = false; };
  }, [api, siteId]);
  const publicPageUrl = React.useMemo(() => {
    if (!siteBaseUrl || (!isHome && !slug)) return "";
    try {
      const path = new URL(isHome ? "/" : slug, `${siteBaseUrl}/`);
      return `${siteBaseUrl}${path.pathname}${path.search}${path.hash}`;
    } catch { return ""; }
  }, [siteBaseUrl, isHome, slug]);
  const dirty = !!page && fingerprint !== original;
  const unsavedChanges = !!page && fingerprint !== (durableFingerprint || original);
  const path = `/sites/${siteId}/pages/${row.key}`;
  const unresolved = operation && ["pending", "unknown"].includes(operation.status);
  const load = React.useCallback(async (refresh = true) => {
    const sequence=++loadSequence.current;
    setLoading(true); setError(""); setMessage("");
    try {
      const [liveResult,actorResult,draftResult]=await Promise.allSettled([
        api<Page>(path+(refresh?"?refresh=true":"")),draftActorId?Promise.resolve({id:draftActorId}):api<{id:string}>("/auth/me"),api<ServerPageDraft|null>(`${path}/draft`),
      ]);
      if(sequence!==loadSequence.current)return;
      actorId.current=actorResult.status==="fulfilled"&&actorResult.value.id?String(actorResult.value.id):null;
      draftKey.current=actorId.current?pageDraftStorageKey(actorId.current,siteId,initialRow.current.key):null;
      const storage=browserDraftStorage();
      const local=storage&&draftKey.current?readPageDraft(storage,draftKey.current):null;
      const server=draftResult.status==="fulfilled"?draftResult.value:null;
      const serverDraft:SavedPageDraft|null=server?{request_id:server.id,revision:server.revision,title:server.title,description:server.description,content:server.content,saved_at:server.updated_at||server.created_at,status:server.operation?.status==="failed"?"failed":server.operation&&["pending","unknown"].includes(server.operation.status)?server.operation.status as "pending"|"unknown":"draft"}:null;
      let draft=newestPageDraft(local,serverDraft);
      let receipt=draft&&server?.id===draft.request_id?server.operation:null;
      let recoveryError="";
      if(draft&&(!server||server.id!==draft.request_id||server.operation===undefined)){
        const recovered=await recoverPageSave<Page>(draft,id=>api<Result>(`${path}/edits/${id}`));
        draft=recovered.draft;receipt=recovered.operation;
        if(recovered.error&&!recovered.notFound)recoveryError=errorText(recovered.error);
      }
      if(sequence!==loadSequence.current)return;
      const live=liveResult.status==="fulfilled"?liveResult.value:null;
      setShortcodes(live?.shortcodes||[]);setOriginal(live?editablePageFingerprint(live):"");
      if(receipt?.status==="confirmed"&&receipt.page){
        if(storage&&draftKey.current)clearPageDraft(storage,draftKey.current,receipt.id);
        savedDraft.current=null;setDurableFingerprint("");setDraftLocation("");setOperation(receipt);
        setPage(receipt.page);setOriginal(editablePageFingerprint(receipt.page));setMessage("Изменения сохранены на сайте и подтверждены.");
      }else if(draft){
        if(receipt)draft={...draft,status:receipt.status==="failed"?"failed":["pending","unknown"].includes(receipt.status)?receipt.status as "pending"|"unknown":"draft"};
        else if(server?.id===draft.request_id&&server.operation===null)draft={...draft,status:"draft"};
        savedDraft.current=draft;
        if(storage&&draftKey.current)writePageDraft(storage,draftKey.current,draft);
        const location=server?.id===draft.request_id?"в системе":"в этом браузере";
        setDraftLocation(location);setDurableFingerprint(editablePageFingerprint(draft));
        setPage({...initialRow.current,...live,title:draft.title,description:draft.description,content:draft.content as Page["content"],revision:draft.revision});
        setOperation(receipt||(["pending","unknown"].includes(draft.status)?{id:draft.request_id,status:draft.status}:null));
        setMessage(receipt?.background&&receipt.status==="pending"?"Сохраняем в фоне. Можно покинуть страницу.":`Восстановлен черновик, сохранённый ${location}.`);
        setError(recoveryError||receipt?.error||(!receipt?.background&&["pending","unknown"].includes(draft.status)?"Результат публикации пока не подтверждён. Проверьте сохранение.":""));
      }else{
        savedDraft.current=null;setDurableFingerprint("");setDraftLocation("");setOperation(null);setPage(live);
      }
      if(!live&&liveResult.status==="rejected"&&!(receipt?.status==="confirmed"&&receipt.page))setError(errorText(liveResult.reason));
      else if(draftResult.status==="rejected"&&!draft)setError("Не удалось загрузить сохранённый черновик. "+errorText(draftResult.reason));
      if(actorResult.status==="rejected")setError(current=>[current,"Не удалось проверить локальный черновик. Повторите загрузку страницы."].filter(Boolean).join(" "));
    }
    catch (e) { setError(errorText(e)); }
    finally { if(sequence===loadSequence.current)setLoading(false); }
  }, [api, path,siteId,draftActorId]);
  React.useEffect(() => { if (fullPage) void load(); else openDetailPage(`/page-editor/${encodeURIComponent(siteId)}/${encodeURIComponent(row.key)}/`);return()=>{loadSequence.current++;}; }, [fullPage, load, siteId, row.key]);
  const leave = React.useCallback((navigate: () => void) => { if ((!unsavedChanges || window.confirm("Есть несохранённые изменения. Закрыть редактор без сохранения?"))) { routeExitApproved.current = true; navigate(); } }, [unsavedChanges]);
  const close = React.useCallback(() => leave(onClose), [leave, onClose]);
  React.useEffect(() => {
    if (fullPage) return;
    const previous = document.activeElement as HTMLElement;
    const position = returnPosition || { left: window.scrollX, top: window.scrollY };
    const overflow = document.body.style.overflow; document.body.style.overflow = "hidden"; dialog.current?.focus({ preventScroll: true });
    return () => { document.body.style.overflow = overflow; previous?.focus({ preventScroll: true }); window.scrollTo({ ...position, behavior: "instant" }); };
  }, []);
  React.useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (!routeExitApproved.current && unsavedChanges) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn);
  }, [unsavedChanges]);
  React.useLayoutEffect(() => {
    if (!fullPage) return;
    const address = window.location.href, state = window.history.state;
    const guard = (event: PopStateEvent) => {
      if (routeExitApproved.current || !unsavedChanges) return;
      if (window.confirm("Есть несохранённые изменения. Выйти без сохранения?")) return;
      event.stopImmediatePropagation(); window.history.pushState(state, "", address);
    };
    window.addEventListener("popstate", guard, true);
    return () => window.removeEventListener("popstate", guard, true);
  }, [fullPage, unsavedChanges, busy]);
  React.useEffect(() => {
    if (!fullPage || !page) return;
    const target = new URLSearchParams(window.location.search).get("block");
    if (target == null) return;
    const index = page.content?.blocks?.findIndex((block, index) => (block.id || String(index)) === target);
    if (index == null || index < 0) return;
    const element = document.getElementById(`page-editor-block-${index}`);
    element?.scrollIntoView({ block: "center" });
    element?.querySelector<HTMLElement>('[contenteditable="true"],textarea,input')?.focus({ preventScroll: true });
  }, [fullPage, page?.revision]);
  function handleKeys(event: React.KeyboardEvent) {
    if (event.key === "Escape" && !(event.target as HTMLElement).closest('.tg-combobox')) { event.stopPropagation(); close(); }
    if (!fullPage && event.key === "Tab") {
      const items = Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), [contenteditable="true"], [tabindex="0"]') || []).filter(el => el.offsetParent !== null && !el.closest('fieldset:disabled'));
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  }
  async function receive(result: Result) {
    setOperation(result);
    if (result.status === "confirmed") {
      if(!result.page){setOperation({...result,status:"unknown"});setError("Сохранение подтверждено, но сервер не вернул сохранённую страницу. Проверьте результат ещё раз.");return;}
      const storage=browserDraftStorage();
      if(storage&&draftKey.current)clearPageDraft(storage,draftKey.current,result.id);
      if(savedDraft.current?.request_id===result.id)savedDraft.current=null;
      setDurableFingerprint("");setDraftLocation("");
      const next=result.page;setPage(next);setOriginal(editablePageFingerprint(next));onSaved(next);setMessage("Изменения сохранены в Webdev и подтверждены.");setError("");
    } else if(result.status === "pending" && result.background) {
      if(savedDraft.current?.request_id===result.id){
        savedDraft.current={...savedDraft.current,status:"pending"};
        const storage=browserDraftStorage();if(storage&&draftKey.current)writePageDraft(storage,draftKey.current,savedDraft.current);
      }
      setError("");setMessage("Сохраняем в фоне. Можно покинуть страницу; результат появится в проекте.");
    } else {
      if(savedDraft.current?.request_id===result.id){
        savedDraft.current={...savedDraft.current,status:result.status==="failed"?"failed":"unknown"};
        const storage=browserDraftStorage();if(storage&&draftKey.current)writePageDraft(storage,draftKey.current,savedDraft.current);
      }
      setError(result.error || "Сохранение ещё не подтверждено. Проверьте результат.");
    }
  }
  const receiveLatest=React.useRef(receive);receiveLatest.current=receive;
  React.useEffect(()=>{
    if(!operation?.background||operation.status!=="pending")return;
    let stopped=false;let timer:ReturnType<typeof setTimeout>;
    const poll=async()=>{
      try{const value=await api<Result>(`${path}/edits/${operation.id}`);if(stopped)return;await receiveLatest.current(value);if(value.status!=="pending")return;}
      catch{/* The server keeps the job; a transient polling failure does not resend it. */}
      if(!stopped)timer=setTimeout(poll,4000);
    };
    timer=setTimeout(poll,2000);
    return()=>{stopped=true;clearTimeout(timer);};
  },[api,path,operation?.id,operation?.background,operation?.status]);
  async function save() {
    if (!page) return;
    setBusy(true); setError(""); setMessage("");
    const draft=preparePageDraft(page,savedDraft.current,()=>crypto.randomUUID());
    let publicationStarted=false;
    try {
      if(!actorId.current){
        try{const actor=await api<{id:string}>("/auth/me");actorId.current=actor.id?String(actor.id):null;}
        catch{/* The server draft can still protect edits if actor lookup is temporarily unavailable. */}
      }
      draftKey.current=actorId.current?pageDraftStorageKey(actorId.current,siteId,row.key):null;
      const storage=browserDraftStorage();
      const persisted=await persistPageDraft({draft,storage,key:draftKey.current,
        saveServer:payload=>api(`${path}/draft`,{method:"PUT",body:JSON.stringify(payload)}),
        onLocalSaved:()=>{savedDraft.current=draft;setDurableFingerprint(editablePageFingerprint(draft));setDraftLocation("в этом браузере");setMessage("Черновик сохранён в этом браузере.");},
      });
      if(!persisted.local&&!persisted.server)throw new Error("Не удалось сохранить черновик. Изменения остаются в редакторе: скопируйте их перед выходом. "+errorText(persisted.error));
      savedDraft.current=draft;setDurableFingerprint(editablePageFingerprint(draft));
      if(persisted.server){setDraftLocation("в системе");setMessage("Черновик сохранён в системе.");}
      const draftErrorStatus=(persisted.error as {statusCode?:number}|undefined)?.statusCode;
      if(draftErrorStatus&&draftErrorStatus<500)throw persisted.error;
      savedDraft.current={...draft,status:"unknown"};
      if(storage&&draftKey.current)writePageDraft(storage,draftKey.current,savedDraft.current);
      const {request_id,revision,title,description,content}=draft;
      publicationStarted=true;setOperation({id:request_id,status:"unknown"});
      await receive(await api<Result>(path+"?background=true",{method:"PUT",body:JSON.stringify({request_id,revision,title,description,content})}));
    }
    catch (e) {
      setError(errorText(e));
      const status = (e as { statusCode?: number })?.statusCode;
      const uncertain=publicationStarted&&(!status||status>=500);
      setOperation(uncertain?{id:draft.request_id,status:"unknown"}:null);
      if(savedDraft.current?.request_id===draft.request_id){
        savedDraft.current={...savedDraft.current,status:uncertain?"unknown":"draft"};
        const storage=browserDraftStorage();if(storage&&draftKey.current)writePageDraft(storage,draftKey.current,savedDraft.current);
      }
    }
    finally { setBusy(false); }
  }
  async function check() {
    if (!operation) return;
    setBusy(true); setError("");
    try {
      if(savedDraft.current?.request_id===operation.id){
        const recovered=await recoverPageSave<Page>(savedDraft.current,id=>api<Result>(`${path}/edits/${id}`));
        savedDraft.current=recovered.draft;
        const storage=browserDraftStorage();if(storage&&draftKey.current)writePageDraft(storage,draftKey.current,recovered.draft);
        if(recovered.notFound){setOperation(null);setError("Запись о сохранении не найдена. Черновик сохранён — нажмите «Сохранить на сайте», чтобы повторить отправку.");}
        else if(recovered.error){setOperation(recovered.operation);setError(errorText(recovered.error));}
        else if(recovered.operation)await receive(recovered.operation);
      }else await receive(await api<Result>(`${path}/edits/${operation.id}`));
    }
    catch (e) {
      if((e as {statusCode?:number})?.statusCode===404){
        setOperation(null);
        if(savedDraft.current?.request_id===operation.id){
          savedDraft.current={...savedDraft.current,status:"draft"};
          const storage=browserDraftStorage();if(storage&&draftKey.current)writePageDraft(storage,draftKey.current,savedDraft.current);
        }
        setError("Запись о сохранении не найдена. Черновик сохранён — нажмите «Сохранить на сайте», чтобы повторить отправку.");
      }else setError(errorText(e));
    }
    finally { setBusy(false); }
  }
  async function reloadFromSite(){
    if(busy)return;
    const draft=savedDraft.current;
    if(draft&&!window.confirm("Загрузить версию с сайта? Сохранённый черновик будет удалён."))return;
    if(!draft&&unsavedChanges&&!window.confirm("Загрузить актуальную страницу из Webdev? Несохранённые изменения будут потеряны."))return;
    if(draft){
      setBusy(true);setError("");
      try{
        try{await api(`${path}/draft/${encodeURIComponent(draft.request_id)}`,{method:"DELETE"});}
        catch(error){if((error as {statusCode?:number})?.statusCode!==404)throw error;}
        const storage=browserDraftStorage();if(storage&&draftKey.current)clearPageDraft(storage,draftKey.current,draft.request_id);
        savedDraft.current=null;setDurableFingerprint("");setDraftLocation("");
      }catch(error){setError("Черновик сохранён. Не удалось загрузить версию с сайта: "+errorText(error));return;}
      finally{setBusy(false);}
    }
    await load(true);
  }
  function blocks(next: Block[]) { if (page) setPage({ ...page, content: { ...page.content, blocks: next } }); }
  const validContent = page?.content && Array.isArray(page.content.blocks);
  if (!fullPage) return null;
  return <div className={`pp-page-editor pp-page-editor-route ${documentMode ? "pp-document-mode" : ""}`} ref={dialog} tabIndex={-1} role="region" aria-label={`Редактор страницы: ${page?.title || row.title}`} onKeyDown={handleKeys}>
    <header className="pp-editor-header"><div><button type="button" className="pp-editor-back" onClick={close}><ArrowLeft size={16} />Назад</button><nav className="pp-editor-breadcrumbs" aria-label="Хлебные крошки редактора"><ol>{(breadcrumbs || [{ label: "Все страницы", onClick: onClose }]).map((item, index) => <li key={index}><button type="button" onClick={() => leave(item.onClick)}>{item.label}</button><ChevronRight size={13} aria-hidden="true" /></li>)}<li aria-current="page">{isHome ? "Главная страница" : (page?.title || row.title)}</li></ol></nav><h2>{page?.title || row.title}</h2><small>{slug}</small></div><div className="pp-editor-actions"><button type="button" className="button secondary" disabled={!publicPageUrl} title={publicPageUrl || "Адрес страницы недоступен"} onClick={() => window.open(publicPageUrl, "_blank", "noopener,noreferrer")}><ExternalLink size={16} />Посмотреть на сайте</button><button type="button" className="button secondary" disabled={busy || !!unresolved} onClick={() => void reloadFromSite()}><RefreshCcw size={16} />Загрузить заново</button><button type="button" className="button primary" disabled={(!dirty && !unsavedChanges) || busy || loading || !!unresolved || !validContent} onClick={() => void save()}><Save size={16} />{operation?.background&&unresolved ? "Сохраняем в фоне…" : busy ? "Отправляем…" : "Сохранить на сайте"}</button><button className="pp-icon" type="button" aria-label="Закрыть редактор" onClick={close}><X size={24} /></button></div></header>
    <main className="pp-editor-main">{loading && <p role="status">Загрузка страницы…</p>}{error && <div className="pp-page-error" role="alert">{error}{unresolved && <button className="button secondary" disabled={busy} onClick={() => void check()}>Проверить сохранение</button>}</div>}{message && <p role="status" className="pp-page-success"><Check size={18} />{message}</p>}
      {!loading && page && <><div className="pp-shortcode-layout"><ShortcodeSidebar content={page.content} catalog={shortcodes} onNavigate={index=>{const element=document.getElementById(`page-editor-block-${index}`);element?.scrollIntoView({block:"center",behavior:"smooth"});element?.querySelector<HTMLElement>('input,textarea,[contenteditable="true"]')?.focus({preventScroll:true});}}/><div className="pp-editor-content"><div className="pp-editor-info"><span>{unsavedChanges ? "Есть несохранённые изменения" : dirty ? `Черновик сохранён ${draftLocation}; ещё не опубликован` : "Загружена сохранённая версия"} · Изменения публикуются кнопкой «Сохранить на сайте».</span><button type="button" className="button secondary compact" onClick={() => void navigator.clipboard.writeText(JSON.stringify({ title: page.title, description: page.description, content: page.content }, null, 2)).then(() => setMessage("Черновик скопирован")).catch(() => setError("Браузер не разрешил копирование."))}><Copy size={14} />Скопировать черновик</button></div>
      {page?.source === "cache" && <p className="muted" role="status">{page.warning || "Сохранённая версия из серверного кеша. При сохранении проверяется актуальная версия в Webdev."}</p>}
      {validContent && <details className="pp-editor-tools-disclosure"><summary>Инструменты · AI, перелинковка и история версий</summary><PageContentTools api={api} path={path} isHome={isHome} content={page.content} metadata={{ title: page.title, description: page.description }} revision={page.revision} disabled={busy || !!unresolved}
        applyContent={content => setPage(current => current ? { ...current, content: content as Page["content"] } : current)}
        applyVersion={snapshot => setPage(current => current ? { ...current, title: snapshot.title, description: snapshot.description, content: snapshot.content as Page["content"] } : current)} /></details>}
      <PageEditorFields locked={busy || !!unresolved}><section className="pp-editor-card"><h3>Название и описание</h3><div className="pp-page-meta">{isHome ? "Главная страница" : slug}<PageTimestamps page={page} /></div><label>Title<input aria-label="Title страницы" maxLength={2000} value={page.title} onChange={e => setPage({ ...page, title: e.target.value })} /></label><label>Description<textarea aria-label="Description страницы" rows={3} maxLength={10000} value={page.description} onChange={e => setPage({ ...page, description: e.target.value })} /></label></section>
        <div className="pp-editor-modebar"><strong>Контент · {validContent ? page.content.blocks.length : 0} блоков</strong><div><button type="button" aria-pressed={documentMode} onClick={() => setDocumentMode(true)}>Документ</button><button type="button" aria-pressed={!documentMode} onClick={() => setDocumentMode(false)}>Поля блоков</button></div></div>
        <div className={documentMode ? "pp-document-sheet" : ""}>
        {validContent ? page.content.blocks.map((block, index) => <section className={`pp-editor-card pp-content-block ${block.type==="shortcode"?"pp-shortcode-block":""}`} data-block-type={block.type} id={`page-editor-block-${index}`} key={block.id || index}><header><h3>{blockNames[block.type] || block.type}</h3><div>{documentMode ? <button type="button" className="pp-icon" aria-label={`Настройки блока ${index + 1}`} aria-expanded={settingsBlock === index} onClick={() => setSettingsBlock(settingsBlock === index ? null : index)}>Настройки</button> : null}<button type="button" className="pp-icon" aria-label={`Блок ${index + 1} вверх`} disabled={index === 0} onClick={() => { const next = [...page.content.blocks]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; blocks(next); }}><ArrowUp size={16} /></button><button type="button" className="pp-icon" aria-label={`Блок ${index + 1} вниз`} disabled={index === page.content.blocks.length - 1} onClick={() => { const next = [...page.content.blocks]; [next[index + 1], next[index]] = [next[index], next[index + 1]]; blocks(next); }}><ArrowDown size={16} /></button><button type="button" className="pp-icon" aria-label={`Удалить блок ${index + 1}`} onClick={() => { if (window.confirm("Удалить этот блок из черновика?")) blocks(page.content.blocks.filter((_, i) => i !== index)); }}><Trash2 size={16} /></button></div></header>{documentMode && settingsBlock !== index ? <DocumentBlock block={block} onChange={data => blocks(page.content.blocks.map((b, i) => i === index ? { ...b, data } : b))} /> : <Fields value={block.data} label={blockNames[block.type] || block.type} name={block.type} onChange={data => blocks(page.content.blocks.map((b, i) => i === index ? { ...b, data } : b))} />}</section>) : <p role="alert">Webdev вернул неподдерживаемый формат контента. Сохранение отключено, исходная страница сохранена без изменений.</p>}
        </div>
        {validContent && <section className="pp-editor-card pp-add-block"><TemplateCombobox label="Тип нового блока" value={newType} options={Object.keys(defaults).map(type => ({ value: type, label: blockNames[type] }))} onChange={setNewType} /><button type="button" className="button secondary" onClick={() => blocks([...page.content.blocks, { id: crypto.randomUUID(), type: newType, data: structuredClone(defaults[newType]) }])}><Plus size={16} />Добавить блок</button></section>}
      </PageEditorFields></div></div></>}
    </main>
  </div>;
}
