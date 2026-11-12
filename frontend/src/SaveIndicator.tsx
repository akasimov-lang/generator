import React from "react";
import { Save } from "lucide-react";
import { editActive, type NetworkEditItem } from "./networkEditQueue";
import "./styles/save-indicator.css";

export type SaveState = "idle" | "saving" | "saved" | "error";
export function SaveIndicator({state, version = "", label = "Сохранение", error}: {state: SaveState; version?: string; label?: string; error?: string}) {
  const token = `${state}:${version}`;
  const previous = React.useRef(token);
  const [visible, setVisible] = React.useState(state === "saving" || state === "error");
  React.useEffect(() => {
    const changed = previous.current !== token;
    previous.current = token;
    if (state === "saving" || state === "error") { setVisible(true); return; }
    if (state === "saved" && changed) {
      setVisible(true);
      const timer = window.setTimeout(() => setVisible(false), 3000);
      return () => window.clearTimeout(timer);
    }
    if (state === "idle") setVisible(false);
  }, [state, token]);
  const message = state === "saving" ? "Сохраняем…" : state === "saved" ? "Сохранено успешно!" : state === "error" ? error?.trim() || "Не удалось сохранить. Причина не получена от сервера." : "";
  const text = `${label}: ${message}`;
  return <span className={`saveIndicator ${state}${visible ? " visible" : ""}`} title={visible ? text : undefined} role="status" aria-label={visible ? text : undefined} aria-hidden={!visible}>
    <Save size={14} strokeWidth={1.8} aria-hidden="true" />
    {visible && <span className="saveIndicatorText">{message}</span>}
  </span>;
}

export function QueueSaveIndicator({items, label}: {items: NetworkEditItem[]; label: string}) {
  const latest = [...items].sort((a,b) => (b.created_at || "").localeCompare(a.created_at || ""))[0];
  const pending = items.find(editActive);
  const item = pending || latest;
  const state: SaveState = !item ? "idle" : editActive(item) ? "saving" : item.status === "failed" ? "error" : "saved";
  return <SaveIndicator state={state} version={item?.id || ""} label={label} error={item?.message} />;
}
