import type { NetworkEditItem } from "./networkEditQueue";

export function queueSaveState(items: NetworkEditItem[]) {
  const latest = [...items].sort((a,b) => (b.created_at || "").localeCompare(a.created_at || ""));
  const item = latest.find(item => item.status === "unconfirmed")
    || latest.find(item => !["completed", "failed"].includes(item.status)) || latest[0];
  if (!item) return { state: "idle" as const, version: "" };
  const version = `${item.id}:${item.status}`;
  if (item.status === "failed" || item.status === "unconfirmed") {
    return { state: "error" as const, version, message: item.message };
  }
  if (item.status === "completed") return { state: "saved" as const, version };
  if (item.status === "submitting" || item.status === "processing") {
    return { state: "saving" as const, version, message: item.message };
  }
  return { state: "waiting" as const, version, message: item.message || "В очереди. Ожидаем выполнения…" };
}
