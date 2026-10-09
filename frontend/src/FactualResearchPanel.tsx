import React from "react";

type Source = { id: string; url: string; status: string; excerpt?: string };
type Query = {
  query: string; question: string; reason: string; source_type: string; period: string;
  round: number; status: string; results?: { url: string; title?: string; source_id?: string }[];
};
type Report = { status: string; geo?: string; language?: string; query_limit?: number; queries?: Query[]; sources?: Source[];
  competitor_url_analysis?: { status: string; pages: { url: string; status: string; analysis?: string }[] } };

export function factualResearchFromPayload(payload: Record<string, unknown>): unknown {
  const meta = payload.generation_meta;
  if (!meta || typeof meta !== "object" || !("generation_context" in meta)) return undefined;
  const context = meta.generation_context;
  return context && typeof context === "object" && "factual_research" in context ? context.factual_research : undefined;
}

const labels: Record<string, string> = {
  reading_competitors: "Gemini читает конкурентов",
  planning: "Планирование", searching: "Собираем источники", complete: "Поиск завершён",
  not_needed: "Дополнительные запросы не потребовались", budget_reached: "Достигнут лимит поиска",
  partial: "Часть данных недоступна", failed: "Не удалось составить план",
  unavailable: "DataForSEO не подключён", searched: "Выдача получена", empty: "Пустая выдача",
};

function publicLink(value: string): string | undefined {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
}

export function FactualResearchPanel({ value }: { value: unknown }) {
  if (!value || typeof value !== "object" || !("status" in value)) return null;
  const report = value as Report;
  const queries = Array.isArray(report.queries) ? report.queries : [];
  const sources = Array.isArray(report.sources) ? report.sources : [];
  return (
    <details className="briefPreview">
      <summary>Поиск фактов · {labels[report.status] || report.status} · {queries.length}/{report.query_limit ?? 6} запросов</summary>
      {report.query_limit ? <p className="fieldHint">Общий лимит на статью — 10 запросов: до 5 для конкурентов и до 5 для уточнения фактов.</p> : null}
      <p className="fieldHint">GEO: {report.geo || "—"} · Язык: {report.language || "—"}. Получение страницы само по себе не подтверждает факт.</p>
      {report.competitor_url_analysis?.pages?.length ? <div className="competitorList">
        <strong>Анализ исходных ссылок Gemini</strong>
        {report.competitor_url_analysis.pages.map((page) => <div className="competitorResult" key={page.url}>
          <a href={publicLink(page.url)} target="_blank" rel="noreferrer">{page.url}</a>
          <span>{page.status === "read" ? "Чтение подтверждено" : "Чтение не подтверждено"}</span>
          {page.analysis ? <details><summary>Анализ страницы</summary><p style={{ whiteSpace: "pre-wrap" }}>{page.analysis}</p></details> : <span>Анализ недоступен</span>}
        </div>)}
      </div> : null}
      <div className="competitorList">
        {queries.map((query, index) => (
          <div className="competitorResult" key={`${index}:${query.query}`}>
            <strong>Раунд {query.round}: {query.question}</strong>
            <p><b>Запрос:</b> {query.query}</p>
            <p><b>Цель:</b> {query.reason}</p>
            <span>Источник: {query.source_type} · Период: {query.period} · {query.status === "failed" ? "Ошибка поиска" : labels[query.status] || query.status}</span>
            {(query.results || []).map((result, resultIndex) => {
              const source = sources.find((entry) => entry.id === result.source_id);
              return (
                <div className="pageParseItem" key={`${resultIndex}:${result.url}`}>
                  <a href={publicLink(result.url)} target="_blank" rel="noreferrer">{result.title || result.url}</a>
                  <span>{source?.status === "fetched" ? "Текст получен" : "Текст источника недоступен"}</span>
                  {source?.excerpt ? <details><summary>Прочитанный текст</summary><p style={{ whiteSpace: "pre-wrap" }}>{source.excerpt}</p></details> : null}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </details>
  );
}
