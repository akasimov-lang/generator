export type ProjectNotice = { siteId: string; key: string; code: string; message: string; context?: string; severity: "info" | "warning" | "error"; active: boolean; persist?: boolean; synced?: boolean; created_at?: string };
export const NOTICE_EVENT = "pagepilot-project-notice";
export const PROJECT_CHANGED_EVENT = "pagepilot-project-changed";
const notices = new Map<string, ProjectNotice>();
let activeSite = "";
export function setNotificationProject(siteId: string) { activeSite = siteId; }
export function localProjectNotices(siteId: string) { return [...notices.values()].filter(notice => notice.siteId === siteId); }
export function noticeSynced(siteId:string,key:string) {
  const id=siteId+":"+key,notice=notices.get(id);
  if(!notice)return;
  notices.set(id,{...notice,synced:true});
  window.dispatchEvent(new CustomEvent(NOTICE_EVENT,{detail:{...notice,persist:false}}));
}
function redact(text: string) { return text.replace(/(bearer\s+)[\w.\-]+/gi, "$1[скрыто]").replace(/((?:api[_-]?key|access[_-]?token|password|secret|token)["']?\s*[=:]\s*["']?)[^\s&"'<>]+/gi, "$1[скрыто]"); }
export function projectNotice(notice: ProjectNotice) {
  const id = notice.siteId + ":" + notice.key;
  const value = { ...notice, synced:false, message: redact(notice.message).slice(0, 20000), context: redact(notice.context || "").slice(0, 2000), created_at: new Date().toISOString() };
  const previous = notices.get(id);
  if (previous && previous.active === value.active && previous.message === value.message && previous.code === value.code) return;
  if (!value.active && !previous) return;
  notices.set(id, value);
  window.dispatchEvent(new CustomEvent(NOTICE_EVENT, { detail: value }));
}
export function projectApiResult(path: string, method: string, error?: unknown) {
  if (path.includes("/notifications")) return;
  const siteId = path.match(/^\/sites\/([\w-]{36})(?:\/|$|\?)/)?.[1] || activeSite;
  if (!siteId) return;
  if (!error && (method !== "GET" || /\/network(?:\?|$)/.test(path))) projectChanged(siteId);
  const endpoint = path.split("?")[0];
  const key = `api:${method}:${endpoint}`;
  const previous = notices.get(siteId + ":" + key);
  if (!error && !previous?.active) return;
  const status = (error as {statusCode?:number})?.statusCode;
  if (status === 401) return;
  projectNotice({siteId, key, code: status ? `HTTP_${status}` : "REQUEST_FAILED", severity: "error", active: !!error,
    message: error instanceof Error ? error.message : "Запрос снова выполняется успешно.", context: `${method} ${endpoint}`, persist: true});
}
export function projectChanged(siteId: string) { window.dispatchEvent(new CustomEvent(PROJECT_CHANGED_EVENT, { detail: {siteId} })); }
