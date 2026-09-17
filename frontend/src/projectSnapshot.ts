// Project snapshots are isolated by externally authenticated user.
// No network requests or expiry-driven refresh.
export type ProjectSnapshot<T> = { projects: T[]; updatedAt: string | null };
async function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("pagepilot-projects", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("snapshots");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
export async function readProjectSnapshot<T>(userId: string): Promise<ProjectSnapshot<T>> {
  const db = await database();
  try {
    return await new Promise((resolve, reject) => {
      const request = db.transaction("snapshots").objectStore("snapshots").get(userId);
      request.onsuccess = () => resolve(request.result || { projects: [], updatedAt: null });
      request.onerror = () => reject(request.error);
    });
  } finally { db.close(); }
}
export async function writeProjectSnapshot<T>(userId: string, snapshot: ProjectSnapshot<T>): Promise<void> {
  const db = await database();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction("snapshots", "readwrite");
      tx.objectStore("snapshots").put(snapshot, userId);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  } finally { db.close(); }
}

export async function removeLegacyProjectSnapshot(): Promise<void> {
  const db = await database();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction("snapshots", "readwrite");
      tx.objectStore("snapshots").delete("shared-projects-v1");
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } finally { db.close(); }
}
