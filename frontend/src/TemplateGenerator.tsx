import React from "react";
import { Download, Monitor, Smartphone, Plus, ArrowLeft, Loader2, CheckCircle2, AlertCircle, RefreshCcw, Sparkles, Search, ChevronRight } from "lucide-react";
import "./styles/template-generator.css";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type Provider = { id: string; name: string; provider_type: string; is_active: boolean };
type Section = { id: string; title: string; paragraphs: string[]; bullets: string[]; table: string[][] };
type Content = { title: string; description: string; heading: string; intro: string; menu_label: string; cta_label: string; faq_title: string; footer_text: string; sections: Section[]; faq: { question: string; answer: string }[]; editorial_notes: string[] };
type Menu = { id: string; label: string; section_id: string; mode: "fake" | "real"; url: string; header: boolean; footer: boolean };
type Summary = { id: string; brand: string; geo: string; language: string; status: string; phase: string; error: string | null; revision: number; created_at: string; updated_at: string };
type Template = Summary & { html: string | null; request: { uniqueness_scope: string }; document: null | {
  content?: Content; menu?: Menu[]; design?: Record<string, string>; design_rationale?: string;
  comparisons?: { template_id: string; similarity: number; passed: boolean }[];
  visual_comparisons?: { template_id: string; score: number; passed: boolean; explanation: string }[];
  screenshots?: Record<string, string>;
  research?: { query: string; analysis: string; sources: { url: string; title: string; status: string; position: number }[] };
} };
const GEO = [ ["PL", "Польша", "pl"], ["DE", "Германия", "de"], ["CZ", "Чехия", "cs"], ["RU", "Россия", "ru"], ["GB", "Великобритания", "en"], ["US", "США", "en"], ["CA", "Канада", "en"], ["BR", "Бразилия", "pt"], ["ES", "Испания", "es"], ["FR", "Франция", "fr"], ["IT", "Италия", "it"], ["IN", "Индия", "en"], ["TR", "Турция", "tr"], ["KZ", "Казахстан", "ru"], ["SE", "Швеция", "sv"], ["AU", "Австралия", "en"] ];
const languages = [["en", "English"], ["pl", "Polski"], ["de", "Deutsch"], ["cs", "Čeština"], ["ru", "Русский"], ["pt", "Português"], ["es", "Español"], ["fr", "Français"], ["it", "Italiano"], ["tr", "Türkçe"], ["sv", "Svenska"], ["uk", "Українська"], ["hi", "हिन्दी"], ["kk", "Қазақша"]];
const statusLabels: Record<string, string> = { queued: "В очереди", generating: "Генерируется", ready: "Готов", failed: "Ошибка" };
const busyStatus = (status: string) => ["queued", "generating"].includes(status);
const errorText = (e: unknown) => e instanceof Error ? e.message : "Не удалось выполнить действие";

export function TemplateGenerator({ api }: { api: Api }) {
  const [items, setItems] = React.useState<Summary[]>([]);
  const [providers, setProviders] = React.useState<Provider[]>([]);
  const [selected, setSelected] = React.useState<Template | null>(null);
  const [screen, setScreen] = React.useState<"list" | "new" | "detail">("list");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [search, setSearch] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [form, setForm] = React.useState({ brand: "", geo: "PL", language: "pl", ai_provider_id: "", uniqueness_scope: "brand_geo", collect_competitors: true, keyword: "", facts: "" });
  const requestSequence = React.useRef(0);
  const loadList = React.useCallback(async () => {
    const data = await api<Summary[]>("/site-templates");
    setItems(data);
  }, [api]);
  React.useEffect(() => {
    let live = true;
    Promise.all([api<Summary[]>("/site-templates"), api<Provider[]>("/ai-providers")]).then(([rows, p]) => {
      if (!live) return;
      setItems(rows); setProviders(p);
      setForm(f => ({ ...f, ai_provider_id: f.ai_provider_id || p.find(p => p.provider_type === "gemini" && p.is_active)?.id || "" }));
    }).catch(e => { if (live) setError(errorText(e)); }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; requestSequence.current++; };
  }, [api]);
  React.useEffect(() => {
    if (!items.some(i => busyStatus(i.status)) && !(selected && busyStatus(selected.status))) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const rows = await api<Summary[]>("/site-templates");
        if (!live) return;
        setItems(rows);
        if (selected && busyStatus(selected.status)) {
          const detail = await api<Template>(`/site-templates/${selected.id}`);
          if (live) setSelected(detail);
        }
      } catch (e) { if (live) setError(errorText(e)); }
      if (live) timer = setTimeout(poll, 4000);
    };
    timer = setTimeout(poll, 4000);
    return () => { live = false; clearTimeout(timer); };
  }, [api, items.some(i => busyStatus(i.status)), selected?.id, selected?.status]);

  async function open(id: string) {
    const seq = ++requestSequence.current;
    setError(""); setLoading(true);
    try {
      const detail = await api<Template>(`/site-templates/${id}`);
      if (seq === requestSequence.current) { setSelected(detail); setScreen("detail"); }
    } catch (e) { if (seq === requestSequence.current) setError(errorText(e)); }
    finally { if (seq === requestSequence.current) setLoading(false); }
  }
  async function create(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const result = await api<Template>("/site-templates", { method: "POST", body: JSON.stringify(form) });
      setSelected(result); setItems(rows => [result, ...rows]); setScreen("detail");
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  const gemini = providers.filter(p => p.provider_type === "gemini" && p.is_active);
  const filtered = items.filter(i => `${i.brand} ${i.geo} ${i.language}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  return <div className="tg">
    {error && <div className="tg-alert" role="alert"><AlertCircle size={18} />{error}<button type="button" onClick={() => setError("")} aria-label="Закрыть ошибку">×</button></div>}
    {screen === "list" && <>
      <div className="tg-heading"><div><h2>Ваши шаблоны</h2><p>Одностраничные сайты с контентом, дизайном и готовым меню.</p></div><button className="button primary" onClick={() => { setError(""); setScreen("new"); }}><Plus size={18} />Создать шаблон</button></div>
      {loading ? <div className="tg-empty"><Loader2 className="tg-spin" />Загружаем шаблоны…</div> : items.length === 0 ? <div className="tg-empty"><Sparkles size={36} /><h3>Первый шаблон начинается с бренда</h3><p>Gemini изучит конкурентов, подготовит текст и выберет самостоятельный дизайн. Результат можно посмотреть и скачать.</p><button className="button primary" onClick={() => setScreen("new")}>Создать первый шаблон</button></div> : <>
        <label className="tg-search"><Search size={18} /><input placeholder="Найти по бренду или ГЕО" value={search} onChange={e => setSearch(e.target.value)} /></label>
        <div className="tg-list">{filtered.map(item => <button className="tg-row" key={item.id} onClick={() => void open(item.id)}><div><strong>{item.brand}</strong><span>{item.geo} · {item.language.toUpperCase()} · {new Date(item.created_at).toLocaleDateString("ru-RU")}</span></div><span className={`tg-status tg-${item.status}`}>{busyStatus(item.status) && <Loader2 size={14} className="tg-spin" />}{statusLabels[item.status] || item.status}</span><ChevronRight size={18} /></button>)}</div>
        {filtered.length === 0 && <p>По этому запросу шаблонов нет.</p>}
      </>}
    </>}
    {screen === "new" && <>
      <button className="button secondary" onClick={() => setScreen("list")}><ArrowLeft size={16} />Все шаблоны</button>
      <div className="tg-create-layout"><form className="tg-card" onSubmit={create}>
        <h2>Новый шаблон</h2><p>Укажите бренд и страну. Остальное генератор подготовит автоматически.</p>
        <label>Бренд<input autoFocus required maxLength={160} placeholder="Название бренда" value={form.brand} onChange={e => setForm({ ...form, brand: e.target.value })} /></label>
        <div className="tg-fields"><label>ГЕО<input required aria-label="ГЕО" list="template-geos" pattern="[A-Za-z]{2}" title="Двухбуквенный код страны, например DE или PL" minLength={2} maxLength={2} value={form.geo} onChange={e => { const geo = e.target.value.toUpperCase(); setForm({ ...form, geo, language: GEO.find(g => g[0] === geo)?.[2] || form.language }); }} /><datalist id="template-geos">{GEO.map(([code, name]) => <option key={code} value={code}>{name}</option>)}</datalist></label><label>Язык<select aria-label="Язык" value={form.language} onChange={e => setForm({ ...form, language: e.target.value })}>{languages.map(([code, name]) => <option key={code} value={code}>{name}</option>)}</select></label></div>
        <label>Gemini<select aria-label="Gemini" required value={form.ai_provider_id} onChange={e => setForm({ ...form, ai_provider_id: e.target.value })}><option value="" disabled>Выберите провайдер</option>{gemini.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
        {gemini.length === 0 && <p className="tg-help">Сначала подключите Gemini в <a href="/ai-providers">API Providers</a>.</p>}
        <label className="tg-check"><input type="checkbox" checked={form.collect_competitors} onChange={e => setForm({ ...form, collect_competitors: e.target.checked })} /><span><strong>На основе выдачи и конкурентов</strong><small>До 10 страниц из Google через DataForSEO. Анализ сохранится вместе с шаблоном.</small></span></label>
        <fieldset className="tg-scope"><legend>С чем сравнивать уникальность</legend><label><input type="radio" name="scope" checked={form.uniqueness_scope === "brand_geo"} onChange={() => setForm({ ...form, uniqueness_scope: "brand_geo" })} /><span>Этот бренд + ГЕО<small>Рекомендуется для обычной генерации</small></span></label><label><input type="radio" name="scope" checked={form.uniqueness_scope === "global"} onChange={() => setForm({ ...form, uniqueness_scope: "global" })} /><span>Все шаблоны<small>Сравнение со всей историей генератора</small></span></label></fieldset>
        <details className="tg-options"><summary>Дополнительные настройки</summary><label>Поисковый запрос<input maxLength={250} placeholder={form.brand || "По умолчанию — название бренда"} value={form.keyword} onChange={e => setForm({ ...form, keyword: e.target.value })} /></label><label>Проверенные сведения о бренде<textarea rows={5} maxLength={20000} placeholder="Особенности, условия, подтверждённые контакты и другие факты, которые нужно учесть." value={form.facts} onChange={e => setForm({ ...form, facts: e.target.value })} /></label></details>
        <button className="button primary tg-submit" disabled={busy || !form.brand.trim() || !form.ai_provider_id}>{busy ? <Loader2 size={18} className="tg-spin" /> : <Sparkles size={18} />}{busy ? "Создаём задачу…" : "Сгенерировать шаблон"}</button>
      </form><aside className="tg-card tg-explainer"><h3>Что получится</h3><ol><li><strong>Контент под бренд и ГЕО</strong><p>Анализ источников, структура страницы и текст на выбранном языке.</p></li><li><strong>Самостоятельный дизайн</strong><p>Три концепции, 15 параметров уникальности и сравнение готового вида с историей.</p></li><li><strong>Готовый одностраничник</strong><p>Хедер, футер и адаптивное меню без JavaScript.</p></li></ol><div className="tg-note">По умолчанию пункты фейкового меню ведут к секциям страницы. Позже им можно назначить реальные адреса.</div><p className="tg-help">Генерация занимает несколько минут. Можно закрыть раздел — результат сохранится здесь.</p></aside></div>
    </>}
    {screen === "detail" && selected && <TemplateDetail key={`${selected.id}:${selected.revision}:${selected.status}`} template={selected} api={api} onBack={() => { setScreen("list"); void loadList().catch(e => setError(errorText(e))); }} onUpdate={t => { setSelected(t); setItems(rows => rows.map(r => r.id === t.id ? t : r)); }} />}
  </div>;
}

function TemplateDetail({ template: t, api, onBack, onUpdate }: { template: Template; api: Api; onBack: () => void; onUpdate: (t: Template) => void }) {
  const [tab, setTab] = React.useState("preview");
  const [mobile, setMobile] = React.useState(false);
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState("");
  const [draft, setDraft] = React.useState(() => t.document?.content ? structuredClone(t.document.content) : null);
  const [menu, setMenu] = React.useState(() => structuredClone(t.document?.menu || []));
  const [dirty, setDirty] = React.useState(false);
  const pending = busyStatus(t.status);
  React.useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  async function action(name: string, fn: () => Promise<void>) { setBusy(name); setError(""); try { await fn(); } catch (e) { setError(errorText(e)); } finally { setBusy(""); } }
  function editContent(next: Content) { setDraft(next); setDirty(true); }
  function editMenu(index: number, patch: Partial<Menu>) { setMenu(menu.map((m, i) => i === index ? { ...m, ...patch } : m)); setDirty(true); }
  async function download(kind: string) {
    await action(kind, async () => {
      const file = await api<{ filename: string; mime: string; base64: string }>(`/site-templates/${t.id}/download/${kind}`);
      const bytes = Uint8Array.from(atob(file.base64), c => c.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], { type: file.mime }));
      const link = document.createElement("a"); link.href = url; link.download = file.filename; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    });
  }
  const tabs = [["preview", "Предпросмотр"], ["content", "Контент"], ["menu", "Меню"], ["research", "Конкуренты"], ["checks", "Проверки"]];
  return <>
    <button className="button secondary" onClick={() => { if (!dirty || window.confirm("Есть несохранённые изменения. Выйти без сохранения?")) onBack(); }}><ArrowLeft size={16} />Все шаблоны</button>
    <div className="tg-heading"><div><h2>{t.brand} <span className="tg-muted">/ {t.geo}</span></h2><p>{t.language.toUpperCase()} · Одностраничник · Уникальность: {t.request.uniqueness_scope === "global" ? "все шаблоны" : "бренд + ГЕО"}</p></div><span className={`tg-status tg-${t.status}`}>{statusLabels[t.status]}</span></div>
    {(error || t.error) && <div className="tg-alert" role="alert"><AlertCircle size={18} /><span>{error || t.error}</span>{t.status === "failed" && <button disabled={!!busy} className="button secondary" onClick={() => void action("retry", async () => onUpdate(await api<Template>(`/site-templates/${t.id}/retry`, { method: "POST" })))}><RefreshCcw size={16} />Повторить</button>}</div>}
    {pending && <div className="tg-progress" role="status"><Loader2 className="tg-spin" /><div><strong>{t.phase}</strong><p>Задача сохранена. Можно уйти из раздела и вернуться позже.</p></div></div>}
    {!pending && t.document?.content && <>
      <div className="tg-toolbar"><div className="tg-tabs" role="tablist" aria-label="Шаблон">{tabs.map(([id, label]) => <button role="tab" aria-selected={tab === id} key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</button>)}</div></div>
      {dirty && <div className="tg-save"><span>Есть несохранённые изменения. Предпросмотр показывает сохранённую версию.</span><button disabled={!!busy} className="button primary" onClick={() => void action("save", async () => {
        const result = await api<Template>(`/site-templates/${t.id}`, { method: "PUT", body: JSON.stringify({ revision: t.revision, content: draft, menu }) });
        setDirty(false); onUpdate(result);
      })}>{busy === "save" ? "Сохраняем…" : "Сохранить и проверить"}</button></div>}
      {tab === "preview" && <>
        <div className="tg-preview-toolbar"><div className="tg-device"><button className={!mobile ? "active" : ""} aria-pressed={!mobile} onClick={() => setMobile(false)}><Monitor size={17} />Компьютер</button><button className={mobile ? "active" : ""} aria-pressed={mobile} onClick={() => setMobile(true)}><Smartphone size={17} />Телефон</button></div><div className="tg-downloads"><button className="button secondary" disabled={!!busy || t.status !== "ready" || dirty} onClick={() => void download("html")}><Download size={16} />HTML</button><button className="button secondary" disabled={!!busy || t.status !== "ready" || dirty} onClick={() => void download("images")}><Download size={16} />Изображения ZIP</button><button className="button primary" disabled={!!busy || t.status !== "ready" || dirty} onClick={() => void download("bundle")}><Download size={16} />Весь шаблон</button></div></div>
        <p className="tg-help">Для отдельного HTML распакуйте images.zip рядом с index.html. «Весь шаблон» содержит автономный HTML, настройки и результаты проверок.</p>
        <div className={`tg-preview ${mobile ? "tg-preview-mobile" : ""}`}><iframe title={`Предпросмотр ${t.brand}`} sandbox="" referrerPolicy="no-referrer" srcDoc={t.html || ""} /></div>
        <p className="tg-help">Шаблон сохраняется как черновик с noindex. Перед публикацией потребуются домен и окончательная проверка фактов. Иллюстрация в базовой версии — локальный SVG.</p>
      </>}
      {tab === "content" && draft && <div className="tg-card tg-editor"><h3>Текст и метаданные</h3><label>Title<input value={draft.title} maxLength={250} onChange={e => editContent({ ...draft, title: e.target.value })} /></label><label>Description<textarea value={draft.description} maxLength={600} onChange={e => editContent({ ...draft, description: e.target.value })} /></label><label>Главный заголовок<input value={draft.heading} onChange={e => editContent({ ...draft, heading: e.target.value })} /></label><label>Вступление<textarea rows={4} value={draft.intro} onChange={e => editContent({ ...draft, intro: e.target.value })} /></label>
        {draft.sections.map((section, index) => <details key={section.id} className="tg-options"><summary>{section.title}</summary><label>Заголовок<input value={section.title} onChange={e => editContent({ ...draft, sections: draft.sections.map((s, i) => i === index ? { ...s, title: e.target.value } : s) })} /></label><label>Текст — абзацы через пустую строку<textarea rows={7} value={section.paragraphs.join("\n\n")} onChange={e => editContent({ ...draft, sections: draft.sections.map((s, i) => i === index ? { ...s, paragraphs: e.target.value.split("\n\n") } : s) })} /></label><label>Список — один пункт на строку<textarea rows={4} value={section.bullets.join("\n")} onChange={e => editContent({ ...draft, sections: draft.sections.map((s, i) => i === index ? { ...s, bullets: e.target.value.split("\n") } : s) })} /></label>{section.table.length > 0 && <div className="tg-table-edit">{section.table.map((cells, r) => <div key={r}>{cells.map((cell, c) => <input aria-label={`Таблица: строка ${r + 1}, колонка ${c + 1}`} key={c} value={cell} onChange={e => editContent({ ...draft, sections: draft.sections.map((s, i) => i === index ? { ...s, table: s.table.map((row, ri) => ri === r ? row.map((v, ci) => ci === c ? e.target.value : v) : row) } : s) })} />)}</div>)}</div>}</details>)}
        <details className="tg-options"><summary>FAQ и подвал</summary><label>Заголовок FAQ<input value={draft.faq_title} onChange={e => editContent({ ...draft, faq_title: e.target.value })} /></label>{draft.faq.map((faq, i) => <div key={i}><label>Вопрос {i + 1}<input value={faq.question} onChange={e => editContent({ ...draft, faq: draft.faq.map((f, n) => n === i ? { ...f, question: e.target.value } : f) })} /></label><label>Ответ<textarea value={faq.answer} onChange={e => editContent({ ...draft, faq: draft.faq.map((f, n) => n === i ? { ...f, answer: e.target.value } : f) })} /></label></div>)}<label>Текст подвала<textarea value={draft.footer_text} onChange={e => editContent({ ...draft, footer_text: e.target.value })} /></label></details>
        {!!draft.editorial_notes.length && <div className="tg-note"><strong>Что проверить перед публикацией</strong><ul>{draft.editorial_notes.map((note, i) => <li key={i}>{note}</li>)}</ul></div>}
      </div>}
      {tab === "menu" && <div className="tg-card"><h3>Меню хедера и футера</h3><p>Фейковое меню ведёт к секциям этой страницы. Для реального пункта укажите уже существующий адрес; отдельные страницы здесь не создаются.</p><div className="tg-menu-list">{menu.map((item, i) => <div className="tg-menu-item" key={item.id}><label>Название<input value={item.label} maxLength={100} onChange={e => editMenu(i, { label: e.target.value })} /></label><label>Назначение<select aria-label="Назначение" value={item.mode} onChange={e => editMenu(i, { mode: e.target.value as Menu["mode"] })}><option value="fake">Фейковое → секция</option><option value="real">Реальная ссылка</option></select></label>{item.mode === "real" ? <label>Адрес<input placeholder="/page/ или https://…" value={item.url} onChange={e => editMenu(i, { url: e.target.value })} /></label> : <label>Секция<select value={item.section_id} onChange={e => editMenu(i, { section_id: e.target.value })}>{draft?.sections.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}<option value="faq">FAQ</option></select></label>}<div className="tg-menu-toggles"><label><input type="checkbox" checked={item.header} onChange={e => editMenu(i, { header: e.target.checked })} />Хедер</label><label><input type="checkbox" checked={item.footer} onChange={e => editMenu(i, { footer: e.target.checked })} />Футер</label></div></div>)}</div></div>}
      {tab === "research" && <div className="tg-card"><h3>Анализ конкурентов</h3>{t.document.research ? <><p>Запрос: <strong>{t.document.research.query}</strong></p><div className="tg-sources">{t.document.research.sources.map((s, i) => <a key={i} href={s.url} target="_blank" rel="noopener noreferrer"><span>{s.position}. {s.title || s.url}</span><small>{s.status === "fetched" ? "Прочитан" : "Недоступен"}</small></a>)}</div><div className="tg-analysis">{t.document.research.analysis}</div></> : <p>Этот шаблон создан без сбора выдачи.</p>}</div>}
      {tab === "checks" && <div className="tg-card"><h3>Протокол уникальности</h3><p>{t.request.uniqueness_scope === "global" ? "Проверка по всей истории генератора." : `Сравнение с шаблонами бренда ${t.brand} в ГЕО ${t.geo}.`}</p><p>Максимум 3 совпадения из 15 параметров. Визуальная похожесть — ниже 40/100. Запрещённые сочетания проверяются отдельно.</p>{t.document.design_rationale && <p>{t.document.design_rationale}</p>}<div className="tg-check-results"><p>{t.status === "ready" ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}HTML без JavaScript, структура секций и меню</p><p>{t.status === "ready" ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}Отображение на 1440, 390 и 320 px</p><p>{t.status === "ready" ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}Сравнено шаблонов: {t.document.comparisons?.length || 0}</p></div>{t.document.visual_comparisons?.map(v => <div className="tg-note" key={v.template_id}><strong>{v.score}/100 · {v.passed ? "Проверка пройдена" : "Слишком похоже"}</strong><p>{v.explanation}</p></div>)}<details className="tg-options"><summary>Дизайн-паспорт: 15 параметров</summary><dl className="tg-passport">{Object.entries(t.document.design || {}).map(([key, value]) => <React.Fragment key={key}><dt>{key}</dt><dd>{value}</dd></React.Fragment>)}</dl></details><div className="tg-captures">{Object.entries(t.document.screenshots || {}).map(([key, image]) => <figure key={key}><img src={`data:image/jpeg;base64,${image}`} alt={key.includes("mobile") ? "Проверка мобильной версии" : "Проверка десктопной версии"} /><figcaption>{key.replace("desktop", "Компьютер").replace("mobile", "Телефон").replace("_hero", " · первый экран").replace("_middle", " · середина")}</figcaption></figure>)}</div></div>}
    </>}
  </>;
}
