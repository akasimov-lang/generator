import React from "react";
import { Trash2 } from "lucide-react";

type NetworkOperation = { id: string; action: "reserve" | "reglue" | "alternates" | "create_subdomains" | "delete_domain" | "create_fake_main" | "select_fake_main" | "indexing"; task_id?: string; domains?: string[]; status: string; message: string | null; domain: string | null; initiator: string; created_at: string };
type DomainClassification = { is_subdomain: boolean; parent_domain: string | null; parent_type: "drop" | "newreg" | null; unused_as_main: boolean };
type Network = {
  fake_main_paths?: string[]; fake_main_current?: string; fake_main_enabled?: boolean;
  amp?: string; prev_amp?: string; amp_domains?: string[];
  domain_classification?: Record<string, DomainClassification>;
  domain_types?: Record<string, "drop" | "newreg" | "amp">;
  canon: string; reserve: string; domains: string[]; revision: string;
  main_history: string[]; x_default_history: string[]; alternate_history: string[];
  alternateMarkup: string; enableAlternates: boolean; has_head: boolean;
  alternates: { hreflang: string; href: string; domain: string }[];
  operations: NetworkOperation[];
};
type Props = {
  site: { id: string; name: string }; mode: "network" | "redirects"; username: string;
  api: <T>(path: string, options?: RequestInit) => Promise<T>; onChanged: () => void;
};
type Draft = { markup: string; enabled: boolean; originalMarkup: string; originalEnabled: boolean };
const actionLabels = { select_fake_main: "Выбор текущей фейковой страницы", indexing: "Индексация проекта", create_fake_main: "Создание фейковой главной", delete_domain: "Удаление домена", create_subdomains: "Создание поддоменов", reserve: "Сохранение резерва", reglue: "Переклей", alternates: "Альтернейты" };
const statusLabels: Record<string, string> = { index_queued: "В очереди", index_submitting: "Отправляется", index_submitted: "Задача создана", index_unknown: "Отправка не подтверждена", confirmed: "Подтверждено", pending: "Ожидает подтверждения", unknown: "Результат пока неизвестен", failed: "Ошибка" };
const errorText = (error: unknown) => error instanceof Error ? error.message : "Не удалось выполнить запрос";

export function ProjectNetworkPanel({ site, mode, username, api, onChanged }: Props) {
  const draftKey = `network-alternates:${username}:${site.id}`;
  const [data, setData] = React.useState<Network | null>(null);
  const dataRef = React.useRef<Network | null>(null);
  const [draft, setDraft] = React.useState<Draft | null>(() => {
    try {
      const value = JSON.parse(sessionStorage.getItem(draftKey) || "null");
      return value && typeof value.markup === "string" && typeof value.originalMarkup === "string" && typeof value.enabled === "boolean" && typeof value.originalEnabled === "boolean" ? value : null;
    } catch { return null; }
  });
  const [reserve, setReserve] = React.useState("");
  const [networkView, setNetworkView] = React.useState<"main" | "amp">("main");
  const [onlyFormer, setOnlyFormer] = React.useState(false);
  const [check, setCheck] = React.useState<{ domain: string; reachable: boolean; reason: string } | null>(null);
  const [busy, setBusy] = React.useState("");
  const busyRef = React.useRef(false);
  const [error, setError] = React.useState("");
  const [message, setMessage] = React.useState("");
  const [fakeMainSelection, setFakeMainSelection] = React.useState("");
  const [fakeMainInput, setFakeMainInput] = React.useState("");
  const [subdomainsInput, setSubdomainsInput] = React.useState("");
  const mounted = React.useRef(true);
  const uncertain = data?.operations.some((op) => ["pending", "unknown"].includes(op.status)) || false;
  const dirty = Boolean(draft && (draft.markup !== draft.originalMarkup || draft.enabled !== draft.originalEnabled));
  const conflict = Boolean(data && draft && dirty && (data.alternateMarkup !== draft.originalMarkup || data.enableAlternates !== draft.originalEnabled));

  function accept(next: Network) {
    if (!mounted.current) return;
    dataRef.current = next;
    setData(next);
    setFakeMainSelection(next.fake_main_current || "");
    setReserve((old) => old && next.domains.includes(old) && old !== next.canon ? old : next.reserve);
    setDraft((old) => old && (old.markup !== old.originalMarkup || old.enabled !== old.originalEnabled) && (old.markup !== next.alternateMarkup || old.enabled !== next.enableAlternates) ? old : {
      markup: next.alternateMarkup, enabled: next.enableAlternates,
      originalMarkup: next.alternateMarkup, originalEnabled: next.enableAlternates,
    });
  }
  async function load(force = true) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy("refresh"); setError("");
    try {
      const next = await api<Network>(`/sites/${site.id}/network${force ? "?refresh=true" : ""}`, force ? { cache: "no-store" } : undefined);
      const previous = dataRef.current;
      accept(next);
      if (mounted.current && previous && (previous.revision !== next.revision || JSON.stringify(previous.operations) !== JSON.stringify(next.operations))) onChanged();
    }
    catch (err) { if (mounted.current) setError(errorText(err)); }
    finally { busyRef.current = false; if (mounted.current) setBusy(""); }
  }
  React.useEffect(() => {
    mounted.current = true;
    setNetworkView("main");
    void load(false);
    return () => { mounted.current = false; };
  }, [site.id]);
  React.useEffect(() => {
    if (draft) sessionStorage.setItem(draftKey, JSON.stringify(draft));
  }, [draft, draftKey]);
  React.useEffect(() => {
    if (!uncertain) return;
    const timer = window.setInterval(() => { void load(); }, 10000);
    return () => window.clearInterval(timer);
  }, [uncertain]);

  const indexingPending = data?.operations.some(op => ["index_queued", "index_submitting"].includes(op.status));
  React.useEffect(() => {
    if (!indexingPending) return;
    let alive = true, fetching = false;
    const timer = window.setInterval(async () => {
      if (fetching) return;
      fetching = true;
      try {
        const operations = await api<NetworkOperation[]>(`/sites/${site.id}/network/operations`);
        if (alive && mounted.current && dataRef.current) {
          const next = { ...dataRef.current, operations };
          dataRef.current = next; setData(next);
        }
      } catch { /* Keep the saved history; retry only the local database read. */ }
      finally { fetching = false; }
    }, 5000);
    return () => { alive = false; window.clearInterval(timer); };
  }, [indexingPending, site.id, api]);

  const subdomains = [...new Set(subdomainsInput.toLowerCase().split(/[\s,;]+/).map((value) => value.trim().replace(/\.$/, "")).filter(Boolean))];
  const subdomainErrors = subdomains.flatMap((domain) => {
    if (domain.length > 253 || !domain.split(".").every((label) => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) return [domain + ": некорректное имя"];
    if (data?.domains.includes(domain)) return [domain + ": уже есть в сетке"];
    if (!data?.domains.some((parent) => domain.endsWith("." + parent.replace(/^www\./, "")) && domain !== "www." + parent.replace(/^www\./, ""))) return [domain + ": родительского домена нет в сетке"];
    return [];
  });
  async function mutate(action: Exclude<NetworkOperation["action"], "indexing">, targetDomain?: string) {
    if (!data || !draft || busyRef.current) return;
    busyRef.current = true; setBusy(action); setError(""); setMessage("");
    const payload = { action, fake_main_path: action === "select_fake_main" ? fakeMainSelection : fakeMainInput, revision: data.revision, domain: targetDomain || reserve, alternate_markup: draft.markup, enable_alternates: draft.enabled, ...(action === "create_subdomains" ? { domains: subdomains } : {}) };
    const receiptKey = `network-request:${username}:${site.id}`;
    let requestId = crypto.randomUUID();
    try {
      const previous = JSON.parse(sessionStorage.getItem(receiptKey) || "null");
      if (previous?.fingerprint === JSON.stringify(payload)) requestId = previous.id;
    } catch { /* An invalid draft receipt can safely be replaced. */ }
    sessionStorage.setItem(receiptKey, JSON.stringify({ id: requestId, fingerprint: JSON.stringify(payload) }));
    try {
      const next = await api<Network>(`/sites/${site.id}/network/operations`, { method: "POST", body: JSON.stringify({ ...payload, request_id: requestId }) });
      if (!mounted.current) return;
      accept(next);
      const operation = next.operations.find((op) => op.id === requestId);
      if (action === "create_subdomains" && operation && operation.status !== "failed") setSubdomainsInput("");
      if (operation?.status === "confirmed") {
        if (action === "alternates") setDraft({ markup: next.alternateMarkup, enabled: next.enableAlternates, originalMarkup: next.alternateMarkup, originalEnabled: next.enableAlternates });
        setMessage(`${actionLabels[action]}: подтверждено.`);
        sessionStorage.removeItem(receiptKey);
        onChanged();
      } else if (operation?.status === "failed") { setError(operation.message || "Webdev сообщил об ошибке."); sessionStorage.removeItem(receiptKey); }
      else setMessage(operation?.message || "Запрос отправлен. Ожидается подтверждение.");
      setCheck(null);
    } catch (err) { if (mounted.current) setError(`${errorText(err)} Обновите данные перед повторной отправкой.`); }
    finally { busyRef.current = false; if (mounted.current) setBusy(""); }
  }
  async function saveDomainType(domain: string, domainType: string) {
    if (!data || busyRef.current) return;
    busyRef.current = true; setBusy("domain-type"); setError("");
    try {
      const saved = await api<{ domain_types: Record<string, "drop" | "newreg">; domain_classification?: Record<string, DomainClassification> }>(`/sites/${site.id}/network/domain-type`, {
        method: "PATCH", body: JSON.stringify({ domain, domain_type: domainType }),
      });
      if (!mounted.current) return;
      const next = { ...dataRef.current!, domain_types: saved.domain_types, domain_classification: saved.domain_classification };
      dataRef.current = next; setData(next);
    } catch (err) { if (mounted.current) setError(errorText(err)); }
    finally { busyRef.current = false; if (mounted.current) setBusy(""); }
  }
  async function checkReserve() {
    if (!data || !reserve || busyRef.current) return;
    busyRef.current = true; setBusy("check"); setError(""); setCheck(null);
    try {
      const value = await api<{ domain: string; reachable: boolean; reason: string }>(`/sites/${site.id}/network/check-domain`, { method: "POST", body: JSON.stringify({ domain: reserve, revision: data.revision }) });
      if (mounted.current) setCheck(value);
    } catch (err) { if (mounted.current) setError(errorText(err)); }
    finally { busyRef.current = false; if (mounted.current) setBusy(""); }
  }
  const known = data ? [...new Set([...data.domains, ...(data.amp_domains || []), data.canon, ...data.main_history, ...data.alternate_history])].filter(Boolean) : [];
  const ampDomains = new Set(data?.amp_domains || []);
  const visibleDomains = known.filter((domain) => networkView === "amp" ? ampDomains.has(domain) : !ampDomains.has(domain));
  const disabled = Boolean(busy) || uncertain;
  const reserveValid = Boolean(data && reserve && reserve !== data.canon && data.domains.includes(reserve) && !ampDomains.has(reserve));
  return <section className="dataPanel projectNetworkPanel">
    <div className="panelHeader"><h2>{mode === "network" ? "Сетка проекта" : "Переклей"}</h2>
      <button type="button" className="button secondary compact" disabled={Boolean(busy)} onClick={() => void load()}>{busy === "refresh" ? "Обновляем…" : "Обновить данные"}</button>
    </div>
    <div className="dataPanelBody">
      {error && <div className="notice" role="alert">{error}</div>}
      {message && <p role="status">{message}</p>}
      {!data && <p>{busy ? "Загружаем сетку проекта…" : "Данные сетки недоступны. Повторите загрузку."}</p>}
      {data && <>
        {mode === "network" && <div className="networkViewSwitch" role="group" aria-label="Вид сетки">
          <button type="button" aria-pressed={networkView === "main"} onClick={() => setNetworkView("main")}>Основная сетка</button>
          <button type="button" aria-pressed={networkView === "amp"} onClick={() => setNetworkView("amp")}>Ампы</button>
        </div>}
        {mode === "network" && networkView === "amp" ? <p>Текущий AMP: <strong>{data.amp || "не задан"}</strong> · Предыдущий AMP: <strong>{data.prev_amp || "не задан"}</strong></p> : <p>Текущий Main: <strong>{data.canon || "не задан"}</strong> · Резерв: <strong>{data.reserve || "не выбран"}</strong></p>}
        {uncertain && <div className="notice" role="status">Проверяем результат отправленной операции. Новые изменения станут доступны после подтверждения. Запрос на изменение повторно не отправляется.</div>}
        {mode === "network" && <>
          <div className="networkTableWrap" tabIndex={0} role="region" aria-label="Домены сетки"><table className="networkTable"><thead><tr><th scope="col">Домен</th><th scope="col">Тип домена</th><th scope="col">Поддомен</th><th scope="col">Статус</th><th scope="col">Был Main</th><th scope="col">Был в альтернейтах</th><th scope="col">x-default</th><th scope="col">Действия</th></tr></thead>
            <tbody>{visibleDomains.map((domain) => <tr key={domain}><td data-label="Домен">{domain}</td><td data-label="Тип домена">{ampDomains.has(domain) ? <span className="networkAmpType">AMP</span> : data.domain_classification?.[domain]?.is_subdomain ? <span title="Тип задаётся у родительского домена">{data.domain_classification[domain].parent_type === "drop" ? "Дроп (родитель)" : data.domain_classification[domain].parent_type === "newreg" ? "Новорег (родитель)" : "Не указан у родителя"}</span> : <select className="networkDomainType" aria-label={`Тип домена ${domain}`} value={data.domain_types?.[domain] || ""} disabled={Boolean(busy)} onChange={(event) => void saveDomainType(domain, event.target.value)}><option value="" disabled>Не указан</option><option value="drop">Дроп</option><option value="newreg">Новорег</option></select>}</td><td data-label="Поддомен">
                <span className="networkSubdomain"><input type="checkbox" className="networkHistoryCheck" disabled checked={!!data.domain_classification?.[domain]?.is_subdomain} aria-label={domain + ": поддомен"} />
                {data.domain_classification?.[domain]?.is_subdomain && <span title={"Родитель: " + data.domain_classification[domain].parent_domain}>
                  {data.domain_classification[domain].parent_type === "drop" ? "Поддомен дропа" : data.domain_classification[domain].parent_type === "newreg" ? "Поддомен новорега" : "Тип родителя не указан"}
                  {data.domain_classification[domain].unused_as_main && <small>Не был Main</small>}
                </span>}</span>
              </td><td data-label="Статус">{networkView === "amp" && domain === data.amp ? "Текущий AMP" : networkView === "amp" && domain === data.prev_amp ? "Предыдущий AMP" : domain === data.canon ? "Main" : domain === data.reserve ? "Резерв" : data.domains.includes(domain) ? "В сетке" : "В истории"}</td>
              {[data.main_history, data.alternate_history, data.x_default_history].map((history, i) => <td key={i} data-label={["Был Main", "Был в альтернейтах", "x-default"][i]}><input type="checkbox" className="networkHistoryCheck" disabled checked={history.includes(domain)} aria-label={`${domain}: ${["был Main", "был в альтернейтах", "x-default"][i]}`} /></td>)}
              <td data-label="Действия"><button type="button" className="networkDeleteButton" aria-label={`Удалить ${domain} из сетки`}
                title={domain === data.canon || domain === data.reserve || domain === site.name || domain === data.amp ? "Домен проекта, Main, AMP и резерв защищены от удаления" : "Удалить домен из сетки"}
                disabled={disabled || !data.domains.includes(domain) || [data.canon, data.reserve, site.name, data.amp].includes(domain)}
                onClick={() => void mutate("delete_domain", domain)}><Trash2 size={15} /></button></td>
            </tr>)}</tbody>
          </table></div>
          {!visibleDomains.length && <p>{networkView === "amp" ? "В кеше проекта AMP-домены не указаны." : "В основной сетке нет доменов."}</p>}
          {networkView === "main" && <div className="networkSection">
            <h3>Создание поддоменов</h3>
            <p>Укажите полные имена через запятую, пробел или новую строку. Родительский домен должен быть в сохранённой сетке проекта.</p>
            <label>Поддомены<textarea aria-label="Поддомены" rows={3} value={subdomainsInput} disabled={disabled} placeholder="test1.example.com, test2.example.com" onChange={(event) => setSubdomainsInput(event.target.value)} /></label>
            {subdomains.length > 0 && <><p>Будет создано: {subdomains.length}</p><ul>{subdomains.map((domain) => <li key={domain}>{domain}</li>)}</ul></>}
            {!!subdomainErrors.length && <div className="notice" role="alert">{subdomainErrors.map((text) => <p key={text}>{text}</p>)}</div>}
            {subdomains.length > 100 && <p role="alert">За один запуск можно создать до 100 поддоменов.</p>}
            <button type="button" className="button" disabled={disabled || !subdomains.length || subdomains.length > 100 || !!subdomainErrors.length} onClick={() => void mutate("create_subdomains")}>{busy === "create_subdomains" ? "Запускаем создание…" : "Создать конфиги"}</button>
            <p className="muted">Перед запуском сервер проверит домены по нашей базе и актуальной сетке Webdev. Поддомены добавятся в сетку автоматически; появление в списке ещё не подтверждает готовность HTTPS.</p>
          </div>}
        </>}
        {mode === "redirects" && <div className="networkSection">
          <h3>Резервный домен</h3>
          <label><input type="checkbox" checked={onlyFormer} onChange={(event) => setOnlyFormer(event.target.checked)} /> Показывать только бывшие Main в сетке</label>
          <label>Домен для переклея<select aria-label="Домен для переклея" value={reserve} disabled={disabled} onChange={(event) => { setReserve(event.target.value); setCheck(null); }}>
            <option value="">Выберите резервный домен</option>
            {data.domains.filter((domain) => !ampDomains.has(domain) && domain !== data.canon && (!onlyFormer || data.main_history.includes(domain) || domain === reserve)).map((domain) => <option key={domain} value={domain}>{domain}{data.main_history.includes(domain) ? " — был Main" : ""}</option>)}
          </select></label>
          <div className="networkActions">
            <button type="button" className="button secondary" disabled={disabled || !reserveValid || reserve === data.reserve} onClick={() => void mutate("reserve")}>{busy === "reserve" ? "Сохраняем…" : "Сохранить резерв"}</button>
            <button type="button" className="button secondary" disabled={disabled || !reserveValid || reserve !== data.reserve} onClick={() => void checkReserve()}>{busy === "check" ? "Проверяем…" : "Проверить домен"}</button>
          </div>
          {check && <p role="status">{check.reachable ? "Домен доступен" : `Домен недоступен: ${check.reason || "нет ответа"}`}</p>}
          <p className="muted">Ручной переклей на сохранённый резерв. Проверка домена необязательна; автопереклей и его расписание не запускаются.</p>
          {reserveValid && <p>Смена canonical: <strong>{data.canon}</strong> → <strong>{reserve}</strong></p>}
          {dirty && <p>В альтернейтах есть несохранённые изменения. Сохраните их перед запуском переклея.</p>}
          <button type="button" className="button primary compact networkReglueButton" disabled={disabled || dirty || !reserveValid || reserve !== data.reserve} onClick={() => void mutate("reglue")}>{busy === "reglue" ? "Запускаем переклей…" : "Переклеить на резервный домен"}</button>
        </div>}
        {draft && (mode !== "network" || networkView === "main") && <div className="networkSection">
          <h3>Альтернейты</h3>
          <label><input type="checkbox" checked={draft.enabled} disabled={disabled || !data.has_head} onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })} /> Включить альтернейты</label>
          <label>Альтернейты<textarea aria-label="Альтернейты" className="networkMarkup" rows={8} spellCheck={false} value={draft.markup} disabled={disabled || !data.has_head} onChange={(event) => setDraft({ ...draft, markup: event.target.value })} placeholder={'<link rel="alternate" hreflang="x-default" href="https://example.com/" />'} /></label>
          {!data.has_head && <p>Настройки head не получены. Редактирование недоступно.</p>}
          {conflict && <div className="notice">Разметка в Webdev изменилась, пока вы редактировали её. Скопируйте нужные правки и загрузите актуальный вариант кнопкой ниже.</div>}
          <p role="status" className={dirty ? "notice" : "muted"}>
            {busy === "alternates" ? "Отправляем альтернейты на сервер проекта…"
              : data.operations.some((op) => op.action === "alternates" && ["pending", "unknown"].includes(op.status))
                ? "Запрос отправлен. Ожидаем подтверждения синхронизации с сервером проекта."
              : dirty ? "Изменения не синхронизированы. Нажмите «Сохранить альтернейты», чтобы отправить данные на сервер проекта."
              : "Локальных изменений нет. Разметка соответствует последним полученным данным проекта."}
          </p>
          <div className="networkActions">
            <button type="button" className="button" disabled={disabled || !dirty || conflict || !data.has_head} onClick={() => void mutate("alternates")}>{busy === "alternates" ? "Сохраняем…" : "Сохранить альтернейты"}</button>
            <button type="button" className="button secondary" disabled={Boolean(busy) || !dirty} onClick={() => setDraft({ markup: data.alternateMarkup, enabled: data.enableAlternates, originalMarkup: data.alternateMarkup, originalEnabled: data.enableAlternates })}>Загрузить актуальную разметку</button>
          </div>
        </div>}
        {(mode !== "network" || networkView === "main") && <div className="networkSection"><h3>Фейковые внутренние страницы</h3>
          <p>Динамические страницы: <b>{data.fake_main_enabled ? "включены" : "выключены"}</b>.</p>
          {!!data.fake_main_paths?.length ? <ul>{data.fake_main_paths.map(path => <li key={path}><a href={`https://${data.canon}${path}`} target="_blank" rel="noreferrer">{path}</a>{path === data.fake_main_current ? " — текущая" : ""}</li>)}</ul> : <p className="muted">В кеше нет фейковых внутренних страниц.</p>}
          {!!data.fake_main_paths?.length && <div className="networkFakeCurrent">
            <label>Текущая фейковая страница
              <select aria-label="Текущая фейковая страница" value={fakeMainSelection} onChange={event => setFakeMainSelection(event.target.value)} disabled={disabled}>
                <option value="" disabled>Выберите страницу</option>
                {data.fake_main_paths.map(path => <option key={path} value={path}>{path}</option>)}
              </select>
            </label>
            <button type="button" className="button compact secondary" disabled={disabled || !fakeMainSelection || fakeMainSelection === data.fake_main_current} onClick={() => void mutate("select_fake_main")}>{busy === "select_fake_main" ? "Сохраняем…" : "Сохранить текущую страницу"}</button>
          </div>}
          <label>Путь фейковой главной<input aria-label="Путь фейковой главной" value={fakeMainInput} onChange={e => setFakeMainInput(e.target.value)} disabled={disabled} placeholder="test1 или /events/" /></label>
          <div className="networkActions"><button type="button" className="button compact secondary" disabled={disabled || !fakeMainInput.trim() || !!data.fake_main_paths?.includes("/" + fakeMainInput.trim().replace(/^\/+|\/+$/g, "") + "/")} onClick={() => void mutate("create_fake_main")}>{busy === "create_fake_main" ? "Создаём…" : "Создать фейковую главную"}</button></div>
        </div>}
        {!!data.operations.length && <div className="networkSection"><h3>История операций</h3><ul className="networkOperations">{data.operations.map((operation) => <li key={operation.id}>
          <strong>{actionLabels[operation.action]}{operation.domain ? `: ${operation.domain}` : ""}</strong> — {statusLabels[operation.status] || operation.status}
          <small>{new Date(operation.created_at).toLocaleString("ru-RU")} · {operation.initiator}</small><p>{operation.message}</p>
          {operation.action === "indexing" && <>{operation.task_id && <p>Номер задачи: <strong>{operation.task_id}</strong></p>}<details><summary>Домены для индексации ({operation.domains?.length || 0})</summary><ul>{operation.domains?.map(domain => <li key={domain}>{domain}</li>)}</ul></details></>}
        </li>)}</ul></div>}
      </>}
    </div>
  </section>;
}
