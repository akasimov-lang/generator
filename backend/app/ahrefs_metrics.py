"""Verified Ahrefs export snapshots, independent of Webdev network refreshes."""
import base64
import csv
import hashlib
import io
import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import PurePath
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app import models
from app.domain_redirects import redirect_address

PREFIX = 'ahrefs-metric:'
COLUMNS = {'dr': 'Domain Rating', 'backlinks_all': 'Backlinks / All', 'referring_domains_all': 'Ref. domains / All'}


def key(domain):
    return PREFIX + hashlib.sha256(domain.encode()).hexdigest()


def number(value, field):
    raw = value.strip()
    if raw in ('', '-', '—', 'N/A', 'n/a'):
        return None
    raw = raw.replace(',', '').replace('\u202f', '').replace('\u00a0', '')
    try:
        parsed = float(raw)
    except ValueError:
        raise ValueError(f'Некорректное значение {field}: {value}') from None
    if not math.isfinite(parsed) or parsed < 0 or (field == 'dr' and parsed > 100) or (field != 'dr' and not parsed.is_integer()):
        raise ValueError(f'Некорректное значение {field}: {value}')
    return parsed if field == 'dr' else int(parsed)


def parse_export(data, filename):
    filename = PurePath(filename).name
    try:
        exported = datetime.strptime(filename, 'batch_analysis_%Y-%m-%d_%H-%M-%S.csv').replace(tzinfo=ZoneInfo('Europe/Moscow')).isoformat()
        text = data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
        reader = csv.DictReader(io.StringIO(text), delimiter='\t' if '\t' in text.splitlines()[0] else ',')
    except (ValueError, UnicodeError, IndexError):
        raise ValueError('Ожидается исходная выгрузка Ahrefs с датой в имени файла.') from None
    required = {'Target', 'Mode', 'Protocol', *COLUMNS.values()}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('В файле нет точных столбцов DR, Backlinks / All, Ref. domains / All.')
    sha = hashlib.sha256(data).hexdigest()
    rows = []
    seen = set()
    for line, row in enumerate(reader, 2):
        if row.get('Mode') != 'subdomains' or row.get('Protocol') != 'both':
            raise ValueError(f'Строка {line}: неподдерживаемая область отчёта Ahrefs.')
        domain = redirect_address(row.get('Target') or '', source=True)
        if domain in seen:
            raise ValueError(f'В файле повторяется домен {domain}.')
        seen.add(domain)
        rows.append({'domain': domain, **{field: number(row.get(column) or '', field) for field, column in COLUMNS.items()},
                     'target_mode': 'subdomains', 'protocol': 'both', 'exported_at': exported,
                     'source_file': filename, 'source_sha256': sha, 'source_url': 'https://app.ahrefs.com/batch-analysis'})
    if not rows:
        raise ValueError('Выгрузка Ahrefs не содержит доменов.')
    return rows


def read(db, domains):
    names = set()
    for value in domains:
        try:
            names.add(redirect_address(value, source=True))
        except ValueError:
            continue
    if not names:
        return {}
    records = db.scalars(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key.in_([key(d) for d in names])))
    return {row.value['domain']: row.value for row in records if row.value.get('domain') in names}


def network_metrics(db, site, state):
    from app.network_state import domain_name
    names = [*state.get('domains', []), *state.get('amp_domains', []), state.get('canon'),
             *(site.main_domain_history or []), *(site.alternate_domain_history or []), *(site.x_default_history or []),
             *state.get('history_overrides', {}), *state.get('domain_added_at', {}), *state.get('domain_removed_at', {})]
    return read(db, [name for value in names if (name := domain_name(value))])


def import_exports(db, report_id, files, *, apply=False):
    job = db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.id == str(report_id)).with_for_update())
    if not job or job.kind != 'maintenance_report' or job.payload.get('task_type') != 'ahrefs_batch_audit':
        raise ValueError('Не найден отчёт проверки Ahrefs.')
    entries = deepcopy((job.result or {}).get('entries', []))
    scope = {d for entry in entries for d in entry['domains']}
    sources, merged = [], {}
    for file in files:
        data = base64.b64decode(file['data_base64'], validate=True)
        rows = parse_export(data, file['filename'])
        sources.append({'filename': rows[0]['source_file'], 'sha256': rows[0]['source_sha256'], 'rows': len(rows), 'exported_at': rows[0]['exported_at'], 'source_url': rows[0]['source_url']})
        for row in rows:
            domain = row['domain']
            if domain not in scope:
                raise ValueError(f'Домен {domain} отсутствует в зафиксированном составе отчёта.')
            previous = merged.get(domain)
            if previous and previous['exported_at'] == row['exported_at'] and any(previous[k] != row[k] for k in COLUMNS):
                raise ValueError(f'Противоречивые данные одного экспорта: {domain}.')
            if not previous or row['exported_at'] > previous['exported_at']:
                merged[domain] = row
    now = datetime.now(timezone.utc).isoformat()
    saved = read(db, merged)
    updates = {d: {**r, 'imported_at': now} for d, r in merged.items()
               if d not in saved or saved[d].get('exported_at', '') < r['exported_at']}
    available = {**saved, **updates}
    summary = {'apply': apply, 'rows': sum(s['rows'] for s in sources), 'unique_domains': len(merged),
               'duplicates': sum(s['rows'] for s in sources) - len(merged), 'updated': len(updates),
               'missing_bl': sum(r['backlinks_all'] is None for r in merged.values()),
               'missing_rd': sum(r['referring_domains_all'] is None for r in merged.values()), 'sources': sources}
    if not apply:
        db.rollback()
        return summary
    for domain, values in updates.items():
        row = db.get(models.AutoReglueConfig, key(domain))
        if row is None:
            db.add(models.AutoReglueConfig(key=key(domain), value=values))
        else:
            row.value = values
    # Include earlier imports into this report, without pretending missing exports were checked.
    all_values = {**read(db, scope), **available}
    for entry in entries:
        metrics = {d: all_values[d] for d in entry['domains'] if d in all_values}
        entry['ahrefs'] = {'checked': len(metrics), 'total': len(entry['domains']), 'metrics': metrics,
                           'missing_bl': sum(r['backlinks_all'] is None for r in metrics.values()),
                           'missing_rd': sum(r['referring_domains_all'] is None for r in metrics.values())}
        entry['status'] = 'completed' if len(metrics) == len(entry['domains']) else 'waiting'
        entry['error'] = '' if entry['status'] == 'completed' else 'Ожидаются выгрузки Ahrefs для остальных доменов.'
        entry['facts'] = [{'label': 'Домены проверены', 'value': f"{len(metrics)} / {len(entry['domains'])}"},
                          {'label': 'Выгрузки', 'value': ', '.join(sorted({r['source_file'] for r in metrics.values()})) or 'Нет данных'},
                          {'label': 'Пустые BL / RD в экспорте', 'value': f"{sum(r['backlinks_all'] is None for r in metrics.values())} / {sum(r['referring_domains_all'] is None for r in metrics.values())}"},
                          {'label': 'План', 'value': 'Получить DR, Backlinks All и Referring domains All для каждого домена.'},
                          {'label': 'Результат', 'value': 'Метрики сохранены из CSV Ahrefs. Пустые значения сохранены без подмены нулями.' if metrics else 'Данные ещё не предоставлены.'}]
        if entry['status'] == 'completed':
            entry['finished_at'] = now
    completed = all(e['status'] == 'completed' for e in entries)
    job.result = {**job.result, 'entries': entries}
    previous_sources = {s['sha256']: s for s in job.payload.get('ahrefs_sources', [])}
    previous_sources.update({s['sha256']: s for s in sources})
    job.payload = {**job.payload, 'ahrefs_sources': list(previous_sources.values()),
                   'blocked_reason': '' if completed else 'Ожидаются остальные выгрузки Ahrefs.'}
    job.status = 'completed' if completed else 'running'
    job.finished_at = datetime.now(timezone.utc) if completed else None
    receipt_key = 'ahrefs-import:' + hashlib.sha256((str(report_id) + ''.join(sorted(s['sha256'] for s in sources))).encode()).hexdigest()
    receipt = db.get(models.AutoReglueConfig, receipt_key)
    if receipt is None:
        db.add(models.AutoReglueConfig(key=receipt_key, value={**summary, 'report_id': str(report_id), 'imported_at': now}))
    db.commit()
    return {**summary, 'report_status': job.status, 'projects_completed': sum(e['status'] == 'completed' for e in entries)}


if __name__ == '__main__':
    import argparse
    import sys
    from app.db import SessionLocal
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-id', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    with SessionLocal() as session:
        print(json.dumps(import_exports(session, args.report_id, json.load(sys.stdin)['files'], apply=args.apply), ensure_ascii=False))
