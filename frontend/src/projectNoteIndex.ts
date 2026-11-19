import React from "react";
export type NoteApi = <T>(path: string, init?: RequestInit) => Promise<T>;
export const NOTE_CHANGED = "pagepilot:project-note-changed";
export function useProjectNoteIndex(api: NoteApi) {
  const [ids, setIds] = React.useState<Set<string>>(new Set());
  const [error, setError] = React.useState("");
  React.useEffect(() => {
    let alive = true, generation = 0;
    const changes = new Map<string, boolean>();
    const load = async () => {
      const request = ++generation; changes.clear();
      try {
        const result = await api<{site_ids:string[]}>("/project-notes");
        if (!alive || request !== generation) return;
        const next = new Set(result.site_ids);
        changes.forEach((has, id) => has ? next.add(id) : next.delete(id));
        setIds(next); setError("");
      } catch { if (alive) setError("Не удалось проверить заметки. Приоритет проектов с заметками временно недоступен."); }
    };
    const changed = (e: Event) => {
      const {siteId, hasNote} = (e as CustomEvent).detail;
      changes.set(siteId, hasNote);
      setIds(old => { const next = new Set(old); hasNote ? next.add(siteId) : next.delete(siteId); return next; });
    };
    window.addEventListener(NOTE_CHANGED, changed);
    window.addEventListener("focus", load);
    void load();
    return () => { alive = false; window.removeEventListener(NOTE_CHANGED, changed); window.removeEventListener("focus", load); };
  }, [api]);
  return {ids, error};
}
