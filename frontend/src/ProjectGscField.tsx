import React from "react";
import {projectGscState} from "./projectGscState";
import "./ProjectGscField.css";

type Props = {siteId: string; api: <T>(path: string, options?: RequestInit) => Promise<T>};

export function ProjectGscField({siteId, api}: Props) {
  const store = React.useMemo(() => projectGscState(siteId, api), [siteId, api]);
  const state = React.useSyncExternalStore(store.subscribe, store.snapshot, store.snapshot);
  const id = React.useId();
  React.useEffect(() => { void store.load(); return () => { void store.flush(); }; }, [store]);
  const message = state.status === "error"
    ? state.loaded ? "Не сохранено. Enter — повторить" : "Не загружено. Enter — повторить"
    : state.status === "saving" ? "Сохраняем…" : state.status === "loading" ? "Загружаем…"
    : state.status === "dirty" ? "Изменено" : "Сохранено";
  return <div className="projectGscField" data-state={state.status}>
    <label htmlFor={id}>GSC</label>
    <input id={id} type="text" value={state.value} maxLength={2000}
      placeholder="Введите значение" autoComplete="off" spellCheck={false}
      readOnly={!state.loaded} aria-describedby={`${id}-status`} aria-invalid={state.status === "error"}
      title="Ручная запись. Хранится только в PagePilot, отдельно для этого проекта."
      onChange={event => store.edit(event.target.value)}
      onFocus={() => { if (!state.loaded) void store.load(); }}
      onBlur={() => void store.flush()}
      onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); void (state.loaded ? store.flush() : store.load()); } }} />
    <small id={`${id}-status`} role="status" aria-live="polite">{message}</small>
  </div>;
}
