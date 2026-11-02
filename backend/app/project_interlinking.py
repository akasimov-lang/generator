"""Content links between the homepage and every internal Webdev page."""
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit


class ContentLinks(HTMLParser):
    excluded = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'script', 'style', 'template',
                'code', 'pre', 'noscript', 'nav', 'header', 'footer'}

    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.stack, self.links = [], []
        self.anchor, self.text = None, []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        if tag not in {'br', 'hr', 'img', 'input', 'wbr', 'meta', 'link', 'source'}:
            self.stack.append(tag)
        if tag == 'a':
            self.anchor = dict(attrs).get('href') if not self.excluded.intersection(self.stack) else None
            self.text = []

    def handle_data(self, data):
        if self.anchor is not None and not self.excluded.intersection(self.stack):
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == 'a':
            if self.anchor and ''.join(self.text).strip():
                self.links.append(self.anchor)
            self.anchor, self.text = None, []
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack) - self.stack[::-1].index(tag) - 1]


def body_fragments(page):
    content = page.get('content')
    if not isinstance(content, dict):
        return
    for block in content.get('blocks', []):
        if not isinstance(block, dict):
            continue
        kind, data = block.get('type'), block.get('data')
        if kind == 'faq' and isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and isinstance(item.get('answer'), str):
                    yield item['answer']
        if not isinstance(data, dict):
            continue
        if kind in {'paragraph', 'quote'} and isinstance(data.get('text'), str):
            yield data['text']
        elif kind == 'raw' and isinstance(data.get('html'), str):
            yield data['html']
        elif kind == 'table' and isinstance(data.get('content'), list):
            for row in data['content'][1 if data.get('withHeadings') else 0:]:
                if isinstance(row, list):
                    yield from (cell for cell in row if isinstance(cell, str))
        elif kind == 'list':
            def items(rows):
                for item in rows if isinstance(rows, list) else []:
                    if isinstance(item, str):
                        yield item
                    elif isinstance(item, dict):
                        if isinstance(item.get('content'), str):
                            yield item['content']
                        yield from items(item.get('items'))
            yield from items(data.get('items'))


def local_path(href, origin, page_path):
    if not isinstance(href, str) or not href.strip() or any(c in href for c in ('\\', '\x00', '\n', '\r')):
        return None
    try:
        url = urlsplit(urljoin(origin + page_path, href.strip()))
        base = urlsplit(origin)
        if url.scheme not in {'http', 'https'} or url.username or url.password:
            return None
        if url.hostname != base.hostname or url.port != base.port:
            return None
        return '/' + unquote(url.path).strip('/') if unquote(url.path).strip('/') else '/'
    except ValueError:
        return None


def interlinking_status(project, canon):
    data = project.get('data') if isinstance(project, dict) else None
    rows = data.get('pages') if isinstance(data, dict) else None
    result = {'complete': False, 'internal_count': 0, 'linked_from_home': 0,
              'linked_to_home': 0, 'missing_from_home': [], 'missing_to_home': [],
              'message': 'Нет данных для проверки перелинковки.'}
    if not isinstance(rows, list) or any(not isinstance(p, dict) for p in rows):
        return result
    base = str(canon or '').strip().rstrip('/')
    origin = base if '://' in base else 'https://' + base
    try:
        if not base or not urlsplit(origin).hostname:
            return result
    except ValueError:
        return result
    indexed = [(local_path(str(page.get('slug') or '/'), origin, '/'), page) for page in rows]
    homes = [page for path, page in indexed if path == '/']
    internal = [(path, page) for path, page in indexed if path and path != '/']
    result['internal_count'] = len(internal)
    if len(homes) != 1 or any(path is None for path, _ in indexed) or len({p for p, _ in indexed}) != len(indexed):
        result['message'] = 'Структура страниц неоднозначна; проверьте главную страницу и дубли URL.'
        return result
    if not internal:
        result['message'] = 'На сайте пока нет внутренних страниц.'
        return result

    def links(page, path):
        return {target for fragment in body_fragments(page)
                for href in ContentLinks(fragment).links
                if (target := local_path(href, origin, path)) is not None}

    outgoing = links(homes[0], '/')
    result['missing_from_home'] = [path for path, _ in internal if path not in outgoing]
    result['missing_to_home'] = [path for path, page in internal if '/' not in links(page, path)]
    result['linked_from_home'] = len(internal) - len(result['missing_from_home'])
    result['linked_to_home'] = len(internal) - len(result['missing_to_home'])
    result['complete'] = not result['missing_from_home'] and not result['missing_to_home']
    result['message'] = ('Перелинковка выполнена.' if result['complete'] else
                         'Не все страницы связаны с главной в обе стороны.')
    return result
