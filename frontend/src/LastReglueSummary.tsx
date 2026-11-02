import * as React from "react";
import "./styles/last-reglue-summary.css";

export type LastReglue = {
  at: string; old_main: string | null; new_main: string;
  old_path: string | null; new_path: string | null;
};

export function LastReglueSummary({ last, observedAt }: { last?: LastReglue | null; observedAt?: string | null }) {
  if (observedAt && last && new Date(observedAt).getTime() > new Date(last.at).getTime()) last = null;
  const at = last?.at || observedAt;
  if (!at || !Number.isFinite(new Date(at).getTime())) return null;
  const when = new Intl.DateTimeFormat("ru-RU", {
    timeZone: "Europe/Moscow", day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).format(new Date(at));
  const path = (value: string | null) => value === null ? "нет данных" : value || "не задан";
  const lines = [
    `${last ? "Последний переклей" : "Смена Main обнаружена"}: ${when} МСК`,
    ...(last ? [`Main: ${last.old_main || "нет данных"} → ${last.new_main}`,
      `Внутряк: ${path(last.old_path)} → ${path(last.new_path)}`] : []),
  ];
  return <div className="lastReglueSummary" title={lines.join("\n")} aria-label={lines.join(". ")} tabIndex={0}>
    <time dateTime={at}>{lines[0]}</time>
    {lines.slice(1).map(line => <span key={line}>{line}</span>)}
  </div>;
}
