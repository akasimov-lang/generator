import type { FakeQueueItem } from "./fakeMainQueue";

type Operation = { action?: string; id: string; status: string; created_at: string };
export const activeStatuses = new Set(["pending", "unknown", "queued", "running", "waiting", "processing", "submitting", "unconfirmed", "index_queued", "index_submitting", "index_unknown"]);
export function networkOperationHistory<T extends Operation>(operations: T[], queue: FakeQueueItem[]) {
  const receipts = new Set(queue.flatMap(item => item.operation_ids));
  const rows = [
    ...operations.filter(item => item.action !== "indexing" && !receipts.has(item.id)).map(item => ({ kind: "operation" as const, item })),
    ...queue.map(item => ({ kind: "queue" as const, item })),
  ];
  return rows.sort((a, b) => Number(activeStatuses.has(b.item.status)) - Number(activeStatuses.has(a.item.status))
    || Date.parse(b.item.created_at || "1970-01-01") - Date.parse(a.item.created_at || "1970-01-01")
    || a.item.id.localeCompare(b.item.id));
}
export const fakeQueueStatus: Record<string, string> = {
  submitting: "Отправляем заявку", unconfirmed: "Отправка не подтверждена", queued: "В очереди",
  processing: "Выполняется", waiting: "Ожидаем подтверждения Webdev", completed: "Подтверждено", failed: "Ошибка",
};
