import React from "react";

type NetworkOperation = { id: string; action: "reserve" | "reglue" | "alternates"; status: string; message: string | null; domain: string | null; initiator: string; created_at: string };
type Network = {
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
const actionLabels = { reserve: "Сохранение резерва", reglue: "Переклей", alternates: "Альтернейты" };
const statusLabels: Record<string, string> = { confirmed: "Подтверждено", pending: "Ожидает подтверждения", unknown: "Результат пока неизвестен", failed: "Ошибка" };
const errorText = (error: unknown) => error instanceof Error ? error.message : "Не удалось выполнить запрос";
const escapeAttribute = (value: string) => value.replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");

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
  const [onlyFormer, setOnlyFormer] = React.useState(false);
  const [check, setCheck] = React.useState<{ domain: string; reachable: boolean; reason: string } | null>(null);
  const [busy, setBusy] = React.useState("");
  const busyRef = React.useRef(false);
  const [error, setError] = React.useState("");
  const [message, setMessage] = React.useState("");
  const [newLang, setNewLang] = React.useState("x-default");
  const [newUrl, setNewUrl] = React.useState("");
  const [formerMain, setFormerMain] = React.useState("");
  const mounted = React.useRef(true);
  const uncertain = data?.operations.some((op) => ["pending", "unknown"].includes(op.status)) || false;
  const dirty = Boolean(draft && (draft.markup !== draft.originalMarkup || draft.enabled !== draft.originalEnabled));
  const conflict = Boolean(data && draft && dirty && (data.alternateMarkup !== draft.originalMarkup || data.enableAlternates !== draft.originalEnabled));

  function accept(next: Network) {
    if (!mounted.current) return;
    dataRef.current = next;
    setData(next);
    setReserve((old) => old && next.domains.includes(old) && old !== next.canon ? old : next.reserve);
    setDraft((old) => old && (old.markup !== old.originalMarkup || old.enabled !== old.originalEnabled) && (old.markup !== next.alternateMarkup || old.enabled !== next.enableAlternates) ? old : {
      markup: next.alternateMarkup, enabled: next.enableAlternates,
      originalMarkup: next.alternateMarkup, originalEnabled: next.enableAlternates,
    });
  }
  async function load() {
    if (busyRef.current) return;
    busyRef.current = true; setBusy("refresh"); setError("");
    try {
      const next = await api<Network>(`/sites/${site.id}/network`);
      const previous = dataRef.current;
      accept(next);
      if (mounted.current && (!previous || previous.revision !== next.revision || JSON.stringify(previous.operations) !== JSON.stringify(next.operations))) onChanged();
    }
    catch (err) { if (mounted.current) setError(errorText(err)); }
    finally { busyRef.current = false; if (mounted.current) setBusy(""); }
  }
  React.useEffect(() => {
    mounted.current = true;
    void load();
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

  async function mutate(action: NetworkOperation["action"]) {
    if (!data || !draft || busyRef.current) return;
    busyRef.current = true; setBusy(action); setError(""); setMessage("");
    const payload = { action, revision: data.revision, domain: reserve, alternate_markup: draft.markup, enable_alternates: draft.enabled };
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
  async function checkReserve() {
    if (!data || !reserve || busyRef.current) return;
    busyRef.current = true; setBusy("check"); setError(""); setCheck(null);
    try {
      const value = await api<{ domain: string; reachable: boolean; reason: string }>(`/sites/${site.id}/network/check-domain`, { method: "POST", body: JSON.stringify({ domain: reserve, revision: data.revision }) });
      if (mounted.current) setCheck(value);
    } catch (err) { if (mounted.current) setError(errorText(err)); }
    finally { busyRef.current = false; if (mounted.current) setBusy(""); }
  }
  function addAlternate() {
    if (!draft) return;
    try {
      const url = new URL(newUrl.trim());
      if (!["https:", "http:"].includes(url.protocol) || url.username || url.password || !/^[A-Za-z0-9-]+$/.test(newLang.trim())) throw new Error("Укажите hreflang и полный HTTP(S)-адрес.");
      const parsed = new DOMParser().parseFromString(draft.markup, "text/html");
      if ([...parsed.querySelectorAll('link[hreflang]')].some((link) => link.getAttribute("hreflang")?.toLowerCase() === newLang.trim().toLowerCase())) throw new Error("Этот hreflang уже есть. Измените его адрес в поле «Альтернейты».");
      const line = `<link rel="alternate" hreflang="${escapeAttribute(newLang.trim())}" href="${escapeAttribute(url.href)}" />`;
      setDraft({ ...draft, markup: `${draft.markup}${draft.markup.endsWith("\n") || !draft.markup ? "" : "\n"}${line}` });
      setNewUrl(""); setError("");
    } catch (err) { setError(errorText(err)); }
  }

  const known = data ? [...new Set([...data.domains, data.canon, ...data.main_history, ...data.alternate_history])].filter(Boolean) : [];
  const disabled = Boolean(busy) || uncertain;
  const reserveValid = Boolean(data && reserve && reserve !== data.canon && data.domains.includes(reserve));
  return <section className="dataPanel projectNetworkPanel">
    <div className="panelHeader"><h2>{mode === "network" ? "Сетка проекта" : "Переклей"}</h2>
      <button type="button" className="button secondary compact" disabled={Boolean(busy)} onClick={() => void load()}>{busy === "refresh" ? "Обновляем…" : "Обновить данные"}</button>
    </div>
    <div className="dataPanelBody">
      {error && <div className="notice" role="alert">{error}</div>}
      {message && <p role="status">{message}</p>}
      {!data && <p>{busy ? "Загружаем сетку проекта…" : "Данные сетки недоступны. Повторите загрузку."}</p>}
      {data && <>
        <p>Текущий Main: <strong>{data.canon || "не задан"}</strong> · Резерв: <strong>{data.reserve || "не выбран"}</strong></p>
        {uncertain && <div className="notice" role="status">Проверяем результат отправленной операции. Новые изменения станут доступны после подтверждения. Запрос на изменение повторно не отправляется.</div>}
        {mode === "network" && <>
          <p>Отметки истории сохраняются после смены домена. x-default означает, что домен был указан в альтернейте с hreflang="x-default".</p>
          <div className="networkTableWrap" tabIndex={0} role="region" aria-label="Домены сетки"><table className="networkTable"><thead><tr><th scope="col">Домен</th><th scope="col">Статус</th><th scope="col">Был Main</th><th scope="col">Был в альтернейтах</th><th scope="col">x-default</th></tr></thead>
            <tbody>{known.map((domain) => <tr key={domain}><td data-label="Домен">{domain}</td><td data-label="Статус">{domain === data.canon ? "Main" : domain === data.reserve ? "Резерв" : data.domains.includes(domain) ? "В сетке" : "В истории"}</td>
              {[data.main_history, data.alternate_history, data.x_default_history].map((history, i) => <td key={i} data-label={["Был Main", "Был в альтернейтах", "x-default"][i]}><input type="checkbox" className="networkHistoryCheck" disabled checked={history.includes(domain)} aria-label={`${domain}: ${["был Main", "был в альтернейтах", "x-default"][i]}`} /></td>)}</tr>)}</tbody>
          </table></div>
        </>}
        {mode === "redirects" && <div className="networkSection">
          <h3>Резервный домен</h3>
          <label><input type="checkbox" checked={onlyFormer} onChange={(event) => setOnlyFormer(event.target.checked)} /> Показывать только бывшие Main в сетке</label>
          <label>Домен для переклея<select aria-label="Домен для переклея" value={reserve} disabled={disabled} onChange={(event) => { setReserve(event.target.value); setCheck(null); }}>
            <option value="">Выберите резервный домен</option>
            {data.domains.filter((domain) => domain !== data.canon && (!onlyFormer || data.main_history.includes(domain) || domain === reserve)).map((domain) => <option key={domain} value={domain}>{domain}{data.main_history.includes(domain) ? " — был Main" : ""}</option>)}
          </select></label>
          <div className="networkActions">
            <button type="button" className="button secondary" disabled={disabled || !reserveValid || reserve === data.reserve} onClick={() => void mutate("reserve")}>{busy === "reserve" ? "Сохраняем…" : "Сохранить резерв"}</button>
            <button type="button" className="button secondary" disabled={disabled || !reserveValid || reserve !== data.reserve} onClick={() => void checkReserve()}>{busy === "check" ? "Проверяем…" : "Проверить домен"}</button>
          </div>
          {check && <p role="status">{check.reachable ? "Домен доступен" : `Домен недоступен: ${check.reason || "нет ответа"}`}</p>}
          {reserveValid && <p>Смена canonical: <strong>{data.canon}</strong> → <strong>{reserve}</strong></p>}
          {dirty && <p>В альтернейтах есть несохранённые изменения. Сохраните их перед запуском переклея.</p>}
          <button type="button" className="button" disabled={disabled || dirty || !reserveValid || reserve !== data.reserve || check?.domain !== reserve || !check.reachable} onClick={() => void mutate("reglue")}>{busy === "reglue" ? "Запускаем переклей…" : "Переклеить на резервный домен"}</button>
        </div>}
        {draft && <div className="networkSection">
          <h3>Альтернейты</h3>
          <p>Разметка сохраняется отдельно. При переклее canonical меняется через выбранный резерв.</p>
          <label><input type="checkbox" checked={draft.enabled} disabled={disabled || !data.has_head} onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })} /> Включить альтернейты</label>
          <label>Альтернейты<textarea aria-label="Альтернейты" className="networkMarkup" rows={8} spellCheck={false} value={draft.markup} disabled={disabled || !data.has_head} onChange={(event) => setDraft({ ...draft, markup: event.target.value })} placeholder={'<link rel="alternate" hreflang="x-default" href="https://example.com/" />'} /></label>
          {!data.has_head && <p>Настройки head не получены. Редактирование недоступно.</p>}
          {conflict && <div className="notice">Разметка в Webdev изменилась, пока вы редактировали её. Скопируйте нужные правки и загрузите актуальный вариант кнопкой ниже.</div>}
          <details><summary>Добавить ссылку в альтернейты</summary><div className="networkAlternateBuilder">
            <label>Бывший Main<select value={formerMain} onChange={(event) => { setFormerMain(event.target.value); if (event.target.value) setNewUrl(`https://${event.target.value}/`); }}><option value="">Выбрать из истории</option>{data.main_history.filter((domain) => domain !== data.canon).map((domain) => <option key={domain}>{domain}</option>)}</select></label>
            <label>hreflang<input value={newLang} onChange={(event) => setNewLang(event.target.value)} placeholder="x-default" /></label>
            <label>Адрес<input type="url" value={newUrl} onChange={(event) => setNewUrl(event.target.value)} placeholder="https://example.com/" /></label>
            <button className="button secondary" type="button" disabled={disabled || !data.has_head} onClick={addAlternate}>Добавить в разметку</button>
          </div></details>
          <div className="networkActions">
            <button type="button" className="button" disabled={disabled || !dirty || conflict || !data.has_head} onClick={() => void mutate("alternates")}>{busy === "alternates" ? "Сохраняем…" : "Сохранить альтернейты"}</button>
            <button type="button" className="button secondary" disabled={Boolean(busy) || !dirty} onClick={() => setDraft({ markup: data.alternateMarkup, enabled: data.enableAlternates, originalMarkup: data.alternateMarkup, originalEnabled: data.enableAlternates })}>Загрузить актуальную разметку</button>
          </div>
        </div>}
        {!!data.operations.length && <div className="networkSection"><h3>История операций</h3><ul className="networkOperations">{data.operations.map((operation) => <li key={operation.id}>
          <strong>{actionLabels[operation.action]}{operation.domain ? `: ${operation.domain}` : ""}</strong> — {statusLabels[operation.status] || operation.status}
          <small>{new Date(operation.created_at).toLocaleString("ru-RU")} · {operation.initiator}</small><p>{operation.message}</p>
        </li>)}</ul></div>}
      </>}
    </div>
  </section>;
}
