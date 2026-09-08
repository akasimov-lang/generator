import React from "react";

type Page = { key: string; label: string; topic: string; path: string; existing?: { id: string; status: string; path: string } | null };
type Site = { id: string; name: string; homepage_title: string | null; geo: string; language: string };
type Settings = { facts?: string; menu_type?: string; auto_publish?: boolean; pages?: { key: string }[] };
type Props = {
  api: <T>(path: string, options?: RequestInit) => Promise<T>;
  sites: Site[];
  providers: { id: string; name: string }[];
  initialSiteId: string;
  initialProviderId: string;
  onCreated: () => void | Promise<void>;
  onClose: () => void;
};

export function TechnicalPagesForm({ api, sites, providers, initialSiteId, initialProviderId, onCreated, onClose }: Props) {
  const [siteId, setSiteId] = React.useState(initialSiteId || sites[0]?.id || "");
  const site = sites.find((candidate) => candidate.id === siteId);
  const providerId = providers.find((provider) => provider.id === initialProviderId)?.id || providers[0]?.id || "";
  const [catalog, setCatalog] = React.useState<Page[]>([]);
  const [selected, setSelected] = React.useState<string[]>([]);
  const [detectedBrand, setDetectedBrand] = React.useState("");
  const [facts, setFacts] = React.useState("");
  const [menuType, setMenuType] = React.useState("footer");
  const [autoPublish, setAutoPublish] = React.useState(true);
  const [preview, setPreview] = React.useState<Page[] | null>(null);
  const [existing, setExisting] = React.useState<Record<string, Page["existing"]>>({});
  const [busy, setBusy] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [createdTaskId, setCreatedTaskId] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setPreview(null);
    setCreatedTaskId(null);
    setDetectedBrand("");
    setCatalog([]);
    setSelected([]);
    setExisting({});
    if (!siteId) { setLoading(false); return; }
    api<{ catalog: Page[]; settings: Settings | null; existing: Record<string, Page["existing"]> }>(`/sites/${siteId}/technical-pages`)
      .then((data) => {
        if (cancelled) return;
        setCatalog(data.catalog);
        setExisting(data.existing);
        setSelected((data.settings?.pages?.map((page) => page.key) || data.catalog.map((page) => page.key)).filter((key) => !data.existing[key]));
        setFacts(data.settings?.facts || "");
        setMenuType(data.settings?.menu_type || "footer");
        setAutoPublish(data.settings?.auto_publish ?? true);
      }).catch((reason) => { if (!cancelled) setError(reason.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [api, siteId]);

  React.useEffect(() => { setPreview(null); }, [selected, facts, siteId, menuType, providerId]);

  function requestPayload() {
    return {
      brand: detectedBrand, facts: facts.trim(), geo: site?.geo || "", language: site?.language || "",
      ai_provider_id: providerId, menu_type: menuType, auto_publish: autoPublish, target_words: 550,
      pages: selected.map((key) => ({ key, label: preview?.find((page) => page.key === key)?.label || "", path: preview?.find((page) => page.key === key)?.path })),
    };
  }

  async function prepare(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setBusy("preview");
    try {
      const result = await api<{ pages: Page[]; brand: string }>(`/sites/${siteId}/technical-pages/preview`, { method: "POST", body: JSON.stringify(requestPayload()) });
      setPreview(result.pages);
      setDetectedBrand(result.brand);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Не удалось подготовить страницы"); }
    finally { setBusy(""); }
  }

  async function launch() {
    setError("");
    setBusy("launch");
    try {
      let taskId = createdTaskId;
      if (!taskId) {
        const task = await api<{ id: string }>(`/sites/${siteId}/technical-pages/tasks`, { method: "POST", body: JSON.stringify(requestPayload()) });
        taskId = task.id;
        setCreatedTaskId(task.id);
      }
      await api(`/tasks/${taskId}/start`, { method: "POST" });
      await onCreated();
      onClose();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Не удалось запустить генерацию"); }
    finally { setBusy(""); }
  }

  const ready = Boolean(siteId && providerId && site?.homepage_title && site?.geo && site?.language && selected.length && !loading && !busy);
  const newCount = preview?.filter((page) => !page.existing).length || 0;
  return <form className="formGrid createTaskForm technicalPagesForm" onSubmit={prepare}>
    <fieldset className="technicalPagesFields wide" disabled={Boolean(loading || busy || createdTaskId)}>
      <div className="formGrid">
        {sites.length > 1 ? <label>Проект<select value={siteId} onChange={(event) => setSiteId(event.target.value)}>{sites.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label> : null}
        <label>Расположение<select value={menuType} onChange={(event) => setMenuType(event.target.value)}><option value="footer">Футер — внизу сайта</option><option value="header">Хедер — вверху сайта</option></select></label>
        <p className="wide">{site?.name} · {site?.language.toUpperCase()} · {site?.geo.toUpperCase()} · 500–600 слов на страницу. Тематика — по главной странице проекта.</p>
        <div className="technicalPageSelection wide">
          <div className="technicalPageSelectionHeader"><strong>Выбрано {selected.length} из {catalog.length}</strong><button type="button" className="button secondary compact" onClick={() => setSelected(catalog.filter((page) => !existing[page.key]).map((page) => page.key))}>Весь набор</button><button type="button" className="button secondary compact" onClick={() => setSelected([])}>Снять выбор</button></div>
          {catalog.map((page) => <label className="checkboxRow technicalPageChoice" key={page.key}><input type="checkbox" checked={selected.includes(page.key)} disabled={Boolean(existing[page.key])} onChange={(event) => setSelected(event.target.checked ? [...selected, page.key] : selected.filter((key) => key !== page.key))} /><span><b>{page.label}</b><small>{page.topic}{existing[page.key] ? " · Уже есть — будет пропущена" : ""}</small></span></label>)}
        </div>
        <label className="wide">Замечания к текстам <small>Необязательно</small><textarea rows={3} value={facts} onChange={(event) => setFacts(event.target.value)} maxLength={12000} placeholder="Например: контакты для обращений, сведения о cookie или пожелания к содержанию." /></label>
        <label className="checkboxRow wide"><input type="checkbox" checked={autoPublish} onChange={(event) => setAutoPublish(event.target.checked)} /><span><b>Опубликовать автоматически</b><small>Автоматически принять тексты, добавить пункты меню и опубликовать. Отключите, чтобы сначала проверить тексты.</small></span></label>
      </div>
    </fieldset>
    {!providerId ? <p className="formError wide">Добавьте активный Gemini-провайдер в настройках.</p> : null}
    {!site?.homepage_title && !loading ? <p className="formError wide">Обновите проект: для генерации нужен Title главной страницы.</p> : null}
    {loading ? <p className="wide">Загружаем настройки проекта…</p> : null}
    {preview ? <div className="wide technicalPagesPreview"><strong>Предпросмотр · {menuType === "footer" ? "Footer" : "Header"} · новых страниц: {newCount}</strong><p>Подписи можно изменить. Адреса уже записаны латиницей и сохранятся при правке подписи.</p>{preview.map((page) => <label className="technicalPagePreviewRow" key={page.key}><span>{catalog.find((entry) => entry.key === page.key)?.label}<small>{page.existing ? `Уже существует · ${page.existing.path}` : page.path}</small></span><input aria-label={`Подпись меню: ${page.topic}`} value={page.label} maxLength={60} required disabled={Boolean(page.existing || busy || createdTaskId)} onChange={(event) => setPreview(preview.map((entry) => entry.key === page.key ? { ...entry, label: event.target.value } : entry))} /></label>)}</div> : null}
    {error ? <span className="formError wide" role="alert">{error}</span> : null}
    {createdTaskId && error ? <p className="wide">Задача уже создана. Повторный запуск продолжит её без создания дублей; она также доступна в списке задач.</p> : null}
    <div className="formActions wide"><button className="button secondary" type="button" onClick={onClose} disabled={Boolean(busy)}>Закрыть</button>{!createdTaskId ? <button className="button secondary" type="submit" disabled={!ready}>{busy === "preview" ? "Подготавливаем…" : preview ? "Обновить предпросмотр" : "Подготовить страницы"}</button> : null}{preview || createdTaskId ? <button className="button primary" type="button" onClick={() => void launch()} disabled={Boolean(busy) || (!createdTaskId && (!ready || !newCount || preview?.some((page) => !page.label.trim())))}>{busy === "launch" ? "Запускаем…" : createdTaskId ? "Повторить запуск" : autoPublish ? `Сгенерировать и опубликовать (${newCount})` : `Сгенерировать (${newCount})`}</button> : null}</div>
  </form>;
}
