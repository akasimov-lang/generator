import * as React from "react";
import { AlertCircle, CheckCircle2, ChevronDown, ChevronUp, Copy } from "lucide-react";
import "./styles/domain-column-header.css";

export function DomainColumnHeader({ label, domains, sortDirection, onSort, copyText }: {
  label: string;
  domains: string[];
  sortDirection?: "asc" | "desc";
  onSort: () => void;
  copyText: (text: string) => Promise<void>;
}) {
  const [state, setState] = React.useState<"idle" | "copying" | "copied" | "error">("idle");
  const values = domains.map(domain => domain.trim()).filter(domain => domain && domain !== "—");
  const text = values.join("\n");
  React.useEffect(() => { setState("idle"); }, [text]);
  React.useEffect(() => {
    if (state !== "copied" && state !== "error") return;
    const timer = window.setTimeout(() => setState("idle"), state === "error" ? 5000 : 2400);
    return () => window.clearTimeout(timer);
  }, [state]);
  const message = state === "copied" ? `Скопировано доменов: ${values.length}`
    : state === "error" ? "Не удалось скопировать домены. Повторите попытку."
    : `Скопировать домены из ${label}: ${values.length} (вся выборка)`;

  async function copy() {
    setState("copying");
    try { await copyText(text); setState("copied"); }
    catch { setState("error"); }
  }

  return <span className="domainColumnHeader">
    <button className={`tableSortButton ${sortDirection ? "active" : ""}`} type="button" onClick={onSort}>
      <span>{label}</span>
      {sortDirection === "desc" ? <ChevronDown size={15} /> : <ChevronUp size={15} />}
    </button>
    <button className={`domainColumnCopyButton ${state}`} type="button"
      title={message} aria-label={`Скопировать домены из столбца ${label}`}
      disabled={!values.length || state === "copying"} aria-busy={state === "copying"}
      onClick={event => { event.stopPropagation(); void copy(); }}>
      {state === "copied" ? <CheckCircle2 size={13} /> : state === "error" ? <AlertCircle size={13} /> : <Copy size={13} />}
    </button>
    <span className="domainColumnCopyStatus" role="status">{state === "copied" || state === "error" ? message : ""}</span>
  </span>;
}
