export type FakeAction = "delete" | "create";
export type FakeQueueItem = { id: string; action: FakeAction; path: string; status: string; message: string; operation_ids: string[] };
export type FakeQueueSnapshot<T> = { items: FakeQueueItem[]; limit: number; active_count: number; network: T | null };
type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
export const fakeQueueActive = (item: FakeQueueItem) => !["completed", "failed"].includes(item.status);
export const normalizedFakePath = (path: string) => "/" + path.trim().replace(/^\/+|\/+$/g, "") + (path.trim().endsWith("/") ? "/" : "");

/** Local submissions are immediate; only the short enqueue requests are serialized. */
export class FakeMainQueue<T> {
  server: FakeQueueSnapshot<T> = { items: [], limit: 10, active_count: 0, network: null };
  pending = new Map<string, FakeQueueItem>();
  error = "";
  private listeners = new Set<() => void>();
  private sending = false;
  private reading = false;
  private epoch = 0;
  private networkBusy = false;
  private outbox: string[] = [];
  private siteId: string;
  private api: Api;
  constructor(siteId: string, api: Api) { this.siteId = siteId; this.api = api; }
  subscribe(listener: () => void) { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; }
  private emit() { for (const listener of this.listeners) listener(); }
  get items() { return [...this.pending.values(), ...this.server.items.filter(item => !this.pending.has(item.id))]; }
  get count() { return this.items.filter(fakeQueueActive).length; }
  busyPath(path: string) { return this.items.some(item => item.path === normalizedFakePath(path) && fakeQueueActive(item)); }
  setNetworkBusy(busy: boolean) {
    if (busy !== this.networkBusy) { this.epoch++; this.networkBusy = busy; this.server = { ...this.server, network: null }; }
  }
  private accept(snapshot: FakeQueueSnapshot<T>) {
    this.server = this.networkBusy ? { ...snapshot, network: null } : snapshot;
    for (const item of snapshot.items) this.pending.delete(item.id);
    this.emit();
  }
  async refresh() {
    if (this.reading || this.sending || this.networkBusy) return;
    this.reading = true; const epoch = this.epoch;
    try {
      const snapshot = await this.api<FakeQueueSnapshot<T>>(`/sites/${this.siteId}/network/fake-main-queue`);
      if (epoch === this.epoch && !this.sending) { this.error = ""; this.accept(snapshot); }
    } catch (error) { this.error = error instanceof Error ? error.message : "Не удалось проверить очередь"; this.emit(); }
    finally { this.reading = false; }
  }
  enqueue(action: FakeAction, rawPath: string) {
    const path = normalizedFakePath(rawPath);
    if (this.busyPath(path)) return false;
    if (this.count >= this.server.limit) { this.error = "В очереди уже 10 страниц."; this.emit(); return false; }
    const id = crypto.randomUUID();
    this.pending.set(id, { id, action, path, status: "submitting", message: "Добавляем в очередь…", operation_ids: [id] });
    this.outbox.push(id); this.epoch++; this.error = ""; this.emit(); void this.send();
    return true;
  }
  retry(id: string) {
    const item = this.pending.get(id);
    if (!item || item.status !== "unconfirmed") return;
    this.pending.set(id, { ...item, status: "submitting", message: "Проверяем постановку в очередь…" });
    this.outbox.push(id); this.epoch++; this.emit(); void this.send();
  }
  private async send() {
    if (this.sending) return;
    this.sending = true;
    try {
      while (this.outbox.length) {
        const id = this.outbox.shift()!; const item = this.pending.get(id);
        if (!item) continue;
        const epoch = this.epoch;
        try {
          const snapshot = await this.api<FakeQueueSnapshot<T>>(`/sites/${this.siteId}/network/fake-main-queue`, {
            method: "POST", body: JSON.stringify({ request_id: id, action: item.action, path: item.path }),
          });
          this.pending.delete(id); this.accept(epoch === this.epoch ? snapshot : { ...snapshot, network: null });
        } catch (error) {
          const status = (error as { statusCode?: number })?.statusCode;
          const rejected = !!status && status >= 400 && status < 500;
          this.pending.set(id, { ...item, status: rejected ? "failed" : "unconfirmed", message:
            rejected ? (error instanceof Error ? error.message : "Не удалось добавить задачу") : "Отправка не подтверждена. Проверяем очередь…" });
          this.emit();
        }
      }
    } finally { this.sending = false; }
  }
}
