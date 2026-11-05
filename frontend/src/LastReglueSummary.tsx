import * as React from "react";
import "./styles/last-reglue-summary.css";

export type LastReglue = {
  at: string; old_main: string | null; new_main: string;
  old_path: string | null; new_path: string | null;
};

export type RecentNetworkChange = Omit<LastReglue, "new_main"> & {id: string; kind: "reglue" | "fake_path"; new_main: string | null};
export function LastReglueSummary({ last, observedAt, recent }: { last?: LastReglue | null; observedAt?: string | null; recent?: RecentNetworkChange[] }) {
  if (recent?.length) {
    const observed = observedAt && Number.isFinite(Date.parse(observedAt)) && (!last || Date.parse(observedAt) > Date.parse(last.at))
      ? [{id: "observed-main", kind: "observed" as const, at: observedAt, old_main: null, new_main: null, old_path: null, new_path: null}] : [];
    const changes = [...recent, ...observed].filter(item => Number.isFinite(Date.parse(item.at))).sort((a,b) => Date.parse(b.at)-Date.parse(a.at)).slice(0,7);
    const path = (value: string | null) => value === null ? "нет данных" : value || "не задан";
    return <div className="lastReglueSummary lastReglueHistory" aria-label="Последние изменения проекта" tabIndex={0}>
      <strong>Последние изменения · {changes.length}</strong>
      {changes.map(item => <article key={item.id}>
        <time dateTime={item.at}>{item.kind === "fake_path" ? "Замена внутряка" : item.kind === "observed" ? "Смена Main обнаружена" : "Переклей"}: {new Date(item.at).toLocaleString("ru-RU", {timeZone:"Europe/Moscow"})} МСК</time>
        {item.kind === "reglue" && <span>Main: {item.old_main || "нет данных"} → {item.new_main}</span>}
        {item.kind !== "observed" && <span>Внутряк: {path(item.old_path)} → {path(item.new_path)}</span>}
      </article>)}
    </div>;
  }
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
