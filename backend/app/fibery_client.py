"""Narrow Fibery writer for confirmed maintenance receipts, with read-back recovery."""
import re
import time
from urllib.parse import quote

import httpx

HOST = 'https://hzhz.fibery.io'
TASK_TYPE = 'Alfasearch Config/SEO Tasks'
PROJECT_TYPE = 'Alfasearch Config/SEO Projects'


class FiberyError(Exception):
    pass


class FiberyConflict(FiberyError):
    """An existing human edit must not be overwritten by an automatic retry."""


def normalized_document(value):
    return re.sub(r'\n{3,}', '\n\n', re.sub(r'(?m)^\* ', '- ', value.strip()))


class FiberyClient:
    def __init__(self, token):
        if not token:
            raise FiberyError('Ключ Fibery не настроен.')
        self.http = httpx.Client(base_url=HOST, headers={'Authorization': 'Token ' + token},
                                 timeout=35, follow_redirects=False)
        self.last = 0.0

    def close(self):
        self.http.close()

    def request(self, method, path, data=None):
        time.sleep(max(0, 1.5 - (time.monotonic() - self.last)))
        self.last = time.monotonic()
        try:
            response = self.http.request(method, path, json=data)
        except httpx.HTTPError:
            raise FiberyError('Fibery не подтвердил ответ. Следующая попытка начнётся с проверки существующей задачи.') from None
        if not 200 <= response.status_code < 300:
            raise FiberyError(f'Fibery: HTTP {response.status_code}.')
        try:
            return response.json() if response.content else None
        except ValueError:
            raise FiberyError('Fibery вернул некорректный ответ.') from None

    def command(self, name, args):
        result = self.request('POST', '/api/commands', [{'command': name, 'args': args}])
        if not isinstance(result, list) or len(result) != 1 or not result[0].get('success'):
            # Remote error bodies can contain entity values and credentials; never journal them.
            raise FiberyError('Fibery не подтвердил выполнение команды.')
        return result[0].get('result')

    def query(self, type_, fields, where=None, params=None, limit=2):
        query = {'q/from': type_, 'q/select': fields, 'q/limit': limit}
        if where is not None:
            query['q/where'] = where
        result = self.command('fibery.entity/query', {'query': query, 'params': params or {}})
        if not isinstance(result, list):
            raise FiberyError('Fibery не подтвердил результат поиска.')
        return result

    def task(self, task_id):
        rows = self.query(TASK_TYPE, ['fibery/id', 'fibery/public-id', 'Alfasearch Config/Name',
            {'Alfasearch Config/SEO Project': ['fibery/id', 'fibery/public-id']},
            {'Alfasearch Config/ТЗ': ['Collaboration~Documents/secret']},
            {'workflow/state': ['enum/name']}], ['=', ['fibery/id'], '$id'], {'$id': task_id})
        if len(rows) > 1:
            raise FiberyConflict('Найдено несколько задач с одним идентификатором.')
        return rows[0] if rows else None

    def ensure_task(self, *, task_id, project_number, title, description):
        projects = self.query(PROJECT_TYPE, ['fibery/id', 'fibery/public-id', 'Alfasearch Config/Name'],
            ['=', ['fibery/public-id'], '$id'], {'$id': str(project_number)})
        if len(projects) != 1:
            raise FiberyError(f'Не найден единственный SEO-проект Fibery #{project_number}.')
        project = projects[0]
        task = self.task(task_id)
        if task and (task.get('Alfasearch Config/SEO Project', {}).get('fibery/id') != project['fibery/id']
                     or task.get('Alfasearch Config/Name') != title):
            raise FiberyConflict('Существующая SEO-задача имеет другую привязку или название; автоматическая перезапись остановлена.')
        states = self.query('workflow/state_' + TASK_TYPE, ['fibery/id', 'enum/name'], limit=50)
        states = {row['enum/name']: row['fibery/id'] for row in states}
        if 'Closed' not in states or 'In Progress' not in states:
            raise FiberyError('Не найдены состояния SEO-задачи в Fibery.')
        if not task:
            # The caller stores this deterministic UUID before any external mutation.
            # If POST times out, the next attempt queries exactly this UUID, never creates a new one.
            self.command('fibery.entity/create', {'type': TASK_TYPE, 'entity': {
                'fibery/id': task_id, 'Alfasearch Config/Name': title,
                'Alfasearch Config/SEO Project': {'fibery/id': project['fibery/id']},
                'workflow/state': {'fibery/id': states['In Progress']},
            }})
            task = self.task(task_id)
        if not task or not task.get('fibery/public-id'):
            raise FiberyError('Создание SEO-задачи ещё не подтверждено чтением.')
        secret = (task.get('Alfasearch Config/ТЗ') or {}).get('Collaboration~Documents/secret')
        if not secret:
            raise FiberyError('Описание SEO-задачи ещё не доступно.')
        path = '/api/documents/' + quote(secret, safe='') + '?format=md'
        current = self.request('GET', path).get('content', '')
        if normalized_document(current) != normalized_document(description):
            if current.strip():
                raise FiberyConflict('Описание SEO-задачи изменено вне PagePilot; автоматическая перезапись остановлена.')
            self.request('PUT', path, {'content': description})
        if normalized_document(self.request('GET', path).get('content', '')) != normalized_document(description):
            raise FiberyError('Текст отчёта ещё не подтверждён чтением из Fibery.')
        if (task.get('workflow/state') or {}).get('enum/name') != 'Closed':
            self.command('fibery.entity/update', {'type': TASK_TYPE, 'entity': {
                'fibery/id': task_id, 'workflow/state': {'fibery/id': states['Closed']}}})
        verified = self.task(task_id)
        if not verified or (verified.get('workflow/state') or {}).get('enum/name') != 'Closed':
            raise FiberyError('Завершение SEO-задачи ещё не подтверждено.')
        if verified.get('Alfasearch Config/SEO Project', {}).get('fibery/id') != project['fibery/id'] or verified.get('Alfasearch Config/Name') != title:
            raise FiberyConflict('Название или привязка SEO-задачи изменились во время записи.')
        return {'task_id': task_id, 'public_id': str(verified['fibery/public-id']),
                'project_id': project['fibery/id'], 'project_number': str(project_number),
                'url': HOST + '/favorites/Alfasearch_Config/SEO_Tasks/' + str(verified['fibery/public-id']),
                'title': title, 'description_verified': True}
