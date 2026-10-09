import React from "react";
import { History, Link2, Smile, Sparkles, X } from "lucide-react";
import { TemplateCombobox } from "./TemplateCombobox";
type Api = <T>(path: string, init?: RequestInit) => Promise<T>;
type Content = { blocks: Array<{ id?: string; type: string; data: unknown; [key: string]: unknown }>; [key: string]: unknown };
type Draft = { id: string; action: string; status: string; error?: string; input_content?: Content; result_content?: Content; created_at: string };
type Version = { id: string; requested_by: string; created_at: string; title: string };
type Snapshot = { title: string; description: string; content: Content };
const names: Record<string, string> = { paragraphs: "Переписать все абзацы", headings: "Переписать заголовки", emoji: "Добавить тематические эмодзи в таблицы" };
const states: Record<string, string> = { queued: "в очереди", generating: "генерация", ready: "готово", failed: "ошибка" };
const message = (e: unknown) => e instanceof Error ? e.message : "Не удалось выполнить действие";

function plain(value: string) {
  const element = document.createElement("template"); element.innerHTML = value;
  element.content.querySelectorAll("script,style,iframe,svg,object").forEach(node => node.remove());
  return element.content.textContent || "";
}
function strings(value: unknown): string[] {
  if (typeof value === "string") return [plain(value)];
  if (Array.isArray(value)) return value.flatMap(strings);
  if (value && typeof value === "object") return Object.entries(value).filter(([key]) => ["text", "content", "items", "question", "answer", "caption", "button"].includes(key)).flatMap(([, val]) => strings(val));
  return [];
}
function ContentView({ content }: { content: Content }) {
  return <div className="pp-version-content">{content.blocks.map((block, i) => <div key={i} className={block.type === "header" ? "pp-version-heading" : ""}>{strings(block.data).map((text, j) => <p key={j}>{text}</p>)}{["image", "shortcode", "raw"].includes(block.type) && <small>{block.type === "image" ? "Изображение" : block.type === "raw" ? "HTML-блок" : "Шорткод"} · сохраняется в структуре страницы</small>}</div>)}</div>;
}

export function PageContentTools({ api, path, isHome, content, disabled, revision, applyContent, applyVersion }: {
  api: Api; path: string; isHome: boolean; content: Content; disabled: boolean; revision: string;
  applyContent: (content: Content) => void; applyVersion: (snapshot: Snapshot) => void;
}) {
  const currentContent = React.useRef(content); currentContent.current = content;
  const [providers, setProviders] = React.useState<{ id: string; name: string }[]>([]);
  const [provider, setProvider] = React.useState("");
  const [drafts, setDrafts] = React.useState<Draft[]>([]);
  const [versions, setVersions] = React.useState<Version[]>([]);
  const [historyOpen, setHistoryOpen] = React.useState(false);
  const [preview, setPreview] = React.useState<Draft | null>(null);
  const [snapshot, setSnapshot] = React.useState<Snapshot | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const [notice, setNotice] = React.useState("");
  const load = React.useCallback(async () => {
    const [history, jobs] = await Promise.all([api<Version[]>(`${path}/history`), isHome ? api<Draft[]>(`${path}/ai`) : Promise.resolve([])]);
    setVersions(history); setDrafts(jobs);
  }, [api, path, isHome]);
  React.useEffect(() => { void load().catch(e => setError(message(e))); }, [load, revision]);
  React.useEffect(() => {
    if (!isHome) return;
    let live = true;
    void api<Array<{ id: string; name: string; provider_type: string; is_active: boolean }>>("/ai-providers").then(items => {
      if (!live) return;
      const active = items.filter(p => p.is_active && p.provider_type === "gemini"); setProviders(active); setProvider(active[0]?.id || "");
    }).catch(e => { if (live) setError(message(e)); });
    return () => { live = false; };
  }, [api, isHome]);
  const pending = drafts.some(d => ["queued", "generating"].includes(d.status));
  React.useEffect(() => { if (!pending) return; const timer = setInterval(() => void load().catch(e => setError(message(e))), 4000); return () => clearInterval(timer); }, [pending, load]);
  async function perform(fn: () => Promise<void>) { setBusy(true); setError(""); setNotice(""); try { await fn(); } catch (e) { setError(message(e)); } finally { setBusy(false); } }
  return <section className="pp-editor-card pp-content-tools"><h3>Работа с контентом</h3>
    {isHome && <><TemplateCombobox label="Gemini для переработки контента" value={provider} options={providers.map(p => ({ value: p.id, label: p.name }))} onChange={setProvider} />
      <div className="pp-tool-buttons">{Object.entries(names).map(([action, label]) => <button key={action} type="button" className="button secondary" disabled={disabled || busy || pending || !provider} onClick={() => void perform(async () => {
        const draft = await api<Draft>(`${path}/ai`, { method: "POST", body: JSON.stringify({ action, provider_id: provider, content }) }); setDrafts(rows => [draft, ...rows]); setNotice("Задача сохранена. Результат можно проверить перед вставкой в редактор.");
      })}>{action === "emoji" ? <Smile size={16} /> : <Sparkles size={16} />}{label}</button>)}</div><p>Переписывание сохраняет смысл и факты. Результат сначала появится как черновик для проверки.</p></>}
    {!isHome && <button type="button" className="button secondary" disabled={disabled || busy} onClick={() => void perform(async () => { const result = await api<{ content: Content; message: string; changed: boolean }>(`${path}/interlink`, { method: "POST", body: JSON.stringify({ content }) }); if (result.changed) { if (JSON.stringify(currentContent.current) !== JSON.stringify(content)) throw new Error("Контент изменился во время подготовки ссылки. Запустите перелинковку ещё раз."); applyContent(result.content); } setNotice(result.message); })}><Link2 size={16} />Сгенерировать перелинковку</button>}
    <button type="button" className="button secondary" disabled={busy} onClick={() => { setHistoryOpen(!historyOpen); setSnapshot(null); }}><History size={16} />История версий ({versions.length})</button>
    {error && <p className="pp-page-error" role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {!!drafts.length && <details><summary>Черновики переработки ({drafts.length}){pending ? " · выполняется генерация" : ""}</summary>{drafts.map(draft => <div className="pp-draft-row" key={draft.id}><span>{names[draft.action]} · {states[draft.status] || draft.status} · {new Date(draft.created_at).toLocaleString("ru-RU")}</span><button type="button" className="button secondary compact" disabled={busy || pending && draft.status !== "ready" && draft.status !== "failed"} onClick={() => void perform(async () => { const result = await api<Draft>(`${path}/ai/${draft.id}`); if (result.status === "failed") setError(result.error || "Генерация не завершена"); else { setPreview(result); setSnapshot(null); } })}>Просмотреть</button></div>)}</details>}
    {preview?.result_content && <section className="pp-version-preview"><header><h3>Результат: {names[preview.action]}</h3><button type="button" className="pp-icon" aria-label="Закрыть результат" onClick={() => setPreview(null)}><X size={16} /></button></header><div className="pp-version-compare"><div><h4>До</h4>{preview.input_content && <ContentView content={preview.input_content} />}</div><div><h4>После</h4><ContentView content={preview.result_content} /></div></div><button type="button" className="button primary" disabled={disabled || busy} onClick={() => { if (JSON.stringify(content) !== JSON.stringify(preview.input_content) && !window.confirm("После запуска обработки контент изменился. Заменить текущий черновик этим результатом?")) return; applyContent(preview.result_content!); setPreview(null); setNotice("Результат вставлен в редактор. Проверьте его и нажмите «Сохранить на сайте»."); }}>Вставить результат в редактор</button></section>}
    {historyOpen && <section className="pp-version-history"><h4>Сохранённые версии страницы</h4><p>История ведётся с первого сохранения через PagePilot. Перед каждой записью сохраняется исходная версия из Webdev.</p>{!versions.length && <p>Сохранений через PagePilot пока нет.</p>}{versions.map(version => <div className="pp-draft-row" key={version.id}><span>{new Date(version.created_at).toLocaleString("ru-RU")} · {version.requested_by} · {version.title}</span><button type="button" disabled={busy} className="button secondary compact" onClick={() => void perform(async () => { setSnapshot(await api<Snapshot>(`${path}/history/${version.id}?before=true`)); setPreview(null); })}>До изменения</button><button type="button" disabled={busy} className="button secondary compact" onClick={() => void perform(async () => { setSnapshot(await api<Snapshot>(`${path}/history/${version.id}`)); setPreview(null); })}>После изменения</button></div>)}</section>}
    {snapshot && <section className="pp-version-preview"><h3>{snapshot.title}</h3><p>{snapshot.description}</p><ContentView content={snapshot.content} /><button type="button" className="button secondary" disabled={disabled || busy} onClick={() => { if (window.confirm("Загрузить эту версию в редактор? Текущий черновик будет заменён; сохранение на сайте выполняется отдельно.")) { applyVersion(snapshot); setSnapshot(null); setNotice("Версия загружена в редактор."); } }}>Загрузить версию в редактор</button></section>}
  </section>;
}
