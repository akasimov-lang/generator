from datetime import datetime, timezone

from app.weekly_digest_text import aggregate, render


def row(site_id='site-a', *, brand='Lemon Casino', geo='pl_PL', events=(), **changes):
    return {
        'site_id': site_id, 'project': site_id + '.test', 'brand': brand, 'geo': geo,
        'main': 'current.test', 'main_type': 'drop', 'fake_path': '/inner/',
        'fake_enabled': True, 'alternate': '<link rel="alternate" href="https://current.test/inner/" />',
        'canonical': '<link rel="canonical" href="https://current.test/" />',
        'scheme': 'Дроп; внутряк /inner/; с альтернейтами; Canonical на главную',
        'redirects': [], 'events': list(events), 'observed_at': '2026-11-07T04:00:00+00:00',
        **changes,
    }


def main_event(id='op-a', before='old.test', after='new.test', **changes):
    return {'id': id, 'kind': 'reglue', 'at': '2026-11-06T22:00:00+00:00',
            'before': before, 'after': after, **changes}


def operation(id='op-a', *, site_id='site-a', status='confirmed', payload=None, types=None):
    return {'id': id, 'site_id': site_id, 'status': status,
            'payload': payload or {}, 'types': types or {}}


def test_repeated_main_changes_are_operations_and_unique_projects_are_separate():
    events = [main_event(after='app.first.test'), main_event('op-b', 'app.first.test', 'second.test')]
    operations = [
        operation(types={'first.test': 'drop'}, payload={
            'auto_run_id': 'run-a', 'redirect_old_main': True,
            'redirects_before': [], 'redirects_after': [{'url': 'old.test', 'value': 'app.first.test'}],
            'cross_network_transfer': {'source_site_id': 'donor', 'target_site_id': 'site-a'},
        }),
        operation('op-b', types={'second.test': 'newreg'}, payload={
            'auto_run_id': 'run-b', 'redirect_old_main': True,
            'redirects_before': [{'url': 'old.test', 'value': 'first.test'}],
            'redirects_after': [{'url': 'old.test', 'value': 'first.test'}],
        }),
    ]
    runs = [
        {'id': 'run-a', 'site_id': 'site-a', 'status': 'completed', 'plan': {'balance_mode': 'reserve_pool', 'combination_id': 'one'}},
        {'id': 'run-b', 'site_id': 'site-a', 'status': 'running', 'plan': {'combination_id': 'two'}},
    ]
    overall = aggregate([row(events=events)], operations, runs)['overall']
    assert overall['projects'] == overall['main_projects'] == 1
    assert overall['main_changes'] == 2
    assert overall['domain_changes'] == {'drop': 1, 'newreg': 1, 'unknown': 0, 'subdomain': 1,
                                         'transfers': 1, 'redirects_301': 1, 'reserve_source': 1}
    assert overall['combinations_known'] == 1


def test_unconfirmed_failed_noop_and_wrong_project_operations_never_count():
    events = [main_event(), main_event('op-b'), main_event('op-c', 'same.test', 'same.test'),
              main_event('op-d', status='failed')]
    operations = [operation(status='failed'), operation('op-b', site_id='someone-else')]
    result = aggregate([row(events=events)], operations)
    assert result['overall']['projects'] == 0
    assert result['overall']['main_changes'] == 0


def test_overlapping_report_exports_and_page_retries_do_not_double_count():
    first = row(events=[
        main_event(),
        {'id': 'page-one', 'kind': 'page_added', 'path': '/account', 'words': 900, 'at': '2026-11-06T20:00:00Z'},
    ])
    second = row(events=[
        main_event(),
        {'id': 'page-two', 'kind': 'page_added', 'path': 'https://changed.test/account/?tracking=one', 'words': 1000, 'at': '2026-11-06T21:00:00Z'},
    ], observed_at='2026-11-07T04:30:00+00:00', main='later.test')
    overall = aggregate([first, second], [operation(types={'new.test': 'drop'})])['overall']
    assert overall['projects'] == overall['main_changes'] == 1
    assert overall['pages_added'] == overall['pages_projects'] == 1
    assert overall['page_words'] == 900


def test_metadata_only_edits_count_headings_but_not_body_rewrites():
    event = {'id': 'title', 'kind': 'text', 'text_changed': False,
             'metadata': ['title'], 'heading_changes': [{'field': 'title', 'before': 'Old', 'after': 'New'}]}
    stats = aggregate([row(events=[event])]); overall = stats['overall']
    assert overall['text_edits'] == overall['text_projects'] == overall['heading_projects'] == 1
    assert overall['body_text_projects'] == 0
    assert overall['main_changes'] == 0
    text = render(stats, '2026-11-01T21:00:00Z', '2026-11-07T04:00:00Z')
    assert 'подтверждены работы на **1 проекте**' in text
    assert '**1 правка текста и метаданных на 1 проекте**' in text


def test_brand_and_country_groups_do_not_mix_general_and_monobrand_projects():
    event = {'id': 'layout', 'kind': 'layout', 'categories': ['showcase', 'menu']}
    result = aggregate([
        row('lemon', brand='Lemon Casino', events=[event]),
        row('pelican', brand='Pelican Casino', events=[event]),
        row('pl', brand='Общие ключи', geo='PL-pl', events=[event]),
        row('cs', brand='Общие ключи', geo='cs_CZ', events=[event]),
        row('cz', brand='Общие ключи', geo='cz', events=[event]),
        row('foreign', brand='Общие ключи', geo='de_DE', events=[event]),
        row('empty', brand='Fontan', events=[]),
    ])
    assert result['overall']['projects'] == 6
    assert result['groups']['lemon']['projects'] == 1
    assert result['groups']['pelican']['projects'] == 1
    assert result['groups']['general_pl']['projects'] == 1
    assert result['groups']['general_cz']['projects'] == 2
    assert result['groups']['fontan']['projects'] == 0
    assert result['overall']['layout_projects'] == result['overall']['showcase_projects'] == result['overall']['menu_projects'] == 6


def test_current_schemes_are_not_confused_with_weekly_changes_or_disabled_markup():
    event = {'id': 'menu', 'kind': 'menu'}
    current = aggregate([
        row('root', events=[event]),
        row('inner', events=[event], main='www.root.test', main_type='newreg',
            canonical='<link rel="canonical" href="https://www.root.test/inner/" />'),
        row('off', events=[event], main='mobile.root.test', main_type='unknown',
            fake_enabled=False, alternate='', scheme='Без схем; без альтернейтов; Canonical выключен'),
    ])['overall']
    assert current['main_changes'] == 0
    assert current['current']['drop'] == current['current']['newreg'] == current['current']['unknown'] == 1
    assert current['current']['subdomain'] == 1
    assert current['current']['inner'] == 2
    assert current['current']['alternates'] == 2
    assert current['current']['canonical_root'] == current['current']['canonical_inner'] == current['current']['canonical_disabled'] == 1


def test_missing_type_remains_unknown_instead_of_guessing_from_the_zone():
    stats = aggregate([row(events=[main_event(after='looks-like-drop.com')])])
    assert stats['overall']['domain_changes']['unknown'] == 1
    assert stats['overall']['domain_changes']['drop'] == 0
    assert stats['overall']['current']['drop'] == 1


def test_unverified_snapshot_does_not_inflate_current_schemes_or_manual_review():
    event = {'id': 'menu', 'kind': 'menu'}
    verified = row('verified', events=[event])
    incomplete = row('incomplete', events=[event], status='partial',
                     state_error='Нет полного сохранённого снимка сетки.',
                     main='mobile.partial.test', main_type='newreg',
                     alternate='', scheme='Без альтернейтов; Canonical выключен')
    stats = aggregate([verified, incomplete], manual_review_count=8)
    expected = aggregate([verified])['overall']['current']
    assert stats['overall']['current'] == {**expected, 'unverified': 1}
    assert stats['overall']['projects'] == stats['overall']['menu_projects'] == 2
    assert stats['groups']['lemon']['current']['unverified'] == 1
    assert stats['manual_review_count'] == 8


def test_only_unverified_snapshot_renders_unknown_without_asserting_disabled_scheme():
    stats = aggregate([row(events=[{'id': 'layout', 'kind': 'layout'}],
                           status='partial', state_error='Нет сохранённого снимка.',
                           main_type='unknown', fake_path='', alternate='', canonical='',
                           scheme='Без альтернейтов; Canonical выключен')])
    text = render(stats, '2026-11-01T21:00:00Z', '2026-11-07T04:00:00Z')
    assert stats['overall']['current']['unknown'] == 0
    assert stats['overall']['current']['canonical_disabled'] == 0
    assert stats['overall']['current']['without_alternates'] == 0
    assert 'Проекты без подтверждённой текущей схемы: **1**.' in text
    assert 'Текущие схемы: Main' not in text
    assert 'без них —' not in text
    assert text.endswith('**Незавершённые задачи и задачи с ошибками: 0 — требуют ручного разбора.**')


def test_renderer_preserves_weekly_format_moscow_dates_and_one_review_total():
    stats = aggregate([], manual_review_count=8)
    text = render(stats, datetime(2026, 11, 1, 21, tzinfo=timezone.utc),
                  '2026-11-07T04:00:00Z', observed_at='2026-11-07T04:01:00Z')
    assert text.startswith('**Новости PagePilot и массовые действия с проектами**')
    assert '02.11.2026, 00:00 — 07.11.2026, 07:00 МСК' in text
    assert 'Сводка обновлена: 07.11.2026, 07:01 МСК.' in text
    assert 'Текущие схемы показаны по сохранённым снимкам сеток' in text
    assert 'Проверка:' not in text
    assert text.count('Подтверждённых работ за отчётный период пока нет.') == 6
    assert text.count('требуют ручного разбора') == 1
    assert text.endswith('**Незавершённые задачи и задачи с ошибками: 8 — требуют ручного разбора.**')
