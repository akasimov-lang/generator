import React from "react";
import { ChevronDown, Check } from "lucide-react";

type Option = { value: string; label: string; keywords?: string };

export function TemplateCombobox({ label, value, options, onChange, allowCustom = false, placeholder = "Введите название или код" }: {
  label: string; value: string; options: Option[]; onChange: (value: string) => void; allowCustom?: boolean; placeholder?: string;
}) {
  const id = React.useId();
  const beforeEdit = React.useRef(value);
  const input = React.useRef<HTMLInputElement>(null);
  const list = React.useRef<HTMLDivElement>(null);
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState<string | null>(null);
  const [active, setActive] = React.useState(0);
  const selected = options.find(o => o.value === value);
  const normalized = (query || "").trim().toLocaleLowerCase();
  const matches = options.filter(o => `${o.label} ${o.value} ${o.keywords || ""}`.toLocaleLowerCase().includes(normalized));
  const filtered = allowCustom && normalized && !options.some(o => o.value.toLocaleLowerCase() === normalized) ? [{ value: (query || "").trim(), label: `Использовать «${(query || "").trim()}»` }, ...matches] : matches;

  function show() { beforeEdit.current = value; setOpen(true); setQuery(null); setActive(Math.max(0, options.findIndex(o => o.value === value))); }
  function close() { setOpen(false); setQuery(null); }
  function choose(option: Option) { onChange(option.value); close(); input.current?.focus(); }
  React.useEffect(() => {
    if (open) list.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  return <div className="tg-combobox" onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget as Node)) close(); }}>
    <label htmlFor={id}>{label}</label>
    <div className="tg-combobox-control">
      <input id={id} ref={input} role="combobox" aria-autocomplete="list" aria-expanded={open}
        aria-controls={`${id}-list`} aria-activedescendant={open && filtered[active] ? `${id}-option-${active}` : undefined}
        autoComplete="off" spellCheck={false} value={query ?? selected?.label ?? value}
        maxLength={allowCustom ? 160 : undefined} placeholder={placeholder} onFocus={e => { show(); e.target.select(); }}
        onClick={() => { if (!open) show(); }}
        onChange={e => { if (!open) beforeEdit.current = value; setQuery(e.target.value); if (allowCustom) onChange(e.target.value); setOpen(true); setActive(0); }}
        onKeyDown={e => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            if (!open) show();
            else setActive(i => Math.max(0, Math.min(filtered.length - 1, i + (e.key === "ArrowDown" ? 1 : -1))));
          } else if (e.key === "Enter" && open) {
            e.preventDefault(); if (filtered[active]) choose(filtered[active]);
          } else if (e.key === "Escape") { e.preventDefault(); if (allowCustom && open) onChange(beforeEdit.current); close(); }
          else if (e.key === "Tab") close();
        }} />
      <button type="button" tabIndex={-1} aria-label={`Открыть список: ${label}`}
        onMouseDown={e => e.preventDefault()} onClick={() => { if (open) close(); else { input.current?.focus(); show(); } }}><ChevronDown size={18} /></button>
    </div>
    {open && <div ref={list} id={`${id}-list`} role="listbox" aria-label={label} className="tg-combobox-list">
      {filtered.map((option, index) => <div role="option" id={`${id}-option-${index}`} key={option.value}
        aria-selected={option.value === value} data-index={index} className={index === active ? "active" : ""}
        onMouseDown={e => e.preventDefault()} onClick={() => choose(option)}>
        <span>{option.label}</span>{option.value === value && <Check size={16} />}
      </div>)}
      {!filtered.length && <p role="status">Ничего не найдено. Попробуйте название или код.</p>}
    </div>}
  </div>;
}
