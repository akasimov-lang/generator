"""Count readable words in stored page blocks, excluding metadata and templates."""
import re
from html.parser import HTMLParser


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'template', 'noscript'}:
            self.hidden.append(tag)
        elif tag in {'br', 'p', 'div', 'li', 'td', 'th', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if self.hidden and tag == self.hidden[-1]:
            self.hidden.pop()
        if tag in {'p', 'div', 'li', 'td', 'th', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
            self.parts.append(' ')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def page_visible_text(page):
    content = page.get('content')
    if not isinstance(content, dict) or not isinstance(content.get('blocks'), list):
        return None
    from app.page_content_tools import text_fields
    chunks = []
    for block in content['blocks']:
        if not isinstance(block, dict):
            continue
        chunks.extend(text for _, text in text_fields(block))
        data = block.get('data')
        if isinstance(data, dict):
            # Webdev renders code blocks as HTML, including banners and CTA text.
            keys = {'raw': ('html',), 'code': ('code',), 'image': ('caption',), 'button': ('button',),
                    'plusMinus': ('values',)}.get(block.get('type'), ())
            for key in keys:
                value = data.get(key)
                if isinstance(value, str): chunks.append(value)
                elif key == 'values' and isinstance(value, list):
                    chunks.extend(item[k] for item in value if isinstance(item, dict)
                                  for k in ('plus', 'minus') if isinstance(item.get(k), str))
            if block.get('type') == 'quote' and not data.get('text') and isinstance(data.get('quote'), str):
                chunks.append(data['quote'])
    parser = VisibleText()
    parser.feed(' '.join(chunks))
    return ''.join(parser.parts)


def page_word_count(page):
    text = page_visible_text(page)
    return None if text is None else len(re.findall(r"\b[\w]+(?:['’\-][\w]+)*\b", text, flags=re.UNICODE))
