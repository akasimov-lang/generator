import { BrandIcon } from "./BrandIcon";
import React from "react";
import { RefreshCcw } from "lucide-react";
import { TemplateCombobox } from "./TemplateCombobox";
type Api = <T>(path: string, init?: RequestInit) => Promise<T>;
type Brand = { key: string; brand: string; project_count: number; domain_count: number; projects: { id: string; name: string; geo?: string; domain_count: number; synced_at?: string }[] };
export function BrandNetworkTable({ api }: { api: Api }) {
  const [brands, setBrands] = React.useState<Brand[]>([]);
  const [selected, setSelected] = React.useState("");
  const [query, setQuery] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const load = React.useCallback(async () => { setBusy(true); setError(""); try { setBrands((await api<{ brands: Brand[] }>("/auto-reglue/brands")).brands); } catch (e) { setError(e instanceof Error ? e.message : "Не удалось загрузить бренды"); } finally { setBusy(false); } }, [api]);
  React.useEffect(() => { void load(); }, [load]);
  const brand = brands.find(item => item.key === selected);
  return <section className="dataPanel"><div className="dataPanelHeader"><h2>Бренды и сетки проектов</h2><button className="button secondary" disabled={busy} onClick={() => void load()}><RefreshCcw size={16} />Обновить таблицу</button></div><div className="dataPanelBody"><p>Доступные активные проекты. Число доменов — сумма по последним данным проектов. Переносы доменов пока отключены.</p>{error && <p role="alert">{error}</p>}
    <TemplateCombobox label="Бренд для межпроектного переклея" value={selected} options={brands.filter(b => b.project_count >= 2).map(b => ({ value: b.key, label: `${b.brand} — ${b.project_count} проектов`, keywords: b.brand }))} onChange={setSelected} placeholder="Выберите бренд с двумя или более проектами" />
    <label>Поиск бренда<input value={query} onChange={e => setQuery(e.target.value)} placeholder="Название бренда" /></label>
    <div style={{ overflowX: "auto" }}><table className="dataTable"><thead><tr><th>Бренд</th><th>Проектов</th><th>Доменов в проектах</th><th>Выбор</th></tr></thead><tbody>{brands.filter(b => b.brand.toLowerCase().includes(query.toLowerCase())).map(b => <tr key={b.key}><td><span className="brandTableName"><BrandIcon brand={b.brand} />{b.brand}</span></td><td>{b.project_count}</td><td>{b.domain_count}</td><td><button type="button" className="button secondary compact" disabled={b.project_count < 2} aria-pressed={b.key === selected} onClick={() => setSelected(b.key)}>{b.key === selected ? "Выбран" : b.project_count < 2 ? "Нужно 2 проекта" : "Выбрать"}</button></td></tr>)}</tbody></table></div>{!brands.length && <p>{busy ? "Загрузка брендов…" : "Нет доступных проектов с указанным брендом."}</p>}
    {brand && <div className="networkSection"><h3>{brand.brand}: проекты</h3><ul>{brand.projects.map(p => <li key={p.id}><a href={`/project-auto-reglue/${encodeURIComponent(p.name)}/`}>{p.name}</a> · {p.geo || "ГЕО не указано"} · {p.domain_count} доменов{p.synced_at && <small> · данные от {new Date(p.synced_at).toLocaleString("ru-RU")}</small>}</li>)}</ul><p>Бренд выбран для подготовки отдельного теста. Изменений в сетках нет.</p></div>}
  </div></section>;
}
