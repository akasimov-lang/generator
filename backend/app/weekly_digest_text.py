"""Deterministic weekly prose from confirmed evidence, without database or AI calls.

Rows use ``project_state_reports.row``'s shape. Operations are dictionaries with
``id``, ``site_id``, ``payload`` (or ``request_payload``), ``types`` and optional
``status``. Missing status is accepted only for the already-confirmed export
format: a matching confirmed row event is still required. Runs contain ``id``,
``site_id``, ``status`` and ``plan``. No planned action counts as completed work.
"""
from collections import Counter
from datetime import datetime, timezone
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from app.domain_classification import registrable_root
from app.network_state import domain_name
from app.pilot_scope import country_key


FORMAT_VERSION = 1
MOSCOW = ZoneInfo('Europe/Moscow')
GROUPS = (
    ('fontan', 'Fontan'), ('lemon', 'Lemon'), ('pelican', 'Pelican'),
    ('betonred', 'BetOnRed'), ('general_pl', 'Общие ключи — Польша'),
    ('general_cz', 'Общие ключи — Чехия'),
)


def _brand(value):
    key = re.sub(r'[^\w]', '', str(value or '').casefold())
    return {'fontancasino': 'fontan', 'lemoncasino': 'lemon',
            'pelicancasino': 'pelican', 'betonredcasino': 'betonred'}.get(key, key)


def _group(row):
    brand = _brand(row.get('brand'))
    if brand in {'fontan', 'lemon', 'pelican', 'betonred'}:
        return brand
    if brand in {'общиеключи', 'generalkeywords'} or row.get('site_type') == 'general':
        geo = country_key(row.get('geo'))
        if geo in {'PL', 'CZ'}:
            return 'general_' + geo.lower()
    return None


def _path(value):
    path = urlsplit(str(value or '/')).path.strip('/')
    return '/' + path + '/' if path else '/'


def _events(row, operations):
    """Defend against duplicate exports and explicitly unconfirmed evidence."""
    result = {}
    pages = set()
    for event in sorted(row.get('events') or [], key=lambda e: (str(e.get('at') or ''), str(e.get('id') or ''))):
        if event.get('status') not in {None, 'confirmed', 'completed'}:
            continue
        if event.get('kind') == 'reglue':
            operation = operations.get(event.get('id'))
            if operation and operation.get('status') not in {None, 'confirmed'}:
                continue
            if operation and operation.get('site_id') not in {None, row.get('site_id')}:
                continue
            before, after = domain_name(event.get('before')), domain_name(event.get('after'))
            if not after or before == after:
                continue
        if event.get('kind') == 'page_added':
            path = _path(event.get('path'))
            if path in pages:
                continue
            pages.add(path)
        key = (event.get('kind'), event.get('id'))
        if not event.get('id'):
            key = (event.get('kind'), event.get('at'), event.get('path'), event.get('label'))
        result.setdefault(key, event)
    return list(result.values())


def _rows(values, operations):
    """A project can occur in several saved reports; count its events once."""
    merged = {}
    for row in values:
        sid = row.get('site_id')
        if not sid:
            continue
        if sid not in merged:
            merged[sid] = {**row, 'events': list(row.get('events') or [])}
            continue
        old = merged[sid]
        events = old['events'] + list(row.get('events') or [])
        newest = row if str(row.get('observed_at') or '') > str(old.get('observed_at') or '') else old
        merged[sid] = {**newest, 'events': events}
    result = []
    for row in merged.values():
        events = _events(row, operations)
        if events:
            result.append({**row, 'events': events})
    return result


def _current(rows):
    count = Counter()
    for row in rows:
        if row.get('state_error') or row.get('status') == 'partial':
            count['unverified'] += 1
            continue
        kind = row.get('main_type')
        count[kind if kind in {'drop', 'newreg'} else 'unknown'] += 1
        main = domain_name(row.get('main')).removeprefix('www.')
        root = registrable_root(main) or main
        count['subdomain'] += bool(main and root != main)
        count['inner'] += bool(row.get('fake_path') and row.get('fake_enabled', True))
        scheme = row.get('scheme') or ''
        has_alternates = 'с альтернейтами' in scheme if scheme else bool(row.get('alternate'))
        count['alternates'] += has_alternates
        count['without_alternates'] += not has_alternates
        if 'Canonical выключен' in scheme:
            count['canonical_disabled'] += 1
        else:
            href = re.search(r'''href\s*=\s*["']([^"']+)["']''', row.get('canonical') or '', re.I)
            destination = urlsplit(href.group(1)).path if href else None
            fake_path = row.get('fake_path') or ''
            if destination is not None and destination.rstrip('/') == '':
                count['canonical_root'] += 1
            elif destination is not None and fake_path and destination.rstrip('/') == fake_path.rstrip('/'):
                count['canonical_inner'] += 1
            else:
                count['canonical_other'] += 1
        count['redirect_projects'] += bool(row.get('redirects'))
    return {key: count[key] for key in (
        'drop', 'newreg', 'unknown', 'subdomain', 'inner', 'alternates',
        'without_alternates', 'canonical_root', 'canonical_inner',
        'canonical_disabled', 'canonical_other', 'redirect_projects', 'unverified',
    )}


def _statistics(rows, operations, runs):
    events = [(row, event) for row in rows for event in row['events']]
    counts = Counter(event.get('kind') for _, event in events)
    domain_counts = Counter()
    main_sites, combinations = set(), set()
    main_changes = 0
    for row, event in events:
        if event.get('kind') != 'reglue':
            continue
        operation = operations.get(event.get('id')) or {}
        if operation.get('site_id') not in {None, row['site_id']}:
            continue
        main_changes += 1
        main_sites.add(row['site_id'])
        payload = operation.get('payload') or operation.get('request_payload') or {}
        main = domain_name(event['after'])
        bare = main.removeprefix('www.')
        root = registrable_root(bare) or bare
        types = operation.get('types') or {}
        kind = next((types[key] for key in (main, bare, root, 'www.' + root)
                     if types.get(key) in {'drop', 'newreg'}), 'unknown')
        domain_counts[kind] += 1
        domain_counts['subdomain'] += bare != root
        transfer = payload.get('cross_network_transfer') or {}
        domain_counts['transfers'] += bool(transfer.get('source_site_id') and transfer.get('target_site_id')
                                            and transfer['source_site_id'] != transfer['target_site_id'])
        domain_counts['redirects_301'] += bool(payload.get('redirect_old_main')
                                              and (payload.get('redirects_after') or []) != (payload.get('redirects_before') or []))
        run = runs.get(payload.get('auto_run_id')) or {}
        if run.get('site_id') not in {None, row['site_id']}:
            continue
        plan = run.get('plan') or {}
        domain_counts['reserve_source'] += plan.get('balance_mode') == 'reserve_pool'
        if run.get('status') == 'completed' and plan.get('combination_id'):
            combinations.add(plan['combination_id'])
    heading_sites = {row['site_id'] for row, event in events if event.get('heading_changes')}
    text_events = [(row, event) for row, event in events if event.get('kind') == 'text']
    text_sites = {row['site_id'] for row, _ in text_events}
    body_text_sites = {row['site_id'] for row, event in text_events if event.get('text_changed')}
    category = lambda event, name: name in (event.get('categories') or [])
    def work_sites(kind):
        return len({row['site_id'] for row, event in events if event.get('kind') == kind or category(event, kind)})
    geos = {country_key(row.get('geo')) for row in rows}
    return {
        'projects': len(rows), 'main_changes': main_changes, 'main_projects': len(main_sites),
        'domain_changes': {key: domain_counts[key] for key in ('drop', 'newreg', 'unknown', 'subdomain', 'transfers', 'redirects_301', 'reserve_source')},
        'combinations_known': len(combinations),
        'heading_projects': len(heading_sites),
        'text_edits': len(text_events), 'text_projects': len(text_sites),
        'body_text_projects': len(body_text_sites),
        'fake_created': sum(event.get('kind') == 'fake_path' and bool(event.get('created')) for _, event in events),
        'fake_selected': sum(event.get('kind') == 'fake_path' and not event.get('created') for _, event in events),
        'pages_added': counts['page_added'],
        'pages_projects': len({row['site_id'] for row, event in events if event.get('kind') == 'page_added'}),
        'page_words': sum(event.get('words') or 0 for _, event in events if event.get('kind') == 'page_added'),
        'layout_projects': work_sites('layout'), 'showcase_projects': work_sites('showcase'),
        'menu_projects': work_sites('menu'), 'current': _current(rows),
        'common_geo': next(iter(geos)) if len(geos) == 1 else None,
    }


def aggregate(rows, operations=(), runs=(), manual_review_count=0):
    """Aggregate one bounded evidence period; callers select the period first."""
    opmap = {operation['id']: operation for operation in operations}
    runmap = {run['id']: run for run in runs}
    rows = _rows(rows, opmap)
    return {
        'format_version': FORMAT_VERSION,
        'overall': _statistics(rows, opmap, runmap),
        'groups': {key: {'label': label, **_statistics([row for row in rows if _group(row) == key], opmap, runmap)}
                   for key, label in GROUPS},
        'manual_review_count': max(0, int(manual_review_count or 0)),
    }


def _date(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not value.tzinfo:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(MOSCOW).strftime('%d.%m.%Y, %H:%M')


def _flag(geo):
    return ''.join(chr(127397 + ord(char)) for char in geo) + ' ' if geo and re.fullmatch('[A-Z]{2}', geo) else ''


def _count(number, one, few, many):
    rest = number % 100
    word = many if 11 <= rest <= 14 else one if number % 10 == 1 else few if 2 <= number % 10 <= 4 else many
    return f'{number} {word}'


def _projects(number):
    return _count(number, 'проекте', 'проектах', 'проектах')


def _scheme_text(stats):
    current = stats['current']
    unverified = current.get('unverified', 0)
    unknown_text = f"Проекты без подтверждённой текущей схемы: **{unverified}**."
    if unverified == stats['projects']:
        return unknown_text
    parts = [f"Текущие схемы: Main на дропах — **{current['drop']}**, на новорегах — **{current['newreg']}**"]
    if current['unknown']:
        parts.append(f"тип Main не установлен — **{current['unknown']}**")
    if current['subdomain']:
        parts.append(f"поддомены — **{current['subdomain']}** (входят в числа выше)")
    text = '; '.join(parts) + '. '
    text += f"С альтернейтами — **{current['alternates']}**, без них — **{current['without_alternates']}**. "
    text += f"Назначен внутряк — **{current['inner']}**. "
    text += f"Canonical главной страницы: на `/` — **{current['canonical_root']}**, на внутряк — **{current['canonical_inner']}**"
    if current['canonical_disabled']:
        text += f", выключен — **{current['canonical_disabled']}**"
    if current['canonical_other']:
        text += f", другое или не подтверждено — **{current['canonical_other']}**"
    return text + '.' + (' ' + unknown_text if unverified else '')


def render(stats, period_start, period_end, observed_at=None):
    """Render the saved format using facts only; never invent news or forecasts."""
    overall = stats['overall']; domains = overall['domain_changes']
    lines = ['**Новости PagePilot и массовые действия с проектами**', '',
             f"За эту неделю подтверждены работы на **{_projects(overall['projects'])}**. "
             f"Период: **{_date(period_start)} — {_date(period_end)} МСК**.", '',
             'За этот период выполнено:', '',
             f"- **{_count(overall['main_changes'], 'смена', 'смены', 'смен')} Main на {_projects(overall['main_projects'])}**.",
             f"- **{_count(domains['drop'], 'переклей', 'переклея', 'переклеев')} на дропы**, из них **{domains['reserve_source']} — из резервной базы**.",
             f"- **{_count(domains['newreg'], 'переклей', 'переклея', 'переклеев')} на новореги**.",
             f"- **{_count(domains['subdomain'], 'переклей', 'переклея', 'переклеев')} на поддомены** — входят в числа выше.",
             f"- **{_count(domains['redirects_301'], 'смена', 'смены', 'смен')} Main с установкой или изменением 301**.",
             f"- **Обновление Title/H1 на {_projects(overall['heading_projects'])}**.",
             f"- **{_count(overall['text_edits'], 'правка', 'правки', 'правок')} текста и метаданных на {_projects(overall['text_projects'])}**.",
             f"- **{_count(overall['fake_created'], 'замена', 'замены', 'замен')} внутренней страницы на уникальную**; назначений существующей внутренней страницы — **{overall['fake_selected']}**.",
             f"- **{_count(overall['pages_added'], 'опубликованная внутренняя страница', 'опубликованные внутренние страницы', 'опубликованных внутренних страниц')} на {_projects(overall['pages_projects'])}**.",
             f"- **{_count(domains['transfers'], 'перенос', 'переноса', 'переносов')} доменов между сетками**."]
    if domains['unknown']:
        lines.append(f"- У **{domains['unknown']}** подтверждённых смен Main тип целевого домена не установлен.")
    lines += ['', f"Разных комбинаций схем в сохранённых параметрах завершённых планов: **{overall['combinations_known']}**.", '',
              'Дополнительные действия пересекаются: один проект мог одновременно получить новый Main, 301, обновлённые заголовки, текст и новые страницы. '
              'Количество правок включает отдельные изменения и повторные правки; это не количество полностью переписанных страниц.', '',
              f"Работы с витринами подтверждены на **{_projects(overall['showcase_projects'])}**, "
              f"изменения вёрстки и шаблонов — **на {overall['layout_projects']}**, работы с меню — **на {overall['menu_projects']}**.", '',
              'Подробности по проектам и подтверждённые изменения собраны в [недельных отчётах PagePilot](/weekly-reports).']
    for key, label in GROUPS:
        group = stats['groups'][key]; domains = group['domain_changes']
        lines += ['', f"**{_flag(group['common_geo'])}{label} — проектов с работами: {group['projects']}**", '']
        if not group['projects']:
            lines.append('Подтверждённых работ за отчётный период пока нет.')
            continue
        lines += [f"- Смен Main — **{group['main_changes']} на {_projects(group['main_projects'])}**: "
                  f"на дропы — **{domains['drop']}**, на новореги — **{domains['newreg']}**.",
                  f"- Переклеев на поддомены — **{domains['subdomain']}**; смен Main с установкой или изменением 301 — **{domains['redirects_301']}**.",
                  f"- Переносов доменов между сетками — **{domains['transfers']}**; доменов из резервной базы — **{domains['reserve_source']}**.",
                  f"- Замен внутренней страницы на уникальную — **{group['fake_created']}**; назначений существующей — **{group['fake_selected']}**.",
                  f"- Новых опубликованных страниц — **{group['pages_added']} на {_projects(group['pages_projects'])}**.",
                  f"- Title/H1 обновлены на **{_projects(group['heading_projects'])}**; правок текста и метаданных — **{group['text_edits']} на {_projects(group['text_projects'])}**.",
                  f"- Работы с витринами — **на {_projects(group['showcase_projects'])}**, с вёрсткой — **на {group['layout_projects']}**, с меню — **на {group['menu_projects']}**."]
        if domains['unknown']:
            lines.append(f"- Тип целевого домена не установлен у **{domains['unknown']}** смен Main.")
        lines += ['', _scheme_text(group)]
    lines += ['', 'Текущие схемы показаны по сохранённым снимкам сеток; даты наблюдения могут отличаться. '
              'Недельные счётчики отражают подтверждённые изменения.'
              + (f" Сводка обновлена: {_date(observed_at)} МСК." if observed_at else ''), '',
              f"**Незавершённые задачи и задачи с ошибками: {stats['manual_review_count']} — требуют ручного разбора.**"]
    return '\n'.join(lines)
