import React from "react";
import { Store, RefreshCcw, Pencil, Check, X, Search } from "lucide-react";
import { BrandIcon } from "./BrandIcon";
import { projectChanged } from "./projectNotificationEvents";
import "./styles/showcase-editor.css";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type Field = { id: string; key: string; label: string; value: string; list: boolean };
type Row = { id: string; brand: string; fields: Field[]; editable: boolean; group: string; logo?: string };
type Management = { complete: boolean; notes: string[]; sources: { id: string; kind: string; location: string; action: string; inline_edit: boolean }[] };
type Showcase = { management?: Management; revision: string; rows: Row[]; count: number; source: string; message: string; warning?: string };
type Draft = { rowId: string; revision: string; fields: Record<string, string>; requestId?: string; logo?: { name: string; data: string } };
type Receipt = { id: string; status: string; error?: string; showcase?: Showcase | null };
const isBrand = (field: Field) => field.key === "brand" || field.key === "name";
const errorText = (error: unknown) => error instanceof Error ? error.message : "Не удалось получить данные витрины.";

export function ShowcaseBrands({ siteId, api }: { siteId: string; api: Api }) {
  const [data, setData] = React.useState<Showcase | null>(null);
  const [draft, setDraft] = React.useState<Draft | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState("");
  const [message, setMessage] = React.useState("");
  const [query, setQuery] = React.useState("");
  const active = React.useRef(true);
  const savingRef = React.useRef(false);
  const storageKey = `pagepilot-showcase-draft:${siteId}`;
  const endpoint = `/sites/${siteId}/showcase`;
  const load = React.useCallback(async (refresh = false) => {
    setLoading(true); setError("");
    try {
      const next = await api<Showcase>(`${endpoint}${refresh ? "?refresh=true" : ""}`, { cache: "no-store" });
      if (!Array.isArray(next.rows)) throw new Error("Не получен список брендов витрины.");
      if (active.current) setData(next);
    } catch (cause) { if (active.current) setError(errorText(cause)); }
    finally { if (active.current) setLoading(false); }
  }, [api, endpoint]);
  React.useEffect(() => {
    active.current = true;
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
      if (saved && typeof saved.rowId === "string" && typeof saved.revision === "string" && saved.fields && typeof saved.fields === "object") setDraft(saved);
    } catch { /* Ignore an invalid local draft. */ }
    void load();
    return () => { active.current = false; };
  }, [load, storageKey]);
  function changeDraft(next: Draft | null) {
    setDraft(next);
    try { if (next) sessionStorage.setItem(storageKey, JSON.stringify(next)); else sessionStorage.removeItem(storageKey); } catch { /* Keep the visible draft if browser storage is full. */ }
  }
  function edit(row: Row) {
    if (!data) return;
    setError(""); setMessage("");
    changeDraft({ rowId: row.id, revision: data.revision, fields: Object.fromEntries(row.fields.map(field => [field.id, field.value])) });
  }
  function change(field: Field, value: string) {
    if (draft) changeDraft({ ...draft, fields: { ...draft.fields, [field.id]: value } });
  }
  async function selectLogo(file?: File) {
    if (!file || !draft) return;
    if (file.size > 2 * 1024 * 1024) { setError("Логотип должен быть не больше 2 МБ."); return; }
    const current = draft;
    try {
      const buffer = new Uint8Array(await file.arrayBuffer());
      let binary = "";
      for (const byte of buffer) binary += String.fromCharCode(byte);
      if (active.current) { changeDraft({ ...current, logo: { name: file.name, data: btoa(binary) } }); setError(""); }
    } catch { setError("Не удалось прочитать логотип."); }
  }
  async function save() {
    if (!draft || savingRef.current) return;
    savingRef.current = true; setSaving(true); setError(""); setMessage("");
    const checking = !!draft.requestId;
    const requestId = draft.requestId || crypto.randomUUID();
    const pending = { ...draft, requestId };
    changeDraft(pending);
    try {
      const receipt = checking
        ? await api<Receipt>(`${endpoint}/edits/${requestId}`, { cache: "no-store" })
        : await api<Receipt>(endpoint, { method: "PUT", body: JSON.stringify({ request_id: requestId, revision: draft.revision, row_id: draft.rowId, fields: draft.fields, logo: draft.logo }) });
      if (!active.current) return;
      if (receipt.status === "confirmed") {
        if (receipt.showcase) setData(receipt.showcase); else await load();
        changeDraft(null); setMessage("Карточка бренда сохранена и подтверждён в Webdev."); projectChanged(siteId);
      } else {
        setError(receipt.error || "Сохранение ещё не подтверждено. Нажмите «Проверить сохранение».");
        if (receipt.status === "failed") changeDraft({ ...pending, requestId: undefined });
      }
    } catch (cause) {
      if (!active.current) return;
      const code = (cause as { statusCode?: number }).statusCode;
      setError(errorText(cause));
      if (code && code >= 400 && code < 500) changeDraft({ ...pending, requestId: undefined });
    } finally {
      savingRef.current = false;
      if (active.current) setSaving(false);
    }
  }
  const normalized = query.trim().toLocaleLowerCase();
  const visible = (data?.rows || []).filter(row => row.id === draft?.rowId || !normalized || `${row.brand} ${row.fields.map(field => field.value).join(" ")}`.toLocaleLowerCase().includes(normalized));
  return <section className="projectShowcaseBrands" aria-label="Бренды витрины">
    <div className="showcaseToolbar">
      <div className="projectShowcaseHeading"><Store size={18} aria-hidden="true" /><h3>Бренды витрины</h3>{data && <span>{data.count}</span>}</div>
      <div className="showcaseTools"><label className="showcaseSearch"><Search size={16} aria-hidden="true" /><input aria-label="Поиск по брендам и тексту витрины" value={query} onChange={event => setQuery(event.target.value)} placeholder="Бренд или текст" /></label>
        <button type="button" className="button compact secondary" disabled={loading || saving} onClick={() => void load(true)}><RefreshCcw size={15} className={loading ? "spin" : ""} aria-hidden="true" />Обновить</button></div>
    </div>
    {error && <p className="showcaseError" role="alert">{error}</p>}
    {message && <p className="showcaseSuccess" role="status">{message}</p>}
    {loading && !data && <p role="status">Загружаем бренды и тексты витрины…</p>}
    {data && !data.rows.length && <p>{data.message}</p>}
    {!!data?.rows.length && <div className="showcaseTableWrap"><table className="showcaseTable">
      <thead><tr><th>Бренд</th><th>Текст и условия</th><th><span className="showcaseActionsHeading">Редактирование</span></th></tr></thead>
      <tbody>{visible.map(row => {
        const editing = draft?.rowId === row.id;
        const brandField = row.fields.find(isBrand);
        const textFields = row.fields.filter(field => !isBrand(field));
        return <tr key={row.id} className={editing ? "isEditing" : ""}>
          <td><div className="showcaseBrand">{row.logo ? <img className="showcaseLogo" src={row.logo} alt={row.brand} loading="lazy" /> : <BrandIcon brand={row.brand} />}{editing && brandField ? <input aria-label={`Бренд ${row.brand}`} value={draft.fields[brandField.id] ?? ""} disabled={saving || !!draft.requestId} onChange={event => change(brandField, event.target.value)} /> : <strong>{row.brand}</strong>}</div>{editing && <label className="showcaseLogoUpload">Логотип: PNG, JPEG, WebP (до 2 МБ)<input type="file" accept=".png,.jpg,.jpeg,.webp" disabled={saving || !!draft.requestId} onChange={event => void selectLogo(event.target.files?.[0])} />{draft.logo && <small>Выбран: {draft.logo.name}</small>}</label>}</td>
          <td>{editing ? <div className="showcaseFields">{textFields.map(field => <label key={field.id}>{field.label}<textarea aria-label={`${field.label} — ${row.brand}`} rows={field.list || ["bonus", "description", "text"].includes(field.key) ? 2 : 1} value={draft.fields[field.id] ?? ""} disabled={saving || !!draft.requestId} onChange={event => change(field, event.target.value)} /></label>)}</div>
            : <div className="showcaseTexts">{textFields.filter(field => field.value.trim()).map(field => <span key={field.id} className={["bonus", "description", "text"].includes(field.key) ? "showcasePrimaryText" : ""}><small>{field.label}: </small>{field.value}</span>)}{!textFields.some(field => field.value.trim()) && <span className="muted">{row.editable ? "Текст не заполнен" : "Текст находится в HTML-шаблоне витрины."}</span>}</div>}</td>
          <td><div className="showcaseRowActions">{editing ? <><button type="button" className="button compact" disabled={saving} onClick={() => void save()}><Check size={15} aria-hidden="true" />{saving ? "Сохраняем…" : draft.requestId ? "Проверить сохранение" : "Сохранить"}</button>{!draft.requestId && <button type="button" className="button compact secondary" disabled={saving} onClick={() => { changeDraft(null); setError(""); }}><X size={15} aria-hidden="true" />Отмена</button>}</>
            : row.editable && <button type="button" className="button compact secondary" disabled={!!draft || saving} onClick={() => edit(row)} aria-label={`Редактировать ${row.brand}`}><Pencil size={14} aria-hidden="true" />Изменить</button>}</div></td>
        </tr>;
      })}</tbody>
    </table>{!visible.length && <p>По вашему запросу бренды не найдены.</p>}</div>}
    {data?.management && <details className="showcaseManagement"><summary>Системные пометки об управлении витриной</summary>
      {!data.management.complete && <p className="muted">Способ подключения подтверждён не полностью. Нажмите «Обновить» для проверки Webdev.</p>}
      {data.management.sources.map(source => <div key={source.id}><strong>{({native: "Карточки Webdev", page_table: "Таблица страницы", page_code: "Блок кода", page_raw: "HTML-блок", shortcode: "Шорткод", layout: "Шаблон страницы", banner: "Баннер", external: "Внешняя витрина"} as Record<string,string>)[source.kind] || source.kind}</strong> · <code>{source.location}</code><p>{source.action}</p></div>)}
      <ul>{data.management.notes.map(note => <li key={note}>{note}</li>)}</ul>
    </details>}
    {data?.warning && <p className="muted">{data.warning}</p>}
    {data?.source === "cache" && !!data.rows.length && <small className="muted">Список из серверного кеша. При сохранении проверяется актуальная витрина в Webdev.</small>}
  </section>;
}
