import { PageContentTools } from "./PageContentTools";
import React from "react";
import { createPortal } from "react-dom";
import { ArrowDown, ArrowUp, Check, ChevronRight, Copy, FileText, Home, Plus, RefreshCcw, Save, Search, Trash2, X } from "lucide-react";
import { TemplateCombobox } from "./TemplateCombobox";
import "./styles/project-pages.css";

type Api = <T>(path: string, init?: RequestInit) => Promise<T>;
type Value = string | number | boolean | null | Value[] | { [key: string]: Value };
type Block = { id?: string; type: string; data: Value; [key: string]: unknown };
type PageRow = { key: string; title: string; slug: string; is_home: boolean; updated_at?: string };
type Page = PageRow & { description: string; content: { blocks: Block[]; [key: string]: unknown }; revision: string };
type Result = { id: string; status: string; error?: string; page?: Page };
const errorText = (e: unknown) => e instanceof Error ? e.message : "Не удалось выполнить запрос";
const blockNames: Record<string, string> = { paragraph: "Абзац", header: "Заголовок", list: "Список", table: "Таблица", faq: "Вопросы и ответы", image: "Изображение", button: "Кнопка", shortcode: "Шорткод", raw: "HTML", quote: "Цитата", delimiter: "Разделитель" };
const fieldNames: Record<string, string> = { text: "Текст", level: "Уровень заголовка", items: "Пункты", content: "Содержимое", question: "Вопрос", answer: "Ответ", caption: "Подпись", url: "Адрес", file: "Файл", button: "Текст кнопки", shortcode: "Шорткод", html: "HTML-код", style: "Вид списка", withBorder: "Рамка", withBackground: "Фон", stretched: "На всю ширину", withHeadings: "Строка заголовков", alignment: "Выравнивание", checked: "Отмечено", title: "Заголовок", link: "Ссылка", meta: "Настройки" };
const defaults: Record<string, Value> = { paragraph: { text: "" }, header: { text: "", level: 2 }, list: { style: "unordered", items: [""] }, table: { withHeadings: true, content: [["", ""], ["", ""]] }, faq: [{ question: "", answer: "" }], image: { file: { url: "" }, caption: "", withBorder: false, withBackground: false, stretched: false }, button: { button: "" }, shortcode: { shortcode: "" }, raw: { html: "" }, quote: { text: "", caption: "" } };

export function ProjectPages({ siteId, api }: { siteId: string; api: Api }) {
  const [rows, setRows] = React.useState<PageRow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [query, setQuery] = React.useState("");
  const [selected, setSelected] = React.useState<PageRow | null>(null);
  const load = React.useCallback(async () => {
    setLoading(true); setError("");
    try { const result = await api<{ pages: PageRow[] }>(`/sites/${siteId}/pages`); setRows(result.pages); }
    catch (e) { setError(errorText(e)); }
    finally { setLoading(false); }
  }, [siteId, api]);
  React.useEffect(() => { void load(); }, [load]);
  const filtered = rows.filter(row => `${row.title} ${row.slug} ${row.is_home ? "главная" : ""}`.toLowerCase().includes(query.toLowerCase()));
  return <section className="pp-pages"><header><div><h2>Все страницы <small>{rows.length || ""}</small></h2><p>Страницы из Webdev. Нажмите на заголовок, чтобы открыть редактор.</p></div><button className="button secondary" disabled={loading} onClick={() => void load()}><RefreshCcw size={16} />Обновить список</button></header>
    <label className="pp-page-search"><Search size={18} /><input aria-label="Поиск страниц" placeholder="Заголовок или адрес страницы" value={query} onChange={e => setQuery(e.target.value)} /></label>
    {error && <p className="pp-page-error" role="alert">{error}</p>}
    {loading ? <p role="status">Загружаем страницы из Webdev…</p> : !error && <div className="pp-page-list">{filtered.map(row => <button key={row.key} className="pp-page-row" onClick={() => setSelected(row)}>{row.is_home ? <Home size={21} /> : <FileText size={21} />}<span><strong>{row.title}</strong><small>{row.is_home && <b>Главная</b>}{row.slug}</small></span><ChevronRight size={18} /></button>)}{!filtered.length && <p>{rows.length ? "Страницы не найдены. Измените запрос." : "В Webdev пока нет страниц этого проекта."}</p>}</div>}
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
  if (!rich) return <label>{label}<textarea aria-label={label} rows={value.length > 150 || value.includes("\n") ? 4 : 2} value={value} onChange={e => onChange(e.target.value)} /></label>;
  return <div className="pp-text-field"><div className="pp-text-toolbar"><span>{label}</span><button type="button" onClick={() => setSource(!source)}>{source ? "Визуальный режим" : "HTML текста"}</button>{!source && <><button type="button" aria-label={`Жирный: ${label}`} onMouseDown={e => { e.preventDefault(); editor.current?.focus(); document.execCommand("bold"); if (editor.current) onChange(editor.current.innerHTML); }}><b>B</b></button><button type="button" aria-label={`Курсив: ${label}`} onMouseDown={e => { e.preventDefault(); editor.current?.focus(); document.execCommand("italic"); if (editor.current) onChange(editor.current.innerHTML); }}><i>I</i></button></>}</div>
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

function PageEditor({ siteId, row, api, onClose, onSaved }: { siteId: string; row: PageRow; api: Api; onClose: () => void; onSaved: (page: Page) => void }) {
  const [page, setPage] = React.useState<Page | null>(null);
  const [original, setOriginal] = React.useState("");
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const [operation, setOperation] = React.useState<Result | null>(null);
  const [message, setMessage] = React.useState("");
  const [newType, setNewType] = React.useState("paragraph");
  const dialog = React.useRef<HTMLDivElement>(null);
  const dirty = !!page && JSON.stringify(page) !== original;
  const path = `/sites/${siteId}/pages/${row.key}`;
  const unresolved = operation && ["pending", "unknown"].includes(operation.status);
  const load = React.useCallback(async () => {
    setLoading(true); setError(""); setMessage("");
    try { const next = await api<Page>(path); setPage(next); setOriginal(JSON.stringify(next)); setOperation(null); }
    catch (e) { setError(errorText(e)); }
    finally { setLoading(false); }
  }, [api, path]);
  React.useEffect(() => { void load(); }, [load]);
  const close = React.useCallback(() => { if (!busy && (!dirty || window.confirm("Есть несохранённые изменения. Закрыть редактор без сохранения?"))) onClose(); }, [busy, dirty, onClose]);
  React.useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const overflow = document.body.style.overflow; document.body.style.overflow = "hidden"; dialog.current?.focus();
    return () => { document.body.style.overflow = overflow; previous?.focus(); };
  }, []);
  React.useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty || busy) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, busy]);
  function handleKeys(event: React.KeyboardEvent) {
    if (event.key === "Escape" && !(event.target as HTMLElement).closest('.tg-combobox')) { event.stopPropagation(); close(); }
    if (event.key === "Tab") {
      const items = Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), [contenteditable="true"], [tabindex="0"]') || []).filter(el => el.offsetParent !== null && !el.closest('fieldset:disabled'));
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  }
  async function receive(result: Result) {
    setOperation(result);
    if (result.status === "confirmed") {
      const next = result.page || await api<Page>(path); setPage(next); setOriginal(JSON.stringify(next)); onSaved(next); setMessage("Изменения сохранены в Webdev и подтверждены."); setError("");
    } else setError(result.error || "Сохранение ещё не подтверждено. Проверьте результат.");
  }
  async function save() {
    if (!page) return;
    setBusy(true); setError(""); setMessage("");
    const id = crypto.randomUUID();
    try { await receive(await api<Result>(path, { method: "PUT", body: JSON.stringify({ request_id: id, revision: page.revision, title: page.title, description: page.description, content: page.content }) })); }
    catch (e) {
      setError(errorText(e));
      const status = (e as { statusCode?: number })?.statusCode;
      setOperation(status && status < 500 ? null : { id, status: "unknown" });
    }
    finally { setBusy(false); }
  }
  async function check() {
    if (!operation) return;
    setBusy(true); setError("");
    try { await receive(await api<Result>(`${path}/edits/${operation.id}`)); }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }
  function blocks(next: Block[]) { if (page) setPage({ ...page, content: { ...page.content, blocks: next } }); }
  const validContent = page?.content && Array.isArray(page.content.blocks);
  return createPortal(<div className="pp-page-editor" ref={dialog} tabIndex={-1} role="dialog" aria-modal="true" aria-label={`Редактор страницы: ${row.title}`} onKeyDown={handleKeys}>
    <header className="pp-editor-header"><div><span>{row.is_home ? "Главная страница" : "Редактор страницы"}</span><h2>{page?.title || row.title}</h2><small>{row.slug}</small></div><div className="pp-editor-actions"><button type="button" className="button secondary" disabled={busy} onClick={() => { if (!dirty || window.confirm("Загрузить актуальную страницу из Webdev? Несохранённые изменения будут потеряны.")) void load(); }}><RefreshCcw size={16} />Загрузить заново</button><button type="button" className="button primary" disabled={!dirty || busy || loading || !!unresolved || !validContent} onClick={() => void save()}><Save size={16} />{busy ? "Проверяем…" : "Сохранить на сайте"}</button><button className="pp-icon" type="button" aria-label="Закрыть редактор" disabled={busy} onClick={close}><X size={24} /></button></div></header>
    <main className="pp-editor-main">{loading && <p role="status">Загрузка страницы…</p>}{error && <div className="pp-page-error" role="alert">{error}{unresolved && <button className="button secondary" disabled={busy} onClick={() => void check()}>Проверить сохранение</button>}</div>}{message && <p role="status" className="pp-page-success"><Check size={18} />{message}</p>}
      {!loading && page && <><div className="pp-editor-info"><span>{dirty ? "Есть несохранённые изменения" : "Загружена сохранённая версия"} · Изменения публикуются кнопкой «Сохранить на сайте».</span><button type="button" className="button secondary compact" onClick={() => void navigator.clipboard.writeText(JSON.stringify({ title: page.title, description: page.description, content: page.content }, null, 2)).then(() => setMessage("Черновик скопирован")).catch(() => setError("Браузер не разрешил копирование."))}><Copy size={14} />Скопировать черновик</button></div>
      {validContent && <PageContentTools api={api} path={path} isHome={row.is_home} content={page.content} revision={page.revision} disabled={busy || !!unresolved}
        applyContent={content => setPage(current => current ? { ...current, content: content as Page["content"] } : current)}
        applyVersion={snapshot => setPage(current => current ? { ...current, title: snapshot.title, description: snapshot.description, content: snapshot.content as Page["content"] } : current)} />}
      <fieldset disabled={busy || !!unresolved} className="pp-editor-fields"><section className="pp-editor-card"><h3>Название и описание</h3><label>Title<input aria-label="Title страницы" maxLength={2000} value={page.title} onChange={e => setPage({ ...page, title: e.target.value })} /></label><label>Description<textarea aria-label="Description страницы" rows={3} maxLength={10000} value={page.description} onChange={e => setPage({ ...page, description: e.target.value })} /></label></section>
        {validContent ? page.content.blocks.map((block, index) => <section className="pp-editor-card pp-content-block" key={block.id || index}><header><h3>{blockNames[block.type] || block.type}</h3><div><button type="button" className="pp-icon" aria-label={`Блок ${index + 1} вверх`} disabled={index === 0} onClick={() => { const next = [...page.content.blocks]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; blocks(next); }}><ArrowUp size={16} /></button><button type="button" className="pp-icon" aria-label={`Блок ${index + 1} вниз`} disabled={index === page.content.blocks.length - 1} onClick={() => { const next = [...page.content.blocks]; [next[index + 1], next[index]] = [next[index], next[index + 1]]; blocks(next); }}><ArrowDown size={16} /></button><button type="button" className="pp-icon" aria-label={`Удалить блок ${index + 1}`} onClick={() => { if (window.confirm("Удалить этот блок из черновика?")) blocks(page.content.blocks.filter((_, i) => i !== index)); }}><Trash2 size={16} /></button></div></header><Fields value={block.data} label={blockNames[block.type] || block.type} name={block.type} onChange={data => blocks(page.content.blocks.map((b, i) => i === index ? { ...b, data } : b))} /></section>) : <p role="alert">Webdev вернул неподдерживаемый формат контента. Сохранение отключено, исходная страница сохранена без изменений.</p>}
        {validContent && <section className="pp-editor-card pp-add-block"><TemplateCombobox label="Тип нового блока" value={newType} options={Object.keys(defaults).map(type => ({ value: type, label: blockNames[type] }))} onChange={setNewType} /><button type="button" className="button secondary" onClick={() => blocks([...page.content.blocks, { id: crypto.randomUUID(), type: newType, data: structuredClone(defaults[newType]) }])}><Plus size={16} />Добавить блок</button></section>}
      </fieldset></>}
    </main>
  </div>, document.body);
}
