import React from "react";
import { TemplateCombobox } from "./TemplateCombobox";

type Config = { enabled: boolean; model: string; provider_id: string; include_logo: boolean; models: string[] };
type Api = <T>(path: string, options?: RequestInit) => Promise<T>;

export function ArticleImageSettings({ api, providers }: { api: Api; providers: { id: string; name: string; provider_type: string; is_active: boolean }[] }) {
  const [config, setConfig] = React.useState<Config | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const [saved, setSaved] = React.useState(false);
  React.useEffect(() => {
    let cancelled = false;
    api<Config>("/article-images/settings").then(value => { if (!cancelled) setConfig(value); })
      .catch(error => { if (!cancelled) setError(error.message); });
    return () => { cancelled = true; };
  }, [api]);
  function change(value: Partial<Config>) { setConfig(current => current ? { ...current, ...value } : current); setSaved(false); }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!config) return;
    setBusy(true); setError(""); setSaved(false);
    try {
      const { enabled, model, provider_id, include_logo } = config;
      setConfig(await api<Config>("/article-images/settings", { method: "PUT", body: JSON.stringify({ enabled, model, provider_id, include_logo }) }));
      setSaved(true);
    } catch (error) { setError(error instanceof Error ? error.message : "Не удалось сохранить настройки."); }
    finally { setBusy(false); }
  }
  return <section className="panel">
    <h2>Изображения в текстах</h2>
    <p>Яркий уникальный баннер 1200 × 300 после второго абзаца новой внутренней страницы. Текст создаёт выбранная текстовая модель, изображение — отдельная модель Gemini с тем же ключом.</p>
    {config ? <form className="formGrid" onSubmit={save}>
      <label className="checkboxRow wide"><input type="checkbox" checked={config.enabled} onChange={event => change({ enabled: event.target.checked })} /> Генерировать изображения автоматически</label>
      <TemplateCombobox label="Gemini для изображений" value={config.provider_id} onChange={provider_id => change({ provider_id })}
        options={[{ value: "", label: "Gemini текущей задачи" }, ...providers.filter(provider => provider.provider_type === "gemini" && provider.is_active).map(provider => ({ value: provider.id, label: provider.name }))]} />
      <TemplateCombobox label="Модель изображений" value={config.model} onChange={model => change({ model })}
        options={config.models.map(model => ({ value: model, label: model }))} />
      <label className="checkboxRow wide"><input type="checkbox" checked={config.include_logo} onChange={event => change({ include_logo: event.target.checked })} /> Добавлять официальный логотип из библиотеки бренда, если он есть</label>
      <small className="wide">Генерация изображений расходует квоту Gemini. При ошибке готовый текст сохраняется; изображение можно повторить отдельно в предпросмотре.</small>
      <div className="formActions wide"><button className="button primary" disabled={busy}>{busy ? "Сохраняю…" : "Сохранить настройки изображений"}</button>{saved ? <span role="status">Сохранено</span> : null}</div>
    </form> : null}
    {error ? <p className="formError" role="alert">{error}</p> : null}
  </section>;
}
