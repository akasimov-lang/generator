import React from "react";
import { Copy, Download, LoaderCircle, Sparkles } from "lucide-react";
import { LANGUAGE_OPTIONS } from "./languageOptions";
import "./styles/auto-lb.css";

type Kind = "anchors" | "topics";
type Context = { brand: string; geo: string; language: string; main: string; main_url: string };
type Generation = { id: string; kind: Kind; status: string; context: Context; prompt: string; text: string;
  error: string | null; line_count: number; unique_count: number; created_at: string };
type State = { context: Context | null; context_error: string | null; provider_ready: boolean;
  anchor_count: number; topic_count: number; prompts: Partial<Record<Kind, string>>; generations: Generation[] };
type Api = <T>(path: string, init?: RequestInit) => Promise<T>;
const pending = (row: Generation) => row.status === "queued" || row.status === "running";
const statusLabel: Record<string, string> = { queued: "В очереди", running: "Gemini генерирует список", completed: "Готово", failed: "Ошибка генерации" };

async function copy(text: string) {
  if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
  const previous = document.activeElement as HTMLElement | null;
  const input = document.createElement("textarea");
  input.value = text; input.style.position = "fixed"; input.style.left = "-9999px";
  document.body.appendChild(input); input.select();
  try { if (!document.execCommand("copy")) throw new Error("Выделите список и скопируйте вручную."); }
  finally { input.remove(); previous?.focus(); }
}

function localeLabel(context: Context) {
  const flag = String.fromCodePoint(...[...context.geo].map(c => 127397 + c.charCodeAt(0)));
  const country = new Intl.DisplayNames(["ru"], { type: "region" }).of(context.geo) || context.geo;
  const language = LANGUAGE_OPTIONS.find(option => option.code === context.language)?.nativeName
    || new Intl.DisplayNames(["ru"], { type: "language" }).of(context.language) || context.language;
  return `${flag} ${context.geo} — ${country} · ${language}`;
}

export function AutoLbPanel({ siteId, api }: { siteId: string; api: Api }) {
  const [state, setState] = React.useState<State | null>(null);
  const [loadError, setLoadError] = React.useState("");
  const [errors, setErrors] = React.useState<Partial<Record<Kind, string>>>({});
  const [busy, setBusy] = React.useState<Partial<Record<Kind, boolean>>>({});
  const [selected, setSelected] = React.useState<Partial<Record<Kind, string>>>({});
  const [copied, setCopied] = React.useState<Partial<Record<Kind, string>>>({});
  const alive = React.useRef(true);
  React.useEffect(() => {
    alive.current = true;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      let delay = 10000;
      try {
        const next = await api<State>(`/sites/${siteId}/auto-lb`);
        if (disposed) return;
        setState(next); setLoadError("");
        if (next.generations.some(pending)) delay = 2500;
      } catch (error) { if (!disposed) setLoadError(error instanceof Error ? error.message : "Не удалось загрузить АвтоЛБ."); }
      if (!disposed) timer = setTimeout(refresh, delay);
    }
    void refresh();
    return () => { disposed = true; alive.current = false; clearTimeout(timer); };
  }, [api, siteId]);

  async function generate(kind: Kind) {
    setBusy(current => ({ ...current, [kind]: true }));
    setErrors(current => ({ ...current, [kind]: "" }));
    try {
      const row = await api<Generation>(`/sites/${siteId}/auto-lb`, { method: "POST", body: JSON.stringify({ kind }) });
      if (!alive.current) return;
      setState(current => current ? { ...current, generations: [row, ...current.generations.filter(item => item.id !== row.id)] } : current);
      setSelected(current => ({ ...current, [kind]: row.id }));
    } catch (error) {
      if (alive.current) setErrors(current => ({ ...current, [kind]: error instanceof Error ? error.message : "Не удалось запустить генерацию." }));
    } finally { if (alive.current) setBusy(current => ({ ...current, [kind]: false })); }
  }

  async function copyResult(kind: Kind, row: Generation) {
    try {
      await copy(row.text);
      if (alive.current) setCopied(current => ({ ...current, [kind]: row.id }));
    } catch (error) { if (alive.current) setErrors(current => ({ ...current, [kind]: error instanceof Error ? error.message : "Не удалось скопировать." })); }
  }

  function download(row: Generation) {
    const url = URL.createObjectURL(new Blob([row.text], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url;
    link.download = `autolb-${row.kind}-${row.context.main}-${row.context.language}.txt`;
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <section className="autoLb" aria-label="АвтоЛБ">
    <header className="autoLbHeader">
      <div><h2>АвтоЛБ</h2><p className="muted">Анкор-лист и рекламно-информационные темы для выбранного проекта.</p></div>
      {state?.context && <div className="autoLbContext"><b>{state.context.brand}</b><span>{localeLabel(state.context)}</span><span>Main: {state.context.main}</span></div>}
    </header>
    {loadError && <p role="alert" className="notice">{loadError}</p>}
    {state?.context_error && <p role="alert" className="notice">{state.context_error}</p>}
    {state && !state.provider_ready && <p role="alert" className="notice">Настройте активный Gemini с API-ключом в разделе API Providers.</p>}
    {!state && !loadError && <p role="status">Загрузка АвтоЛБ…</p>}
    <div className="autoLbColumns">
      {(["anchors", "topics"] as Kind[]).map(kind => {
        const rows = state?.generations.filter(row => row.kind === kind) || [];
        const row = rows.find(item => item.id === selected[kind]) || rows[0];
        const active = rows.find(pending);
        const title = kind === "anchors" ? "Анкор-лист" : "Генерация тем";
        const count = kind === "anchors" ? state?.anchor_count ?? 87 : 100;
        const changed = row && state?.context && Object.keys(row.context).some(key => row.context[key as keyof Context] !== state.context?.[key as keyof Context]);
        return <section className="autoLbCard" key={kind} aria-label={title}>
          <div className="autoLbCardTitle"><h3>{title}</h3><span className="autoLbCount">{count} строк</span></div>
          <p className="muted autoLbDescription">{kind === "anchors"
            ? "Структура и повторы из вашего образца. Перевод на язык проекта, домен и URL — текущий Main."
            : "100 разных рекламно-информационных тем по вашему примеру, на языке и для бренда проекта."}</p>
          <button type="button" className="button" disabled={!state?.context || !state.provider_ready || !!active || !!busy[kind] || !!loadError}
            onClick={() => void generate(kind)}>
            {active || busy[kind] ? <LoaderCircle size={16} className="autoLbSpinner" /> : <Sparkles size={16} />}
            {active ? statusLabel[active.status] : busy[kind] ? "Запуск…" : kind === "anchors" ? "Сгенерировать анкор-лист" : "Сгенерировать 100 тем"}
          </button>
          {(active || busy[kind]) && <p className="muted" role="status">Задача выполняется на сервере. Можно закрыть вкладку.</p>}
          {errors[kind] && <p role="alert" className="notice">{errors[kind]}</p>}
          {row?.error && <p role="alert" className="notice">{row.error}</p>}
          {changed && <p className="notice">Этот результат создан для {row.context.brand}, {row.context.geo}, {row.context.language}, Main: {row.context.main}. Параметры проекта изменились — запустите новую генерацию.</p>}
          <div className="autoLbResultBar"><span>{row ? statusLabel[row.status] : "Результат"}{row?.text ? ` · ${row.line_count} строк${kind === "anchors" ? ` · ${row.unique_count} уникальных` : ""}` : ""}</span>
            <div className="autoLbActions"><button type="button" className="button secondary compact" disabled={!row?.text}
              aria-label={`Скопировать ${kind === "anchors" ? "анкор-лист" : "темы"}`} title="Скопировать" onClick={() => row && void copyResult(kind, row)}>
              <Copy size={16} /><span>{row && copied[kind] === row.id ? "Скопировано" : "Скопировать"}</span></button>
              <button type="button" className="button secondary compact" disabled={!row?.text} aria-label={`Скачать ${title} TXT`} title="Скачать TXT" onClick={() => row && download(row)}><Download size={16} /></button></div>
          </div>
          <textarea className="autoLbResult" aria-label={`Результат: ${title}`} readOnly dir="auto" value={row?.text || ""}
            placeholder={kind === "anchors" ? "Каждый анкор с новой строки. Повторы сохраняются." : "Каждая тема с новой строки, без нумерации."} />
          <details><summary>Промпт для Gemini</summary><pre className="autoLbPrompt">{row?.prompt || state?.prompts[kind] || "Заполните бренд, ГЕО, язык и Main проекта."}</pre></details>
          {rows.length > 0 && <details><summary>История генераций ({rows.length})</summary><div className="autoLbHistory">{rows.map(item => <button type="button"
            key={item.id} className="button secondary compact" aria-pressed={row?.id === item.id} onClick={() => setSelected(current => ({ ...current, [kind]: item.id }))}>
            {new Date(item.created_at).toLocaleString("ru-RU")} · {statusLabel[item.status]}</button>)}</div></details>}
        </section>;
      })}
    </div>
  </section>;
}
