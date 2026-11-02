import React from "react";
import { TransferProgress, type TransferRun } from "./TransferProgress";
import type { MassActionFilter } from "./massActionScope";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type Run = TransferRun & {site_id:string};
type Receipt = { id: string; signature: string; target?: string; group?: string };
const active = ["planned", "queued", "running", "waiting", "partial"];
const labels: Record<string, string> = { queued: "В очереди", running: "Переносим", waiting: "Проверяем результат", partial: "Нужна проверка", completed: "Перенесено", failed: "Ошибка", cancelled: "Остановлен" };

export function NetworkMoveButtons({ api, filter, siteIds, onChanged }: { api: Api; filter: MassActionFilter; siteIds: string[]; onChanged: () => void | Promise<void> }) {
  const key = `network-move:${filter.brand}:${filter.geo}:${filter.site_type || "all"}`;
  const [receipt, setReceipt] = React.useState<Receipt | null>(() => {
    try { return JSON.parse(sessionStorage.getItem(key) || "null"); } catch { return null; }
  });
  const [runs, setRuns] = React.useState<Run[]>([]);
  const run=runs[0];
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const onChangedRef = React.useRef(onChanged); onChangedRef.current = onChanged;
  const refreshed = React.useRef("");
  const starting = React.useRef(false);
  const saveReceipt = (value: Receipt | null) => {
    try {
      if (value) sessionStorage.setItem(key, JSON.stringify(value));
      else sessionStorage.removeItem(key);
    } catch {
      if(value&&!value.target)throw new Error("Не удалось сохранить параметры переноса. Разрешите хранение данных вкладки и повторите запуск.");
    }
    setReceipt(value);
  };
  React.useEffect(() => {
    if (!receipt?.target) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const data = await api<{ runs: Run[] }>(receipt.group ? "/auto-reglue" : `/auto-reglue?project_id=${encodeURIComponent(receipt.target!)}`);
        const nextRuns=data.runs.filter(item=>receipt.group?item.plan.batch_id===receipt.group:item.id===receipt.id);
        const next=nextRuns[0];
        if (cancelled || !next) return;
        setRuns(nextRuns); setError("");
        const stamp=JSON.stringify(nextRuns.map(item=>[item.id,item.status,item.phase,item.domain_progress?.map(d=>d.stage)]));
        if(refreshed.current!==stamp){refreshed.current=stamp;await onChangedRef.current();}
        if (nextRuns.every(item=>!active.includes(item.status) && !item.plan.replacement_pending)) {
          saveReceipt(null);

        }
      } catch (e) { if (!cancelled) setError(e instanceof Error ? e.message : "Не удалось проверить перенос"); }
    };
    void poll();
    const timer = setInterval(() => void poll(), 2000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [api, receipt?.id, receipt?.target, receipt?.group]);
  async function move(count: 1 | 2) {
    if(starting.current||receipt?.target)return;
    const payload = { filter, site_ids: [...siteIds].sort(), count };
    const signature = JSON.stringify(payload);
    // An uncertain response is retried with the same id, including after reload.
    const intent = receipt || { id: crypto.randomUUID(), signature };
    if (intent.signature !== signature) { setError("Сначала повторите неподтверждённый запрос с прежней выборкой и числом доменов."); return; }
    starting.current=true;setBusy(true); setError(""); setRuns([]);
    try {
      saveReceipt(intent);
      const next = await api<Run & {runs?:Run[]}>("/auto-reglue/move-plus2", { method: "POST", body: JSON.stringify({ ...payload, request_id: intent.id }) });
      setRuns(next.runs||[next]); saveReceipt({ ...intent, target: next.site_id,group:next.plan.batch_id });
    } catch (e) {
      const status = (e as { statusCode?: number })?.statusCode;
      if (status && status >= 400 && status < 500 && status !== 408) saveReceipt(null);
      setError(e instanceof Error ? e.message : "Не удалось запустить перенос");
    }
    finally { starting.current=false;setBusy(false); }
  }
  return <span style={{ display: "inline-flex", alignItems: "center", flexWrap: "wrap", gap: 6, fontSize: 12, fontWeight: 400 }} aria-label="Перенос новорегов">
    {([2, 1] as const).map(count => <button key={count} className="button secondary compact" type="button" disabled={busy || !!receipt?.target || siteIds.length < 2} title={`Перенести ${count} новорега в меньшую сетку без смены Main`} onClick={() => void move(count)}>Move +{count}</button>)}
    {run && <a className="textLink" href={`/project-auto-reglue/${encodeURIComponent(run.plan.project)}/`} title="История переноса и откат">История</a>}
    <TransferProgress runs={runs} />
    {error && <span role="alert">{error}</span>}
  </span>;
}
