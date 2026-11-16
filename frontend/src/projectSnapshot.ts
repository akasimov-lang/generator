// Project snapshots are optional and isolated by externally authenticated user.
// Storage failures must never prevent authentication or loading fresh projects.
export type ProjectSnapshot<T> = { projects: T[]; updatedAt: string | null };
const SNAPSHOT_TIMEOUT_MS = 1500;

function snapshotRequest<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    let db: IDBDatabase | undefined;
    let tx: IDBTransaction | undefined;
    let finished = false;
    const finish = (error?: unknown, result?: T) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      if (error) {
        try { tx?.abort(); } catch { /* transaction may already be complete */ }
      }
      db?.close();
      if (error) reject(error);
      else resolve(result as T);
    };
    const timer = setTimeout(() => finish(new Error("Локальный кеш не ответил вовремя.")), SNAPSHOT_TIMEOUT_MS);
    try {
      const opening = indexedDB.open("pagepilot-projects", 1);
      opening.onblocked = () => finish(new Error("Локальный кеш занят другой вкладкой."));
      opening.onerror = () => finish(opening.error || new Error("Локальный кеш недоступен."));
      opening.onupgradeneeded = () => {
        if (finished) { opening.transaction?.abort(); return; }
        opening.result.createObjectStore("snapshots");
      };
      opening.onsuccess = () => {
        db = opening.result;
        if (finished) { db.close(); return; }
        db.onversionchange = () => db?.close();
        try {
          tx = db.transaction("snapshots", mode);
          const request = run(tx.objectStore("snapshots"));
          tx.oncomplete = () => finish(undefined, request.result);
          tx.onerror = tx.onabort = () => finish(tx?.error || new Error("Операция с локальным кешем прервана."));
          request.onerror = () => finish(request.error || new Error("Ошибка локального кеша."));
        } catch (error) { finish(error); }
      };
    } catch (error) { finish(error); }
  });
}

export async function readProjectSnapshot<T>(userId: string): Promise<ProjectSnapshot<T>> {
  return await snapshotRequest<ProjectSnapshot<T> | undefined>("readonly", store => store.get(userId))
    || { projects: [], updatedAt: null };
}

export async function writeProjectSnapshot<T>(userId: string, snapshot: ProjectSnapshot<T>): Promise<void> {
  await snapshotRequest("readwrite", store => store.put(snapshot, userId));
}

export async function removeLegacyProjectSnapshot(): Promise<void> {
  await snapshotRequest("readwrite", store => store.delete("shared-projects-v1"));
}
