"""One homepage link in the first quarter-to-half of a generated article."""
from copy import deepcopy
from html import escape
from html.parser import HTMLParser
import re
from app.page_content_tools import ParagraphMarkup, brand_pattern
from app.page_word_count import page_word_count
from app.project_interlinking import local_path


class HomeLinkTags(HTMLParser):
    def __init__(self, source, origin, path):
        super().__init__(convert_charrefs=False)
        self.source, self.origin, self.path = source, origin, path
        self.stack, self.remove = [], []
        self.lines = [0]
        self.lines.extend(m.end() for m in re.finditer('\n', source))
        self.feed(source)

    def position(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            home = local_path(dict(attrs).get('href'), self.origin, self.path) == '/'
            self.stack.append(home)
            if home:
                start = self.position()
                self.remove.append((start, start + len(self.get_starttag_text())))

    def handle_endtag(self, tag):
        if tag == 'a' and self.stack and self.stack.pop():
            start = self.position()
            self.remove.append((start, self.source.index('>', start) + 1))

    def cleaned(self):
        text = self.source
        for start, end in reversed(self.remove):
            text = text[:start] + text[end:]
        return text


def place_home_link(content, anchor, canon, path):
    result = deepcopy(content)
    origin = canon if '://' in canon else 'https://' + canon
    def clean(value):
        if isinstance(value, str): return HomeLinkTags(value, origin, path).cleaned()
        if isinstance(value, list): return [clean(v) for v in value]
        if isinstance(value, dict): return {k: clean(v) for k, v in value.items()}
        return value
    for block in result.get('blocks', []):
        # One contextual homepage link applies to article prose. Navigation,
        # breadcrumbs, buttons and raw template fragments are independent links.
        if isinstance(block, dict) and block.get('type') in {'paragraph', 'list', 'table', 'quote'}:
            block['data'] = clean(block.get('data'))
    total = page_word_count({'content': result}) or 0
    pattern = brand_pattern(anchor)
    candidates, positions, before = [], [], 0
    for block in result.get('blocks', []):
        if block.get('type') == 'paragraph' and isinstance(block.get('data', {}).get('text'), str):
            text = block['data']['text']
            for offset, segment, linked in ParagraphMarkup(text).segments:
                if linked: continue
                prefix = page_word_count({'content': {'blocks': [{'type': 'paragraph', 'data': {'text': text[:offset]}}]}}) or 0
                for match in pattern.finditer(segment):
                    word = before + prefix + len(re.findall(r'\b\w+\b', segment[:match.start()]))
                    if total * .25 <= word <= total * .5:
                        candidates.append((abs(word - total * .375), block, offset + match.start(), offset + match.end()))
                for match in re.finditer(r'\b\w+', segment):
                    word = before + prefix + len(re.findall(r'\b\w+\b', segment[:match.start()]))
                    positions.append((abs(word - total * .375), block, offset + match.start(), offset + match.start()))
        before += page_word_count({'content': {'blocks': [block]}}) or 0
    choices = candidates or positions
    if not choices:
        raise ValueError('Нет текстового абзаца для обязательной ссылки на главную.')
    _, block, start, end = min(choices, key=lambda c: c[0])
    text = block['data']['text']
    label = text[start:end] if end > start else escape(anchor)
    block['data']['text'] = text[:start] + '<a href="/">' + label + '</a>' + (' ' if start == end else '') + text[end:]
    return result
