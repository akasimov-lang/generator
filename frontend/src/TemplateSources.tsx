import React from "react";
import { Copy, Download, Plus, Globe2, Upload, Trash2, ExternalLink, ChevronDown } from "lucide-react";
type Api = <T>(path: string, init?: RequestInit) => Promise<T>;
export type SourceDraftReference = { id: string; revision: number; hasHtml: boolean; suggestedBrand?: string };
type Source = { title?: string; display_url?: string; created_at?: string; updated_at?: string; id: string; url: string; html: string; revision: number; suggested_brand?: string; capture: { status?: string; source?: string; error?: string } };
const blank = (): Source => ({ id: "", url: "", html: "", revision: 0, capture: {} });

export function TemplateSources({ templateId, api, pending, onChanged, onBusy, onDraftSources }: { templateId?: string; api: Api; pending: boolean; onChanged: () => void; onBusy: (busy: boolean) => void; onDraftSources?: (sources: SourceDraftReference[]) => void }) {
  const endpoint = templateId ? `/site-templates/${templateId}/sources` : "/site-templates/source-drafts";
  const rowKeys = React.useRef<string[]>([]);
  const references = React.useRef(new Map<string, SourceDraftReference>());
  const reportSaved = React.useCallback((key: string, row: Source) => {
    references.current.set(key, { id: row.id, revision: row.revision, hasHtml: !!row.html.trim(), suggestedBrand: row.suggested_brand });
    onDraftSources?.(rowKeys.current.flatMap(key => { const ref = references.current.get(key); return ref ? [ref] : []; }));
  }, [onDraftSources]);
  const [rows, setRows] = React.useState<Array<Source & { key: string }>>([]);
  rowKeys.current = rows.map(row => row.key);
  const dirtyKeys = React.useRef(new Set<string>());
  const trackDirty = React.useCallback((key: string, value: boolean) => { if (value) dirtyKeys.current.add(key); else dirtyKeys.current.delete(key); onBusy(dirtyKeys.current.size > 0); }, [onBusy]);
  const [reload, setReload] = React.useState(0);
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  React.useEffect(() => {
    let live = true;
    onBusy(true); setError("");
    const load = async () => {
      try {
        const next = await api<Source[]>(endpoint);
        if (live) {
          rowKeys.current = next.map(row => row.id);
          setRows(next.length ? next.map(row => ({ ...row, key: row.id })) : [{ ...blank(), key: "first" }]);
          references.current = new Map(next.map(row => [row.id, { id: row.id, revision: row.revision, hasHtml: !!row.html.trim(), suggestedBrand: row.suggested_brand }]));
          onDraftSources?.(rowKeys.current.flatMap(key => { const ref = references.current.get(key); return ref ? [ref] : []; }));
          setLoading(false); onBusy(dirtyKeys.current.size > 0);
        }
      } catch (e) { if (live) { setError(String(e)); setLoading(false); } }
    };
    void load();
    const timer = pending ? setInterval(() => void load(), 5000) : undefined;
    const extensionSaved = (event: MessageEvent) => {
      if (event.source !== window || event.origin !== location.origin || event.data?.templateId !== templateId) return;
      if (event.data.type === "PAGEPILOT_SOURCE_SAVED") { onChanged(); void load(); }
      if (event.data.type === "PAGEPILOT_EXTENSION_ERROR") setError(String(event.data.error));
    };
    window.addEventListener("message", extensionSaved);
    return () => { live = false; clearInterval(timer); window.removeEventListener("message", extensionSaved); };
  }, [api, endpoint, templateId, pending, onChanged, onBusy, onDraftSources, reload]);
  return <section className="tg-card tg-source-editor"><div className="tg-source-title"><h3>Главные страницы конкурентов <small>{rows.length} / 10</small></h3></div>
    <p>Добавьте до десяти главных страниц: загрузите файл HTML, TXT, DOC или DOCX или вставьте код. Каждый конкурент сохраняется отдельно и автоматически.</p>
    {pending && <p className="tg-help">Сейчас выполняется задача. Поля станут доступны для изменений после завершения этапа.</p>}
    {error && <p role="alert">{error}<button type="button" className="button secondary" onClick={() => setReload(value => value + 1)}>Повторить загрузку</button></p>}{loading && <p>Загрузка источников…</p>}
    {rows.map((row, index) => <SourceEditor key={row.key} initial={row} number={index + 1} templateId={templateId} api={api} endpoint={endpoint} disabled={pending || loading} onChanged={onChanged} rowKey={row.key} onDirty={trackDirty} onSaved={reportSaved} onRemoved={() => {
      references.current.delete(row.key); dirtyKeys.current.delete(row.key);
      onDraftSources?.(rowKeys.current.flatMap(key => { const ref = references.current.get(key); return ref ? [ref] : []; })); onBusy(dirtyKeys.current.size > 0);
      setRows(current => current.filter(item => item.key !== row.key)); onChanged();
    }} />)}
    <div className="tg-source-footer"><button type="button" className="button secondary" disabled={pending || loading || rows.length >= 10} onClick={() => setRows(current => current.length >= 10 ? current : [...current, { ...blank(), key: crypto.randomUUID() }])}><Plus size={16} />Добавить конкурента</button></div>
  </section>;
}

function SourceEditor({ initial, number, templateId, api, endpoint, disabled, onChanged, rowKey, onDirty, onSaved, onRemoved }: { onRemoved: () => void; endpoint: string; onSaved: (key: string, row: Source) => void; rowKey: string; onDirty: (key: string, value: boolean) => void; initial: Source; number: number; templateId?: string; api: Api; disabled: boolean; onChanged: () => void }) {
  const [expanded, setExpanded] = React.useState(!initial.id || !initial.html.trim() || !!initial.capture.error);
  const [draft, setDraft] = React.useState({ html: initial.html, url: initial.url });
  const [saved, setSaved] = React.useState(initial);
  const [status, setStatus] = React.useState(initial.id ? "Сохранено" : "Вставьте HTML — сохранение автоматическое");
  const [error, setError] = React.useState("");
  const [reading, setReading] = React.useState(false);
  const [removing, setRemoving] = React.useState(false);
  const [filename, setFilename] = React.useState("");
  const fileInput = React.useRef<HTMLInputElement>(null);
  const latest = React.useRef(draft);
  const persisted = React.useRef(initial);
  const dirty = React.useRef(false);
  const deleting = React.useRef(false);
  const timer = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const queue = React.useRef<Promise<Source | undefined>>(Promise.resolve(undefined));
  const mounted = React.useRef(true);
  const flush = React.useCallback(() => {
    clearTimeout(timer.current);
    queue.current = queue.current.catch(() => undefined).then(async () => {
      if (!dirty.current) return persisted.current;
      const snapshot = { ...latest.current };
      if (mounted.current) { setStatus("Сохраняется…"); setError(""); }
      const current = persisted.current;
      try {
        const row = await api<Source>(`${endpoint}${current.id ? "/" + current.id : ""}`, {
          method: current.id ? "PUT" : "POST", body: JSON.stringify({ ...snapshot, revision: current.revision }) });
        persisted.current = row;
        if (mounted.current && !current.html.trim() && row.html.trim() && !row.capture.error && snapshot.html === latest.current.html && snapshot.url === latest.current.url) setExpanded(false);
        dirty.current = snapshot.html !== latest.current.html || snapshot.url !== latest.current.url;
        if (mounted.current) { onSaved(rowKey, row); onDirty(rowKey, dirty.current || deleting.current); setSaved(row); setStatus(dirty.current ? "Ожидает сохранения…" : "Сохранено"); onChanged(); }
        return row;
      } catch (e) { if (mounted.current) { setError(e instanceof Error ? e.message : "Ошибка сохранения"); setStatus("Не сохранено"); } throw e; }
    });
    return queue.current;
  }, [api, endpoint, onChanged, onDirty, rowKey, onSaved]);
  React.useEffect(() => {
    if (!dirty.current && initial.revision >= persisted.current.revision && (initial.html !== persisted.current.html || initial.url !== persisted.current.url)) {
      persisted.current = initial; latest.current = { html: initial.html, url: initial.url };
      setDraft(latest.current); setSaved(initial); setStatus("Сохранено");
      if (!initial.capture.error && initial.html.trim()) setExpanded(false);
    }
  }, [initial]);
  React.useEffect(() => {
    mounted.current = true;
    const warn = (event: BeforeUnloadEvent) => { if (dirty.current) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => { mounted.current = false; clearTimeout(timer.current); if (dirty.current) void flush().catch(() => undefined); window.removeEventListener("beforeunload", warn); };
  }, [flush]);
  function change(next: typeof draft) {
    onChanged(); onDirty(rowKey, true); setDraft(next); latest.current = next; dirty.current = true; setStatus("Ожидает сохранения…");
    clearTimeout(timer.current); timer.current = setTimeout(() => void flush().catch(() => undefined), 500);
  }
  async function upload(file?: File) {
    if (!file) return;
    setError("");
    if (!/\.(html?|txt|docx?)$/i.test(file.name)) { setError("Выберите файл HTML, HTM, TXT, DOC или DOCX."); return; }
    if (file.size > 2_000_000) { setError("HTML превышает 2 МБ. Выберите файл меньшего размера."); return; }
    setReading(true); onDirty(rowKey, true);
    try {
      const extension = file.name.split(".").pop()?.toLowerCase();
      const html = extension === "doc" || extension === "docx"
        ? (await api<{ html: string }>(`/site-templates/source-document?extension=${extension}`, {
            method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file,
          })).html
        : await file.text();
      if (!html.trim()) throw new Error("Файл пуст. Выберите HTML главной страницы.");
      if (new TextEncoder().encode(html).length > 2_000_000) throw new Error("HTML превышает 2 МБ.");
      change({ ...latest.current, html }); setFilename(file.name);
    } catch (e) { setError(e instanceof Error ? e.message : "Не удалось прочитать файл"); onDirty(rowKey, dirty.current); }
    finally { setReading(false); if (fileInput.current) fileInput.current.value = ""; }
  }
  async function remove() {
    deleting.current = true; setRemoving(true); setError(""); onDirty(rowKey, true);
    try {
      clearTimeout(timer.current);
      const row = await flush();
      if (row?.id) await api(`${endpoint}/${row.id}?revision=${row.revision}`, { method: "DELETE" });
      dirty.current = false; onRemoved();
    } catch (e) { setError(e instanceof Error ? e.message : "Не удалось удалить конкурента"); deleting.current = false; onDirty(rowKey, dirty.current); setRemoving(false); }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([draft.html], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = `competitor-${number}-google-html.txt`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function extension() {
    if (!templateId) return;
    dirty.current = true;
    const row = await flush();
    if (row) { window.postMessage({ type: "PAGEPILOT_COLLECT_GOOGLE_HTML", templateId, sourceId: row.id, revision: row.revision, url: latest.current.url }, location.origin); setStatus("Запрос передан расширению. Если Google не открылся, установите расширение Chrome для PagePilot."); }
  }
  const identity = React.useMemo(() => {
    const doc = new DOMParser().parseFromString(saved.html, "text/html");
    return { title: saved.title || doc.querySelector("title")?.textContent?.trim() || "Без тайтла", url: saved.display_url || saved.url || doc.querySelector('link[rel="canonical"]')?.getAttribute("href") || doc.querySelector('meta[property="og:url"]')?.getAttribute("content") || "Адрес не определён" };
  }, [saved]);
  const added = saved.created_at ? new Date(/Z$|[+-]\d\d:\d\d$/.test(saved.created_at) ? saved.created_at : saved.created_at + "Z") : null;
  return <div className="tg-source-field">
    {saved.id && saved.html.trim() && <button type="button" className="tg-source-summary" aria-expanded={expanded} aria-label={`Конкурент ${number}: ${identity.url}`} onClick={() => setExpanded(value => !value)}><span><strong>{identity.url}</strong><small>{identity.title}</small></span><time>{added && !Number.isNaN(added.getTime()) ? added.toLocaleString("ru-RU") : "Дата не указана"}</time><ChevronDown size={17} /></button>}
    <div hidden={!expanded && !error}><div className="tg-heading"><h4>HTML конкурента {number}</h4><small role="status">{reading ? "Читаем файл…" : status}</small><button type="button" className="button secondary" aria-label={`Удалить конкурента ${number}`} disabled={disabled || reading || removing} onClick={() => void remove()}><Trash2 size={16} /></button></div>
    <div className="tg-upload"><input ref={fileInput} type="file" accept=".html,.htm,.txt,.doc,.docx,text/html,text/plain,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document" aria-label={`Загрузить HTML конкурента ${number}`} disabled={disabled || reading || removing} onChange={e => void upload(e.target.files?.[0])} />
      <button type="button" className="button secondary" disabled={disabled || reading || removing} onClick={() => fileInput.current?.click()}><Upload size={17} />Загрузить файл</button><small>{filename || "HTML, HTM, TXT, DOC, DOCX · до 2 МБ"}</small></div>
    <a className="tg-google-test" href={`https://search.google.com/test/rich-results?hl=ru${draft.url.trim() ? `&url=${encodeURIComponent(draft.url.trim())}` : ""}`} target="_blank" rel="noopener noreferrer" aria-label={`Проверить в Google — конкурент ${number} (новая вкладка)`}>
      <span className="tg-google-logo"><img src="/service-logos/google.png" alt="Google" width="92" height="30" /></span>
      <span><strong>Проверить в Google</strong><small>Расширенные результаты</small></span><ExternalLink size={18} aria-hidden="true" />
    </a>
    <details className="tg-source-extra"><summary>Адрес и получение HTML через Google</summary><label>Адрес конкурента <span className="tg-muted">(для запуска проверки)</span><input aria-label={`Адрес конкурента ${number}`} value={draft.url} disabled={disabled || reading || removing} placeholder="https://example.com" onChange={e => change({ ...draft, url: e.target.value })} onBlur={() => { if (dirty.current) void flush().catch(() => undefined); }} /></label>
    </details>
    <textarea aria-label={`HTML конкурента ${number}`} rows={9} disabled={disabled || reading || removing} spellCheck={false} value={draft.html}
      placeholder="Или вставьте сюда HTML главной страницы конкурента…" onChange={e => change({ ...draft, html: e.target.value })} onBlur={() => { if (dirty.current) void flush().catch(() => undefined); }} />
    <details className="tg-source-extra"><summary>Действия с HTML</summary><div className="tg-downloads">{templateId && <button type="button" className="button secondary" disabled={disabled || !draft.url.trim()} onClick={() => void extension().catch(() => undefined)}><Globe2 size={16} />Получить через Chrome</button>}
      <button type="button" className="button secondary" disabled={!draft.html} onClick={download}><Download size={16} />TXT</button>
      <button type="button" className="button secondary" disabled={!draft.html} onClick={() => void navigator.clipboard.writeText(draft.html).then(() => setStatus("Скопировано")).catch(() => setError("Выделите HTML и скопируйте вручную."))}><Copy size={16} />Скопировать</button></div></details>
    {error && <p role="alert" className="tg-alert">{error}<button type="button" onClick={() => void flush().catch(() => undefined)}>Повторить сохранение</button></p>}
    {saved.capture.error && <p className="tg-help">{saved.capture.error}</p>}
    {saved.capture.status === "google_ready" && <p className="tg-help">HTML сохранён и доступен для анализа. </p>}
  </div></div>;
}
