export type TableSaveEvent = {
  id: string; domain: string; field: string; value: string; createdAt: string;
  status: "saving" | "saved" | "error" | "unknown"; message: string;
};

// Keep request failures as well as successes in this user's project history.
export class NetworkTableSaveLog {
  private items: TableSaveEvent[] = [];
  private listeners = new Set<() => void>();
  private key: string;
  private storage: Pick<Storage, "getItem" | "setItem">;
  constructor(username: string, siteId: string, storage: Pick<Storage, "getItem" | "setItem"> = sessionStorage) {
    this.storage = storage;
    this.key = `network-table-saves:${username}:${siteId}`;
    try {
      const saved = JSON.parse(storage.getItem(this.key) || "[]");
      if (Array.isArray(saved)) this.items = saved.filter(item => item &&
        ["id", "domain", "field", "value", "createdAt", "message"].every(key => typeof item[key] === "string") &&
        ["saving", "saved", "error", "unknown"].includes(item.status)).slice(0, 100).map(item => item.status === "saving"
          ? {...item, status: "unknown", message: "Подтверждение сохранения не получено. Обновите данные сетки перед повторной попыткой."} : item);
    } catch { /* Storage may be unavailable or contain an old value. */ }
  }
  getSnapshot = () => this.items;
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  private update(items: TableSaveEvent[]) {
    this.items = items.filter((item, index) => index < 100 || item.status === "saving");
    try { this.storage.setItem(this.key, JSON.stringify(this.items)); } catch { /* Still show the live result. */ }
    this.listeners.forEach(listener => listener());
  }
  start(domain: string, field: string, value: string) {
    const item: TableSaveEvent = {id: crypto.randomUUID(), domain, field, value,
      createdAt: new Date().toISOString(), status: "saving", message: "Сохраняем…"};
    this.update([item, ...this.items]);
    return item.id;
  }
  finish(id: string, error?: string) {
    this.update(this.items.map(item => item.id === id
      ? {...item, status: error ? "error" : "saved", message: error || "Сохранено"} : item));
  }
}
