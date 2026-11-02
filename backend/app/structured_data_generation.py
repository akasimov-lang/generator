"""Conservative JSON-LD from verified page metadata; never invent business facts."""
from html import unescape
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlsplit, urlunsplit


def canonical_url(value):
    value = str(value or '').strip()
    url = urlsplit(value if '://' in value else 'https://' + value)
    if (url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password
            or url.port or url.query or url.fragment or '{{' in value or re.search(r'[\s<>"\\]', value)):
        raise ValueError('Нужен подтверждённый абсолютный canonical URL страницы.')
    host = url.hostname.encode('idna').decode('ascii').lower()
    if '.' not in host or not re.fullmatch(r'[a-z0-9.-]+', host):
        raise ValueError('Некорректный домен canonical URL.')
    return urlunsplit((url.scheme, host, url.path or '/', '', ''))


def language_tag(value):
    value = str(value or '').strip().replace('_', '-')
    if not value: return None
    if not re.fullmatch(r'[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*', value):
        raise ValueError('Некорректный язык страницы для JSON-LD.')
    parts = value.split('-')
    return '-'.join([parts[0].lower(), *(part.upper() if len(part) == 2 else part.title() if len(part) == 4 else part for part in parts[1:])])


def build(*, url, title, description='', language='', website_name=None):
    """Describe only WebSite and WebPage, using current canonical and metadata."""
    url = canonical_url(url)
    title = unescape(str(title or '')).strip()
    if not title: raise ValueError('У страницы отсутствует Title; генерация разметки остановлена.')
    root = urlunsplit((*urlsplit(url)[:2], '/', '', ''))
    website = {'@type':'WebSite', '@id':root+'#website', 'url':root, 'name':unescape(str(website_name or title)).strip()}
    page = {'@type':'WebPage', '@id':url+'#webpage', 'url':url, 'name':title, 'isPartOf':{'@id':website['@id']}}
    if str(description or '').strip(): page['description'] = unescape(str(description)).strip()
    if code := language_tag(language):
        website['inLanguage'] = code; page['inLanguage'] = code
    return {'@context':'https://schema.org', '@graph':[website, page]}


def from_source(source):
    """Capture format: native home/head/settings, plus verified cached language."""
    page = source.get('home') or {}
    head = source.get('head') or {}
    settings = source.get('settings') or {}
    # Use page metadata first. Native shared head is only a fallback for absent
    # page values; neither shortcodes nor inferred brand claims become facts.
    title = page.get('title') or head.get('title')
    description = page.get('description') or head.get('description') or ''
    language = page.get('language') or source.get('language') or settings.get('language') or settings.get('lang') or ''
    if not isinstance(language, str): language = ''
    return build(url=source.get('canonical_url') or settings.get('canon'), title=title,
                 description=description, language=language)


def build_site(*, url, name, description='', language=''):
    """A site-wide head must not describe every inner page as the homepage."""
    website = build(url=url, title=name, language=language)['@graph'][0]
    if str(description or '').strip(): website['description'] = unescape(str(description)).strip()
    return {'@context':'https://schema.org', '@graph':[website]}


def site_markup(value, *, dynamic_main=False):
    """Only URL/id use native Main interpolation; descriptions remain literal."""
    from copy import deepcopy
    data = deepcopy(value)
    if dynamic_main:
        for node in data.get('@graph', []):
            if node.get('@type') != 'WebSite': raise ValueError('Глобальный шаблон поддерживает только WebSite.')
            root = canonical_url(node['url'])
            if urlsplit(root).path != '/': raise ValueError('WebSite должен ссылаться на корень сайта.')
            for key in ('url', '@id'):
                if not node.get(key, '').startswith(root): raise ValueError('Адрес WebSite не принадлежит текущему Main.')
                node[key] = 'https://{{settings.canon}}/' + node[key][len(root):]
    return serialize(data, script=True)


def serialize(value, *, script=False):
    """Escape HTML script delimiters without changing the JSON string values."""
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    payload = payload.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    return '<script type="application/ld+json">\n'+payload+'\n</script>' if script else payload


class JsonLdParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.active = False; self.parts = []; self.documents = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'script':
            self.active = dict(attrs).get('type', '').lower() == 'application/ld+json'
            self.parts = []
    def handle_data(self, data):
        if self.active: self.parts.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == 'script' and self.active:
            self.documents.append(json.loads(''.join(self.parts)))
            self.active = False


def documents(markup):
    parser = JsonLdParser(); parser.feed(markup); parser.close()
    if parser.active: raise ValueError('Незакрытый JSON-LD script.')
    return parser.documents
