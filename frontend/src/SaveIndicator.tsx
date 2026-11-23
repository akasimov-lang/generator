import React from "react";
import { Save } from "lucide-react";
import { type NetworkEditItem } from "./networkEditQueue";
import { queueSaveState } from "./queueSaveState";
import "./styles/save-indicator.css";

export type SaveState = "idle" | "saving" | "saved" | "error" | "waiting";
export function SaveIndicator({state, version = "", label = "Сохранение", error, message: customMessage, showText = true}: {state: SaveState; version?: string; label?: string; error?: string; message?: string; showText?: boolean}) {
  const token = `${state}:${version}`;
  const previous = React.useRef(token);
  const [visible, setVisible] = React.useState(state === "saving" || state === "error" || state === "waiting");
  React.useEffect(() => {
    const changed = previous.current !== token;
    previous.current = token;
    if (state === "saving" || state === "error" || state === "waiting") { setVisible(true); return; }
    if (state === "saved" && changed) {
      setVisible(true);
      const timer = window.setTimeout(() => setVisible(false), 3000);
      return () => window.clearTimeout(timer);
    }
    if (state === "idle") setVisible(false);
  }, [state, token]);
  const message = customMessage || (state === "saving" ? "Сохраняем…" : state === "waiting" ? "В очереди…" : state === "saved" ? "Сохранено успешно!" : state === "error" ? error?.trim() || "Не удалось сохранить. Причина не получена от сервера." : "");
  const text = `${label}: ${message}`;
  return <span className={`saveIndicator ${state}${visible ? " visible" : ""}`} title={visible ? text : undefined} role="status" aria-label={visible ? text : undefined} aria-hidden={!visible}>
    <Save size={14} strokeWidth={1.8} aria-hidden="true" />
    {visible && showText && <span className="saveIndicatorText">{message}</span>}
  </span>;
}

export function QueueSaveIndicator({items, label, showText = true}: {items: NetworkEditItem[]; label: string; showText?: boolean}) {
  return <SaveIndicator {...queueSaveState(items)} label={label} showText={showText} />;
}
