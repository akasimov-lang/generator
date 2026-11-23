import React from "react";
import { SaveIndicator } from "./SaveIndicator";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type Policy = { site_id: string; enabled: boolean };
export function ReglueRedirectPolicy({siteId, api, onBusyChange}: {siteId: string; api: Api; onBusyChange: (busy: boolean) => void}) {
  const [enabled, setEnabled] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [saved, setSaved] = React.useState(false);
  const [error, setError] = React.useState("");
  const [attempt, setAttempt] = React.useState(0);
  const apiRef = React.useRef(api); apiRef.current = api;
  const mounted = React.useRef(true);
  const inFlight = React.useRef(false);
  const path = `/auto-reglue/projects/${encodeURIComponent(siteId)}/redirect-policy`;
  function confirmed(value: Policy) {
    if (value?.site_id !== siteId || typeof value.enabled !== "boolean") throw new Error("Сервер не подтвердил настройку редиректов.");
    return value.enabled;
  }
  React.useEffect(() => {
    mounted.current = true; let cancelled = false;
    setLoading(true); onBusyChange(true);
    void apiRef.current<Policy>(path).then(value => {
      if (!cancelled) { setEnabled(confirmed(value)); setError(""); }
    }).catch(error => {
      if (!cancelled) setError(error instanceof Error ? error.message : "Не удалось загрузить настройку.");
    }).finally(() => { if (!cancelled) { setLoading(false); onBusyChange(false); } });
    return () => { cancelled = true; mounted.current = false; };
  }, [siteId, attempt]);
  async function save(next: boolean) {
    if (loading || inFlight.current) return;
    inFlight.current = true; setSaving(true); setError(""); setSaved(false); onBusyChange(true);
    try {
      const value = await apiRef.current<Policy>(path, {method: "PATCH", body: JSON.stringify({enabled: next})});
      const actual = confirmed(value);
      if (actual !== next) throw new Error("Настройка не сохранена. Повторите попытку.");
      if (mounted.current) { setEnabled(actual); setSaved(true); }
    } catch (error) {
      if (mounted.current) setError(error instanceof Error ? error.message : "Не удалось сохранить настройку.");
    } finally {
      inFlight.current = false;
      if (mounted.current) { setSaving(false); onBusyChange(false); }
    }
  }
  return <div className="networkActions" aria-busy={loading || saving}>
    <label className="checkboxRow" title="Выключено: при переклее сохраняются существующие назначения доменных редиректов. Настройка применяется к ручным и автоматическим переклеям.">
      <input type="checkbox" checked={enabled} disabled={loading || saving} onChange={event => void save(event.currentTarget.checked)} />
      301 редирект на главный домен при переклее
    </label>
    <SaveIndicator state={error ? "error" : saving ? "saving" : saved ? "saved" : "idle"} error={error} label="Редиректы при переклее" version={String(enabled)} />
    {error && <button type="button" className="button secondary compact" onClick={() => setAttempt(value => value + 1)}>Проверить настройку</button>}
  </div>;
}
