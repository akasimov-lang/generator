import React from "react";
import { CheckCircle2, Store } from "lucide-react";
import { PROJECT_CHANGED_EVENT, projectNotice } from "./projectNotificationEvents";

export type ProjectContentStatus = { complete: boolean; internal_count: number; linked_from_home: number; linked_to_home: number; message: string; warning?: string | null; showcase?: { count: number; brands: string[]; message?: string } };
type Api = <T>(path: string, options?: RequestInit) => Promise<T>;

export function ProjectInterlinking({ siteId, api, refreshToken, generalSite = false, onStatus, onShowcaseClick }: { siteId: string; api: Api; refreshToken: number; generalSite?: boolean; onStatus?: (siteId: string, status: ProjectContentStatus | null) => void; onShowcaseClick?: () => void }) {
  const [status, setStatus] = React.useState<ProjectContentStatus | null>(null);
  const publishStatus = React.useRef(onStatus); publishStatus.current = onStatus;
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [request, setRequest] = React.useState(0);
  React.useEffect(() => {
    let timer: number | undefined;
    const changed = (event: Event) => {
      if ((event as CustomEvent<{ siteId: string }>).detail?.siteId !== siteId) return;
      window.clearTimeout(timer);
      timer = window.setTimeout(() => setRequest(value => value + 1), 700);
    };
    window.addEventListener(PROJECT_CHANGED_EVENT, changed);
    return () => { window.clearTimeout(timer); window.removeEventListener(PROJECT_CHANGED_EVENT, changed); };
  }, [siteId]);
  React.useEffect(() => {
    let cancelled = false;
    setLoading(true); setError("");
    api<ProjectContentStatus>(`/sites/${siteId}/pages/interlinking`, { cache: "no-store" }).then(result => {
      if (cancelled) return;
      if (typeof result?.complete !== "boolean" || !Number.isInteger(result.internal_count)) throw new Error("Не получены данные проверки перелинковки.");
      setStatus(result);
      publishStatus.current?.(siteId, result);
      projectNotice({ siteId, key: "interlinking-check", code: "INTERLINKING_CHECK", message: result.warning || "Проверка перелинковки выполнена.", severity: "warning", active: !!result.warning });
    }).catch(cause => {
      if (cancelled) return;
      const message = cause instanceof Error ? cause.message : "Не удалось проверить перелинковку.";
      setError(message);
      projectNotice({ siteId, key: "interlinking-check", code: "INTERLINKING_CHECK", message, severity: "warning", active: true });
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [siteId, api, refreshToken, request]);
  const complete = !loading && !error && !status?.warning && status?.complete === true;
  const detail = loading ? "Проверяем ссылки в контенте страниц…" : error || (status ? `${status.message}\nГлавная → внутренние: ${status.linked_from_home}/${status.internal_count}. Внутренние → главная: ${status.linked_to_home}/${status.internal_count}.` : "Перелинковка пока не проверена.");
  return <><button type="button" className={`projectInterlinking ${complete ? "isComplete" : ""}`} aria-label={complete ? "Перелинковка выполнена" : "Перелинковка не выполнена"} aria-busy={loading} disabled={loading} title={`${detail}\nНажмите, чтобы проверить ещё раз.`} onClick={() => setRequest(value => value + 1)}>
    <CheckCircle2 size={18} aria-hidden="true" /><span>Перелинковка</span>
  </button>{generalSite && <button type="button" className={`projectShowcaseIndicator ${status?.showcase?.count && !error ? "hasBrands" : ""}`} title={error || (status?.showcase ? (status.showcase.brands.join(", ") || status.showcase.message) : "Определяем бренды витрины…")} aria-label="Витрина — открыть контент и публикацию" onClick={onShowcaseClick}>
    <Store size={17} aria-hidden="true" /><span>Витрина</span><b className="projectShowcaseCount" aria-label={`Брендов: ${status?.showcase?.count ?? "не определено"}`}>{status?.showcase?.count ?? (loading ? "…" : "—")}</b>
  </button>}</>;
}

export { ShowcaseBrands } from "./ShowcaseBrands";
