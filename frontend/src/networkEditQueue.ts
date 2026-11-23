export type NetworkEditAction = "reserve" | "reglue" | "domain_redirect" | "domain_redirects_main" | "page_redirect";
export type NetworkEditRequest = { action: NetworkEditAction; revision: string; expected: Record<string, unknown>; [key: string]: unknown };
export type NetworkEditItem = { id: string; request: NetworkEditRequest; status: string; message: string; created_at?: string };
export type NetworkEditSnapshot<T> = { items: NetworkEditItem[]; limit: number; network: T | null };
type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
export const editActive = (item: NetworkEditItem) => !["completed", "failed"].includes(item.status);
export function editKey(request: NetworkEditRequest): string {
  if (request.action === "domain_redirect") return `domain:${request.redirect_original_source || request.redirect_source}`;
  if (request.action === "page_redirect") return `page:${request.page_redirect_original_domain || request.page_redirect_domain}:${request.page_redirect_original_source || request.page_redirect_source}`;
  return request.action;
}

/** Immediate local acknowledgement followed by a durable, idempotent server enqueue. */
export class NetworkEditQueue<T> {
  server: NetworkEditSnapshot<T> = { items: [], limit: 30, network: null };
  pending = new Map<string, NetworkEditItem>();
  error = "";
  private listeners = new Set<() => void>();
  private sending = false;
  private reading = false;
  private epoch = 0;
  private networkBusy = false;
  private dismissing = new Set<string>();
  private dismissedIds = new Set<string>();
  private outbox: string[] = [];
  private siteId: string;
  private api: Api;
  private requestTimeoutMs: number;
  constructor(siteId: string, api: Api, requestTimeoutMs = 20000) { this.siteId = siteId; this.api = api; this.requestTimeoutMs = requestTimeoutMs; }
  private async request<R>(path: string, options?: RequestInit): Promise<R> {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      return await Promise.race([
        this.api<R>(path, { ...options, signal: controller.signal }),
        new Promise<never>((_, reject) => {
          timer = setTimeout(() => {
            reject(new Error("Сервер не ответил вовремя. Проверяем статус отправки."));
            controller.abort();
          }, this.requestTimeoutMs);
          // Unresolved test/middleware promises must not keep a Node process alive.
          (timer as unknown as { unref?: () => void }).unref?.();
        }),
      ]);
    } finally { if (timer !== undefined) clearTimeout(timer); }
  }
  subscribe(listener: () => void) { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; }
  private emit() { for (const listener of this.listeners) listener(); }
  get items() { return [...this.pending.values(), ...this.server.items.filter(item => !this.pending.has(item.id))].filter(item => !this.dismissedIds.has(item.id)); }
  latest(key: string) { return this.items.filter(item => editKey(item.request) === key).sort((a,b) => (b.created_at || "").localeCompare(a.created_at || ""))[0]; }
  busy(key: string) { return this.items.some(item => editKey(item.request) === key && editActive(item)); }
  get count() { return this.items.filter(editActive).length; }
  setNetworkBusy(busy: boolean) {
    if (busy !== this.networkBusy) { this.epoch++; this.networkBusy = busy; this.server = { ...this.server, network: null }; }
  }
  private accept(snapshot: NetworkEditSnapshot<T>) {
    this.server = { ...snapshot, items: snapshot.items.filter(item => !this.dismissedIds.has(item.id)), network: this.networkBusy ? null : snapshot.network };
    for (const item of snapshot.items) this.pending.delete(item.id);
    this.emit();
  }
  async refresh() {
    if (this.reading || this.sending || this.dismissing.size) return;
    this.reading = true; const epoch = this.epoch;
    try {
      const snapshot = await this.request<NetworkEditSnapshot<T>>(`/sites/${this.siteId}/network/edit-queue`);
      if (epoch === this.epoch && !this.sending) { this.error = ""; this.accept(snapshot); void this.send(); }
    } catch (error) { this.error = error instanceof Error ? error.message : "Не удалось проверить очередь"; this.emit(); }
    finally { this.reading = false; }
  }
  enqueue(request: NetworkEditRequest) {
    if (this.busy(editKey(request))) return false;
    if (this.count >= this.server.limit) { this.error = "В очереди уже 30 изменений."; this.emit(); return false; }
    const id = crypto.randomUUID();
    this.pending.set(id, { id, request: structuredClone(request), status: "submitting", message: "Отправляем на сервер…", created_at: new Date().toISOString() });
    this.outbox.push(id); this.epoch++; this.error = ""; this.emit(); void this.send();
    return true;
  }
  retry(id: string) {
    const item = this.pending.get(id);
    if (!item || item.status !== "unconfirmed") return;
    this.pending.set(id, { ...item, status: "submitting", message: "Проверяем отправку…" });
    this.outbox.unshift(id); this.epoch++; this.emit(); void this.send();
  }
  async dismiss(id: string): Promise<boolean> {
    const item = this.items.find(candidate => candidate.id === id);
    if (!item || item.status !== "failed" || item.request.action !== "domain_redirect") return false;
    const key = editKey(item.request);
    if (this.busy(key) || this.dismissing.has(key)) return false;
    const olderFailure = (candidate: NetworkEditItem) => candidate.status === "failed" && editKey(candidate.request) === key &&
      (candidate.id === id || !!candidate.created_at && !!item.created_at && Date.parse(candidate.created_at) <= Date.parse(item.created_at));
    const discarded = this.items.filter(olderFailure).map(candidate => candidate.id);
    // A rejected local enqueue may overlay an earlier persisted failure. Dismiss
    // that server history too, so a reload cannot bring the same draft back.
    const saved = this.server.items.filter(olderFailure).sort((a,b) => (b.created_at || "").localeCompare(a.created_at || ""))[0];
    this.dismissing.add(key); const epoch = ++this.epoch;
    try {
      const snapshot = saved ? await this.request<NetworkEditSnapshot<T>>(`/sites/${this.siteId}/network/edit-queue/${encodeURIComponent(saved.id)}`, { method: "DELETE" }) : null;
      const current = epoch === this.epoch;
      this.epoch++;
      for (const discardedId of discarded) { this.dismissedIds.add(discardedId); this.pending.delete(discardedId); }
      this.outbox = this.outbox.filter(queuedId => !this.dismissedIds.has(queuedId));
      this.error = "";
      if (snapshot) this.accept(current ? snapshot : { ...snapshot, network: null }); else this.emit();
      return true;
    } catch (error) {
      this.error = error instanceof Error ? error.message : "Не удалось удалить ошибочную строку. Повторите удаление.";
      this.emit();
      throw error;
    } finally { this.dismissing.delete(key); }
  }
  private async send() {
    if (this.sending || [...this.pending.values()].some(item => item.status === "unconfirmed")) return;
    this.sending = true;
    try {
      while (this.outbox.length) {
        const id = this.outbox.shift()!; const item = this.pending.get(id);
        if (!item) continue;
        const epoch = this.epoch;
        try {
          const snapshot = await this.request<NetworkEditSnapshot<T>>(`/sites/${this.siteId}/network/edit-queue`, {
            method: "POST", body: JSON.stringify({ ...item.request, request_id: id }),
          });
          this.pending.delete(id); this.accept(epoch === this.epoch ? snapshot : { ...snapshot, network: null });
        } catch (error) {
          const status = (error as { statusCode?: number })?.statusCode;
          const rejected = !!status && status >= 400 && status < 500;
          this.pending.set(id, { ...item, status: rejected ? "failed" : "unconfirmed", message:
            rejected ? (error instanceof Error ? error.message : "Не удалось добавить задачу") : "Отправка не подтверждена. Проверяем очередь…" });
          this.emit();
          if (!rejected) break;
        }
      }
    } finally { this.sending = false; }
  }
}

export type NetworkEditQueueView = Pick<NetworkEditQueue<unknown>, "items" | "latest" | "busy" | "retry" | "dismiss">;
