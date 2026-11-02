import React from "react";
import { Link2, Save } from "lucide-react";
type Api = <T>(path: string, init?: RequestInit) => Promise<T>;
type Settings = { anchors: string[]; source: string };
const values = (text: string) => [...new Map(text.split(/[,\n\r]+/).map(value => value.trim().replace(/\s+/g, " ")).filter(Boolean).map(value => [value.toLowerCase(), value])).values()];
export function GenerationAnchors({ siteId, api }: { siteId: string; api: Api }) {
  const [text, setText] = React.useState("");
  const [saved, setSaved] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState("");
  const flight = React.useRef(false);
  React.useEffect(() => {
    let cancelled = false;
    setLoading(true); setError("");
    api<Settings>(`/sites/${siteId}/pages/generation-anchors`, { cache: "no-store" }).then(result => {
      if (cancelled) return;
      if (!Array.isArray(result.anchors)) throw new Error("Не получен список анкоров.");
      const next = result.anchors.join("\n"); setText(next); setSaved(next);
    }).catch(cause => { if (!cancelled) setError(cause instanceof Error ? cause.message : "Не удалось загрузить анкоры."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [siteId, api]);
  const dirty = JSON.stringify(values(text)) !== JSON.stringify(values(saved));
  async function save() {
    if (loading || flight.current || !dirty) return;
    flight.current = true; setSaving(true); setError("");
    try {
      const result = await api<Settings>(`/sites/${siteId}/pages/generation-anchors`, { method: "PUT", body: JSON.stringify({ anchors: text }) });
      const next = result.anchors.join("\n"); setText(next); setSaved(next);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Не удалось сохранить анкоры."); }
    finally { flight.current = false; setSaving(false); }
  }
  return <section className="panel" aria-label="Анкоры для генерации">
    <div className="panelHeader"><h3><Link2 size={16} /> Анкоры на главную</h3><button type="button" className="button secondary compact" disabled={loading || saving || !dirty} onClick={() => void save()}><Save size={14} />{saving ? "Сохраняем…" : "Сохранить анкоры"}</button></div>
    <label className="field">Анкоры<textarea aria-label="Анкоры на главную" rows={3} value={text} disabled={loading || saving} placeholder="По одному на строку или через запятую" onChange={event => setText(event.target.value)} onBlur={() => void save()} /></label>
    <small className="muted">Один случайный анкор на статью, без равномерного распределения. Ссылка на / вставляется только в обычный абзац. Изменения сохраняются при клике вне поля.</small>
    {error && <p role="alert" className="formError">{error}</p>}
  </section>;
}
