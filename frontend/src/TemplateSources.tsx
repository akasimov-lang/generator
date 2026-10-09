import React from "react";
import { Copy, Download, Plus, Globe2 } from "lucide-react";
type Api = <T>(path: string, init?: RequestInit) => Promise<T>;
export type SourceDraftReference = { id: string; revision: number; hasHtml: boolean };
type Source = { id: string; url: string; html: string; revision: number; capture: { status?: string; source?: string; error?: string } };
const blank = (): Source => ({ id: "", url: "", html: "", revision: 0, capture: {} });

export function TemplateSources({ templateId, api, pending, onChanged, onBusy, onDraftSources }: { templateId?: string; api: Api; pending: boolean; onChanged: () => void; onBusy: (busy: boolean) => void; onDraftSources?: (sources: SourceDraftReference[]) => void }) {
  const endpoint = templateId ? `/site-templates/${templateId}/sources` : "/site-templates/source-drafts";
  const references = React.useRef(new Map<string, SourceDraftReference>());
  const reportSaved = React.useCallback((key: string, row: Source) => {
    references.current.set(key, { id: row.id, revision: row.revision, hasHtml: !!row.html.trim() });
    onDraftSources?.(Array.from(references.current.values()));
  }, [onDraftSources]);
  const [rows, setRows] = React.useState<Array<Source & { key: string }>>([]);
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
          setRows(next.length ? next.map(row => ({ ...row, key: row.id })) : [{ ...blank(), key: "first" }]);
          references.current = new Map(next.map(row => [row.id, { id: row.id, revision: row.revision, hasHtml: !!row.html.trim() }]));
          onDraftSources?.(Array.from(references.current.values()));
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
  return <section className="tg-card tg-source-editor"><div className="tg-source-title"><h3>HTML конкурентов</h3>
    <button type="button" className="button secondary" disabled={pending || loading || rows.length >= 30} onClick={() => setRows(current => [...current, { ...blank(), key: crypto.randomUUID() }])}><Plus size={16} />Добавить конкурента</button></div>
    <p>Ручная вставка HTML с автосохранением: один конкурент — одно поле. В Rich Results Test откройте «Просмотреть проверенную страницу → HTML», скопируйте код и вставьте ниже. Изменения сохраняются автоматически.</p>
    {!templateId && <p className="tg-note">Черновики автоматически сохраняются на сервере под вашим пользователем, даже до создания шаблона. После создания они появятся в задаче. Для вставленного HTML поиск Google включать не требуется.</p>}
    <p className="tg-help">Серверный агент собирает HTML через Google. При запросе входа или CAPTCHA используйте расширение в своём Chrome или вставьте код вручную. Обычный HTML браузера не подменяет результат Google.</p>
    <div className="tg-downloads"><a className="button secondary" href="/extensions/pagepilot-chrome.zip" download><Download size={16} />Скачать расширение Chrome</a><a href="/extensions/install.html" target="_blank" rel="noopener noreferrer">Установка на macOS и Windows</a></div>
    {pending && <p className="tg-help">Сейчас выполняется задача. Поля станут доступны для изменений после завершения этапа.</p>}
    {error && <p role="alert">{error}<button type="button" className="button secondary" onClick={() => setReload(value => value + 1)}>Повторить загрузку</button></p>}{loading && <p>Загрузка источников…</p>}
    {rows.map((row, index) => <SourceEditor key={row.key} initial={row} number={index + 1} templateId={templateId} api={api} endpoint={endpoint} disabled={pending} onChanged={onChanged} rowKey={row.key} onDirty={trackDirty} onSaved={reportSaved} />)}
  </section>;
}

function SourceEditor({ initial, number, templateId, api, endpoint, disabled, onChanged, rowKey, onDirty, onSaved }: { endpoint: string; onSaved: (key: string, row: Source) => void; rowKey: string; onDirty: (key: string, value: boolean) => void; initial: Source; number: number; templateId?: string; api: Api; disabled: boolean; onChanged: () => void }) {
  const [draft, setDraft] = React.useState({ html: initial.html, url: initial.url });
  const [saved, setSaved] = React.useState(initial);
  const [status, setStatus] = React.useState(initial.id ? "Сохранено" : "Вставьте HTML — сохранение автоматическое");
  const [error, setError] = React.useState("");
  const latest = React.useRef(draft);
  const persisted = React.useRef(initial);
  const dirty = React.useRef(false);
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
        dirty.current = snapshot.html !== latest.current.html || snapshot.url !== latest.current.url;
        if (mounted.current) { onSaved(rowKey, row); onDirty(rowKey, dirty.current); setSaved(row); setStatus(dirty.current ? "Ожидает сохранения…" : "Сохранено"); onChanged(); }
        return row;
      } catch (e) { if (mounted.current) { setError(e instanceof Error ? e.message : "Ошибка сохранения"); setStatus("Не сохранено"); } throw e; }
    });
    return queue.current;
  }, [api, endpoint, onChanged, onDirty, rowKey, onSaved]);
  React.useEffect(() => {
    if (!dirty.current && initial.revision >= persisted.current.revision && (initial.html !== persisted.current.html || initial.url !== persisted.current.url)) {
      persisted.current = initial; latest.current = { html: initial.html, url: initial.url };
      setDraft(latest.current); setSaved(initial); setStatus("Сохранено");
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
  function download() {
    const url = URL.createObjectURL(new Blob([draft.html], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = `competitor-${number}-google-html.txt`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function extension() {
    if (!templateId) return;
    dirty.current = true;
    const row = await flush();
    if (row) { window.postMessage({ type: "PAGEPILOT_COLLECT_GOOGLE_HTML", templateId, sourceId: row.id, revision: row.revision, url: latest.current.url }, location.origin); setStatus("Запрос передан расширению. Если Google не открылся, установите расширение по ссылке выше."); }
  }
  return <div className="tg-source-field"><div className="tg-heading"><h4>HTML конкурента {number}</h4><small role="status">{status}</small></div>
    <label>Адрес конкурента <span className="tg-muted">(для запуска проверки)</span><input aria-label={`Адрес конкурента ${number}`} value={draft.url} disabled={disabled} placeholder="https://example.com" onChange={e => change({ ...draft, url: e.target.value })} onBlur={() => { if (dirty.current) void flush().catch(() => undefined); }} /></label>
    <textarea aria-label={`HTML конкурента ${number}`} rows={9} disabled={disabled} spellCheck={false} value={draft.html}
      placeholder="Вставьте полный HTML из проверенной Google страницы…" onChange={e => change({ ...draft, html: e.target.value })} onBlur={() => { if (dirty.current) void flush().catch(() => undefined); }} />
    <div className="tg-downloads">{templateId && <button type="button" className="button secondary" disabled={disabled || !draft.url.trim()} onClick={() => void extension().catch(() => undefined)}><Globe2 size={16} />Получить через Chrome</button>}
      <a href={`https://search.google.com/test/rich-results?hl=ru${draft.url ? `&url=${encodeURIComponent(draft.url)}` : ""}`} target="_blank" rel="noopener noreferrer">Открыть Rich Results Test</a>
      <button type="button" className="button secondary" disabled={!draft.html} onClick={download}><Download size={16} />TXT</button>
      <button type="button" className="button secondary" disabled={!draft.html} onClick={() => void navigator.clipboard.writeText(draft.html).then(() => setStatus("Скопировано")).catch(() => setError("Выделите HTML и скопируйте вручную."))}><Copy size={16} />Скопировать</button></div>
    {error && <p role="alert" className="tg-alert">{error}<button type="button" onClick={() => void flush().catch(() => undefined)}>Повторить сохранение</button></p>}
    {saved.capture.error && <p className="tg-help">{saved.capture.error}</p>}
    {saved.capture.status === "google_ready" && <p className="tg-help">HTML сохранён и доступен для анализа. Источник: {saved.capture.source === "google_rich_results" ? "агент Google Rich Results" : "вставка HTML из Google"}.</p>}
  </div>;
}
