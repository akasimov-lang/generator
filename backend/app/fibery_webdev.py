"""Read-back verified Webdev tasks. Never close an engineering request on creation."""
from urllib.parse import quote

from app.fibery_client import FiberyClient, FiberyConflict, FiberyError, HOST, PROJECT_TYPE, normalized_document

TASK_TYPE = 'Alfasearch Config/Webdev Tasks'
CLOSED = {'Closed', 'Done', 'Archived', 'Cancelled'}


class WebdevClient(FiberyClient):
    def task(self, task_id):
        rows = self.query(TASK_TYPE, ['fibery/id', 'fibery/public-id', 'fibery/creation-date',
            'Alfasearch Config/Name', 'Alfasearch Config/Page URL',
            {'Alfasearch Config/SEO Project': ['fibery/id', 'fibery/public-id']},
            {'Alfasearch Config/Description': ['Collaboration~Documents/secret']},
            {'workflow/state': ['enum/name']}], ['=', ['fibery/id'], '$id'], {'$id': task_id})
        if len(rows) > 1:
            raise FiberyConflict('Неоднозначный идентификатор Webdev-задачи.')
        return rows[0] if rows else None

    def ensure_webdev_task(self, *, task_id, project_number, title, description, page_url):
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
            self.command('fibery.entity/create', {'type': TASK_TYPE, 'entity': {
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
