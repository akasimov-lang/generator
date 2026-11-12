"""Read-back verified Webdev tasks. Never close an engineering request on creation."""
from urllib.parse import quote

from app.fibery_client import FiberyClient, FiberyConflict, FiberyError, HOST, PROJECT_TYPE, normalized_document

TASK_TYPE = 'Alfasearch Config/Webdev Tasks'
CLOSED = {'Closed', 'Done', 'Archived', 'Cancelled'}


class WebdevClient(FiberyClient):
    def existing_domain_task(self, *, project_number, domain):
        """Find manual requests too; never modify their text, ownership or state."""
        rows = self.query(TASK_TYPE, ['fibery/id', 'Alfasearch Config/Name',
            {'workflow/state': ['enum/name']}],
            ['=', ['Alfasearch Config/SEO Project', 'fibery/public-id'], '$project'],
            {'$project': str(project_number)}, limit=1000)
        if len(rows) >= 1000:
            raise FiberyError('Список Webdev-задач неполон; создание дубля заблокировано.')
        expected = {f'{domain} не добавился в сетку'.casefold(),
                    f'{domain} — Title не совпадает с проектом'.casefold()}
        for row in rows:
            if ((row.get('Alfasearch Config/Name') or '').strip().casefold() not in expected
                    or (row.get('workflow/state') or {}).get('enum/name') in CLOSED):
                continue
            task = self.task(row['fibery/id'])
            if not task or (task.get('workflow/state') or {}).get('enum/name') in CLOSED:
                continue
            if str((task.get('Alfasearch Config/SEO Project') or {}).get('fibery/public-id')) != str(project_number):
                raise FiberyConflict('Привязка существующей Webdev-задачи изменилась.')
            secret = (task.get('Alfasearch Config/Description') or {}).get('Collaboration~Documents/secret')
            content = self.request('GET', '/api/documents/' + quote(secret, safe='') + '?format=md').get('content', '') if secret else ''
            return {'task_id': task['fibery/id'], 'public_id': str(task['fibery/public-id']),
                'project_number': str(project_number), 'title': task['Alfasearch Config/Name'],
                'url': HOST + '/favorites/Alfasearch_Config/Webdev_Tasks/' + str(task['fibery/public-id']),
                'page_url': task.get('Alfasearch Config/Page URL'),
                'created_at': task.get('fibery/creation-date'),
                'state': (task.get('workflow/state') or {}).get('enum/name'),
                'existing': True, 'description_read': bool(content.strip())}
        return None

    def task(self, task_id):
        rows = self.query(TASK_TYPE, ['fibery/id', 'fibery/public-id', 'fibery/creation-date',
            'Alfasearch Config/Name', 'Alfasearch Config/Page URL',
            {'Alfasearch Config/Priority': ['enum/name']},
            {'Alfasearch Config/SEO Project': ['fibery/id', 'fibery/public-id']},
            {'Alfasearch Config/Description': ['Collaboration~Documents/secret']},
            {'workflow/state': ['enum/name']}], ['=', ['fibery/id'], '$id'], {'$id': task_id})
        if len(rows) > 1:
            raise FiberyConflict('Неоднозначный идентификатор Webdev-задачи.')
        return rows[0] if rows else None

    def ensure_webdev_task(self, *, task_id, project_number, title, description, page_url, priority=None):
        projects = self.query(PROJECT_TYPE, ['fibery/id', 'fibery/public-id'],
            ['=', ['fibery/public-id'], '$id'], {'$id': str(project_number)})
        if len(projects) != 1:
            raise FiberyError(f'Не найден единственный проект Fibery #{project_number}.')
        project = projects[0]
        task = self.task(task_id)
        def validate(row):
            if (row.get('Alfasearch Config/SEO Project', {}).get('fibery/id') != project['fibery/id']
                    or row.get('Alfasearch Config/Name') != title
                    or row.get('Alfasearch Config/Page URL') != page_url):
                raise FiberyConflict('Название, URL или привязка Webdev-задачи изменены; перезапись остановлена.')
        if task:
            validate(task)
        else:
            states = self.query('workflow/state_' + TASK_TYPE, ['fibery/id', 'enum/name'], limit=50)
            states = {r['enum/name']: r['fibery/id'] for r in states}
            if 'New' not in states:
                raise FiberyError('В Fibery не найден статус New для Webdev-задачи.')
            extra = {}
            if priority:
                priorities = self.query('Alfasearch Config/Priority_WebDev/Webdev Tasks',
                    ['fibery/id', 'enum/name'], limit=30)
                selected = [p['fibery/id'] for p in priorities if p.get('enum/name') == priority]
                if len(selected) != 1:
                    raise FiberyError('В Fibery не найден приоритет Webdev-задачи.')
                extra['Alfasearch Config/Priority'] = {'fibery/id': selected[0]}
            self.command('fibery.entity/create', {'type': TASK_TYPE, 'entity': {
                **extra,
                'fibery/id': task_id, 'Alfasearch Config/Name': title,
                'Alfasearch Config/Page URL': page_url,
                'Alfasearch Config/SEO Project': {'fibery/id': project['fibery/id']},
                'workflow/state': {'fibery/id': states['New']},
            }})
            task = self.task(task_id)
        if not task or not task.get('fibery/public-id'):
            raise FiberyError('Создание Webdev-задачи ещё не подтверждено чтением.')
        validate(task)
        secret = (task.get('Alfasearch Config/Description') or {}).get('Collaboration~Documents/secret')
        if not secret:
            raise FiberyError('Описание Webdev-задачи пока недоступно.')
        path = '/api/documents/' + quote(secret, safe='') + '?format=md'
        current = self.request('GET', path).get('content', '')
        if normalized_document(current) != normalized_document(description):
            if current.strip():
                raise FiberyConflict('Описание Webdev-задачи изменено пользователем; перезапись остановлена.')
            self.request('PUT', path, {'content': description})
        if normalized_document(self.request('GET', path).get('content', '')) != normalized_document(description):
            raise FiberyError('Описание Webdev-задачи не подтверждено чтением.')
        verified = self.task(task_id)
        if not verified:
            raise FiberyError('Webdev-задача не найдена при контрольном чтении.')
        validate(verified)
        return {'task_id': task_id, 'public_id': str(verified['fibery/public-id']),
            'project_id': project['fibery/id'], 'project_number': str(project_number),
            'url': HOST + '/favorites/Alfasearch_Config/Webdev_Tasks/' + str(verified['fibery/public-id']),
            'title': title, 'page_url': page_url, 'created_at': verified.get('fibery/creation-date'),
            'state': (verified.get('workflow/state') or {}).get('enum/name'), 'description_verified': True}
