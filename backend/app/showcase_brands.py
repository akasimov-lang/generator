"""Brands actually placed in homepage showcase data, cards or ranking tables."""
from html import unescape
from html.parser import HTMLParser
import re
import unicodedata


def plain(value):
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', '', str(value or '')))).strip()


def brand_name(value):
    value = plain(value)
    value = re.sub(r'\s+logo\s*$', '', value, flags=re.I)
    value = re.sub(r'^logo\s+(?:of\s+)?', '', value, flags=re.I)
    value = re.sub(r'^#?\d+[.)]\s*', '', value)
    if not value or len(value) > 80 or '{{' in value or re.search(r'\b(icon|payment|payments|bonus|author|cashback|welcome|provider|list|tick)\b', value, re.I):
        return None
    if value.casefold() in {'logo', 'casino', 'kasyno', 'online casino', 'kasyno online', 'visa', 'mastercard', 'blik', 'bitcoin', 'ethereum', 'skrill', 'neteller', 'pln', 'rating'}:
        return None
    return value


def name_key(value):
    value = unicodedata.normalize('NFKC', value).casefold()
    return re.sub(r'[^\w]', '', re.sub(r'\s*casino\s*$', '', value))


def ranking_names(rows):
    if not isinstance(rows, list) or len(rows) < 2 or not isinstance(rows[0], list):
        return []
    labels = [plain(cell).casefold() for cell in rows[0]]
    column = next((i for i, cell in enumerate(labels) if cell in {'casino', 'casino name', 'nazwa kasyna', 'kasyno', 'brand', 'casino brand', 'название казино', 'бренд', 'kazino', 'kasino', 'anbieter'}), None)
    if column is None or not any(re.search(r'bonus|depo|licen|rating|ocena|offer|рейтинг|бонус', cell) for cell in labels):
        return []
    return [row[column] for row in rows[1:] if isinstance(row, list) and len(row) > column]


class ShowcaseHTML(HTMLParser):
    def __init__(self, source, *, showcase=False):
        super().__init__(convert_charrefs=True)
        self.showcase = showcase
        self.stack, self.names = [], []
        self.rows, self.row, self.cell = [], None, None
        self.feed(source)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        context = ' '.join([str(attrs.get('class', '')), str(attrs.get('id', ''))])
        if tag not in {'img', 'br', 'hr', 'input', 'meta', 'link', 'source', 'wbr'}:
            self.stack.append((tag, context))
        if tag == 'img' and not any(t in {'header', 'footer', 'nav'} for t, _ in self.stack):
            card = self.showcase or any(re.search(r'casino|showcase|vitrin|columnItem|rowItem|(?:offer|rank|rating|brand)[-_ ]?card', c, re.I) for _, c in self.stack)
            src = attrs.get('src', '')
            if card and not re.search(r'(?:bonus|tick|payment|cashback|star|check)[-_]?icon', src, re.I):
                if name := brand_name(attrs.get('alt')):
                    self.names.append(name)
        if tag == 'table':
            self.rows = []
        elif tag == 'tr':
            self.row = []
        elif tag in {'td', 'th'}:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {'td', 'th'} and self.cell is not None:
            if self.row is not None:
                self.row.append(''.join(self.cell))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(self.row); self.row = None
        elif tag == 'table':
            self.names.extend(ranking_names(self.rows)); self.rows = []
        if tag in [t for t, _ in self.stack]:
            last = max(i for i, (t, _) in enumerate(self.stack) if t == tag)
            self.stack = self.stack[:last]


def showcase_brands(project):
    data = project.get('data') if isinstance(project.get('data'), dict) else {}
    homes = [p for p in data.get('pages', []) if isinstance(p, dict) and str(p.get('slug') or '').strip('/') == '']
    if len(homes) != 1:
        return {'count': 0, 'brands': [], 'message': 'Не найдена однозначная главная страница.'}
    home = homes[0]
    definitions = {str(s.get('name', '')).removesuffix('.hbs'): s.get('data', '') for s in project.get('shortcodes', []) if isinstance(s, dict) and isinstance(s.get('data'), str)}
    names, sources, visited = [], [], set()

    def source(name):
        name = name.strip().removesuffix('.hbs')
        if name in visited or name.casefold() in {'header', 'footer', 'menu', 'navigation'}:
            return
        visited.add(name)
        markup = definitions.get(name)
        if markup is not None:
            sources.append((name, markup))
            for partial in re.findall(r'{{>\s*["\']?([\w .-]+?)["\']?\s*}}', markup):
                source(partial)

    for block in (home.get('content') or {}).get('blocks', []):
        if not isinstance(block, dict) or not isinstance(block.get('data'), dict):
            continue
        kind, value = block.get('type'), block['data']
        if kind == 'shortcode' and isinstance(value.get('shortcode'), str):
            source(value['shortcode'])
        elif kind == 'raw' and isinstance(value.get('html'), str):
            sources.append(('raw', value['html']))
        elif kind == 'table':
            names.extend(ranking_names(value.get('content')))
    layout = project.get('layout') or ''
    for partial in re.findall(r'{{>\s*["\']?([\w .-]+?)["\']?\s*}}', layout):
        source(partial)
    for banner in home.get('banners', []) if isinstance(home.get('banners'), list) else []:
        if isinstance(banner, str):
            source(banner)
    sources.append(('layout', layout))
    # Read only datasets referenced by a used template; unused logos and old
    # casino records in the project must never become displayed brands.
    for name, markup in sources:
        names.extend(ShowcaseHTML(markup, showcase=bool(re.search(r'casino|showcase|vitrin|ranking', name, re.I))).names)
        groups = re.findall(r'{{#each\s+(?:\.\./)?casinos\.([\w]+)\s*}}', markup)
        if '{{#each casinos}}' in markup:
            groups.append('')
        casinos = data.get('casinos')
        for group in groups:
            records = casinos.get(group, []) if group and isinstance(casinos, dict) else casinos
            for record in records if isinstance(records, list) else []:
                if isinstance(record, dict):
                    names.append(record.get('brand') or record.get('name'))
                elif isinstance(record, list):
                    names.extend(field.get('value') for field in record if isinstance(field, dict) and field.get('key') == 'brand')
    result, seen = [], set()
    for value in names:
        name = brand_name(value)
        if name and name_key(name) not in seen:
            result.append(name); seen.add(name_key(name))
    return {'count': len(result), 'brands': result, 'message': '' if result else 'Бренды витрины не найдены в сохранённом контенте.'}
