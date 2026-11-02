"""One relative homepage link in a brand mention in an article paragraph."""
from copy import deepcopy
from html.parser import HTMLParser
from html import escape

from app.page_content_tools import ParagraphMarkup, brand_pattern
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
        self.home_tag = None
        self.source = source
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.anchor = dict(attrs).get('href')
            line, column = self.getpos()
            self.tag = (sum(len(row) for row in self.source.splitlines(keepends=True)[:line - 1]) + column, self.get_starttag_text(), attrs)
            self.text = []

    def handle_data(self, data):
        if self.anchor is not None:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == 'a':
            if self.anchor == '/' and self.pattern.search(''.join(self.text)):
                self.found = True
                self.home_tag = self.tag
            self.anchor = None


def link_brand_paragraph(content, brand, *, max_mentions=None):
    result = deepcopy(content)
    pattern = brand_pattern(brand)
    paragraphs = [block for block in result.get('blocks', []) if block.get('type') == 'paragraph'
                  and isinstance(block.get('data', {}).get('text'), str)]
    for block in paragraphs:
        anchor = HomeAnchor(block['data']['text'], pattern)
        if anchor.found:
            offset, tag, attrs = anchor.home_tag
            rel = next((v for k, v in attrs if k == 'rel'), '') or ''
            if set(rel.lower().split()) & {'nofollow', 'sponsored', 'ugc'}:
                clean = ' '.join(v for v in rel.split() if v.lower() not in {'nofollow', 'sponsored', 'ugc'})
                values = [(k, clean if k == 'rel' else v) for k, v in attrs if k != 'rel' or clean]
                replacement = '<a' + ''.join(' ' + k + ('="' + escape(v, quote=True) + '"' if v is not None else '') for k, v in values) + '>'
                text = block['data']['text']
                block['data']['text'] = text[:offset] + replacement + text[offset + len(tag):]
                return result, True
            return result, False
    count = 0
    for block in paragraphs:
        text = block['data']['text']
        for offset, segment, linked in ParagraphMarkup(text).segments:
            for match in pattern.finditer(segment):
                count += 1
                if max_mentions is not None and count > max_mentions:
                    break
                if not linked:
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
