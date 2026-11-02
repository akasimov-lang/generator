"""Read homepage headings from the content AND the templates actually used by it.

This is an observer, not a Handlebars interpreter or a template editor. Unknown
expressions inside an H1 remain unresolved instead of being replaced with Title.
"""
import re
from html import escape
from html.parser import HTMLParser

VERSION = 2


class Headings(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.current = None
        self.ignored = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'template', 'noscript'}:
            self.ignored.append(tag)
        if self.ignored:
            return
        if tag == 'h1':
            self.current = []
        elif tag in {'br', 'p', 'div'} and self.current is not None:
            self.current.append(' ')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.ignored:
            if tag == self.ignored[-1]:
                self.ignored.pop()
            return
        if tag == 'h1' and self.current is not None:
            text = ' '.join(''.join(self.current).split())
            if text:
                self.items.append(text)
            self.current = None

    def handle_data(self, data):
        if self.current is not None and not self.ignored:
            self.current.append(data)


def from_html(markup):
    parser = Headings()
    parser.feed(str(markup or ''))
    parser.close()
    return parser.items


def extract(project):
    pages = (project.get('data') or {}).get('pages') or []
    homes = [p for p in pages if isinstance(p, dict) and str(p.get('slug') or '').strip('/') == '']
    if len(homes) != 1:
        return {'h1': '', 'h1_status': 'unavailable', 'h1_source': 'Главная страница не определена', 'headings': [], 'heading_version': VERSION}
    home = homes[0]
    definitions = {}
    for item in project.get('shortcodes') or []:
        if not isinstance(item, dict):
            continue
        data = item.get('data')
        if isinstance(data, dict):
            data = data.get('html') or data.get('code') or data.get('text')
        if isinstance(data, str):
            definitions[str(item.get('name') or '').removesuffix('.hbs')] = data
    context = {'page': home, 'settings': project.get('settings') or {}}
    partial = re.compile(r'{{>\s*["\']?([\w.\-]+)["\']?\s*}}')
    variable = re.compile(r'{{{?\s*([\w.]+)\s*}}}?')
    found = []
    unresolved = False

    def expand(markup, trail=()):
        markup = re.sub(r'{{!--.*?--}}|{{![^}]*}}', '', markup, flags=re.S)
        def include(match):
            name = match[1].removesuffix('.hbs')
            if name in trail or len(trail) >= 12:
                return ''
            return expand(definitions.get(name, ''), (*trail, name))
        return partial.sub(include, markup)

    def scan(markup, source):
        nonlocal unresolved
        def value(match):
            v = context
            for key in match[1].split('.'):
                v = v.get(key) if isinstance(v, dict) else None
            return escape(str(v)) if isinstance(v, (str, int, float)) else match[0]
        for text in from_html(variable.sub(value, expand(markup))):
            if '{{' in text or '}}' in text:
                unresolved = True
                continue
            found.append({'text': text, 'source': source})

    # Layout is scanned separately: renderedBlocks/pageBanners are scanned below,
    # not all definitions in the shortcode catalogue (many are unused/old).
    layout = project.get('layout')
    if isinstance(layout, str):
        scan(layout, 'layout')
    for name in home.get('banners') or []:
        if isinstance(name, str):
            scan(definitions.get(name.removesuffix('.hbs'), ''), 'banner:' + name)
    content = home.get('content') or {}
    if isinstance(content, str):
        scan(content, 'content')
    else:
        for index, block in enumerate(content.get('blocks') or []):
            data = block.get('data') or {}
            if not isinstance(data, dict):
                continue
            kind = block.get('type')
            if kind == 'shortcode':
                name = str(data.get('shortcode') or '').removesuffix('.hbs')
                scan(definitions.get(name, ''), 'shortcode:' + name)
            elif kind == 'header' and str(data.get('level')) == '1':
                scan('<h1>' + str(data.get('text') or '') + '</h1>', f'content:{index}')
            else:
                # Webdev renders code blocks as raw HTML, as well as html/text.
                for key in ('html', 'text', 'code'):
                    if isinstance(data.get(key), str):
                        scan(data[key], f'content:{index}')
    return {'h1': found[0]['text'] if found else '', 'headings': found,
            'h1_source': found[0]['source'] if found else '',
            'h1_status': 'found' if found else 'unresolved' if unresolved else 'not_found',
            'heading_version': VERSION}


def audit_key(site_id):
    return 'homepage-heading:' + str(site_id)


def audited_metadata(db, site, main, current=None):
    """Fill legacy preview display from a verified audit without changing its plan.

    Never use another Main's heading or replace a current template-aware snapshot.
    Execution and its signed plan/drafts are deliberately unaffected.
    """
    from app import models
    if (current or {}).get('heading_version', 0) >= VERSION:
        return current
    audit = db.get(models.AutoReglueConfig, audit_key(site.id))
    def host(v):
        return str(v or '').lower().removeprefix('https://').removeprefix('http://').strip('/')
    if not audit or not host(main) or host(audit.value.get('main')) != host(main) or host(site.cache_canon) != host(main):
        return current
    meta = audit.value.get('metadata') or {}
    if not meta.get('h1') and (current or {}).get('h1'):
        return current
    return {**(current or {}), **meta, 'title': (current or {}).get('title') or meta.get('title') or site.homepage_title or ''}
