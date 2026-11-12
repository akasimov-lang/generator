import {fakeQueueActive, type FakeQueueItem} from "./fakeMainQueue";

type Snapshot = {
  fake_main_enabled?: boolean; fake_main_current?: string; fake_main_paths?: string[];
  operations: {action: string; status: string; created_at: string}[];
};

export function fakeSaveFeedback(items: FakeQueueItem[], snapshot: Snapshot) {
  const latest = [...items].sort((a,b) => (b.created_at || "").localeCompare(a.created_at || ""))[0];
  const item = items.find(fakeQueueActive) || latest;
  if (!item || item.status === "cancelled") return {state: "idle" as const, version: ""};
  if (fakeQueueActive(item)) return {state: "saving" as const, version: item.id};
  if (item.status === "failed") {
    const matches = item.action === "delete" ? !snapshot.fake_main_paths?.includes(item.path)
      : snapshot.fake_main_enabled && snapshot.fake_main_current === item.path && snapshot.fake_main_paths?.includes(item.path);
    const correctedLater = matches && snapshot.operations.some(operation => operation.status === "confirmed"
      && ["create_fake_main", "select_fake_main", "alternates"].includes(operation.action)
      && Date.parse(operation.created_at) > Date.parse(item.finished_at || item.created_at || ""));
    // Keep the failed attempt in history. A later confirmed manual correction is
    // current state, not retroactive success of that failed request.
    if (correctedLater) return {state: "idle" as const, version: item.id};
    return {state: "error" as const, version: item.id, error: item.message};
  }
  return {state: "saved" as const, version: item.id};
}
