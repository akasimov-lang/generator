"""One relative homepage link in a brand mention in an article paragraph."""
from copy import deepcopy
from html.parser import HTMLParser

from app.page_content_tools import Markup, brand_pattern
from app.site_brands import GENERAL


def project_link_brand(site):
    if site is None or getattr(site, 'site_type', None) == 'general':
        return None
    brand = (getattr(site, 'brand', None) or '').strip()
    return brand if brand and brand.casefold() != GENERAL.casefold() else None


class HomeAnchor(HTMLParser):
    def __init__(self, source, pattern):
        super().__init__(convert_charrefs=True)
        self.anchor = None
        self.text = []
        self.found = False
        self.pattern = pattern
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.anchor = dict(attrs).get('href')
            self.text = []

    def handle_data(self, data):
        if self.anchor is not None:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == 'a':
            if self.anchor == '/' and self.pattern.search(''.join(self.text)):
                self.found = True
            self.anchor = None


def link_brand_paragraph(content, brand):
    result = deepcopy(content)
    pattern = brand_pattern(brand)
    paragraphs = [block for block in result.get('blocks', []) if block.get('type') == 'paragraph'
                  and isinstance(block.get('data', {}).get('text'), str)]
    if any(HomeAnchor(block['data']['text'], pattern).found for block in paragraphs):
        return result, False
    for block in paragraphs:
        text = block['data']['text']
        for offset, segment, linked in Markup(text).segments:
            match = pattern.search(segment)
            if match and not linked:
                start, end = offset + match.start(), offset + match.end()
                block['data']['text'] = text[:start] + '<a href="/">' + text[start:end] + '</a>' + text[end:]
                return result, True
    raise ValueError(f'Нет свободного упоминания бренда «{brand}» в абзаце для ссылки на главную.')


def apply_brand_home_links(payload, site):
    brand = project_link_brand(site)
    if not brand:
        return payload
    result = deepcopy(payload)
    for page in result.get('pages', []):
        if not str(page.get('slug') or '').strip('/'):
            continue
        page['content'], _ = link_brand_paragraph(page.get('content') or {}, brand)
    return result
