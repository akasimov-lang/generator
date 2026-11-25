import React from 'react';
import {host} from './redirectScheme';

export function RedirectSchemeHeader({fiberyName, canon, domains, types, redirectCount, backHref}: {
  fiberyName?: string | null; canon: string; domains: string[]; types: Record<string,string>;
  redirectCount: number; backHref: string;
}) {
  const counts = React.useMemo(() => {
    const members = new Map<string,string>();
    for (const domain of domains) {
      const name = host(domain), kind = types[domain];
      if (name && (kind === 'drop' || kind === 'newreg')) members.set(name, kind);
    }
    return {drops: [...members.values()].filter(kind => kind === 'drop').length,
      newregs: [...members.values()].filter(kind => kind === 'newreg').length};
  }, [domains, types]);
  return <header className="redirectFullscreenHeader">
    <a className="button secondary compact" href={backHref}>Назад</a>
    <dl className="redirectSchemaSummary" aria-label="Сводка сетки">
      <div><dt>Fibery</dt><dd title={fiberyName || 'Имя Fibery не задано'}>{fiberyName || 'Не задано'}</dd></div>
      <div className="redirectSchemaMain"><dt>Main</dt><dd>{canon || '—'}</dd></div>
      <div className="redirectSchemaNewregs"><dt>Новореги</dt><dd>{counts.newregs}</dd></div>
      <div className="redirectSchemaDrops"><dt>Дропы</dt><dd>{counts.drops}</dd></div>
      <div title="Связи текущей схемы, включая изменения в черновике"><dt>Редиректы</dt><dd>{redirectCount}</dd></div>
    </dl>
  </header>;
}
