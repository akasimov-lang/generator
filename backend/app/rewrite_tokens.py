"""Keep functional markup and literal values intact during corrective rewrites."""
import re
from collections import Counter


def needed(feedback):
    return any(word in feedback.lower() for word in ('числовые факты', 'упоминания бренда', 'разметк', 'html', 'защищённые значения'))


def pack(items, brand):
    from app.page_content_tools import brand_pattern
    literals = (r'<a\b[^>]*>[\s\S]*?</a>|\{\{[\s\S]*?\}\}|'
                r'[\w.+-]+@[\w.-]+\.\w+|https?://[^\s<>]+|<[^>]+>')
    # Brand mentions may be added/removed. Hide only non-brand numeric literals.
    brand_spans = lambda text: [m.span() for m in brand_pattern(brand).finditer(text)] if brand and brand.casefold() != 'общие ключи' else []
    # Preserve separators inside a numeric expression as one literal. Protecting
    # "2 50" as two markers let the model join them into the different number 250.
    literals += r'|\d+(?:[ \u00a0\u202f]+\d+)*(?:[.,]\d+)*'
    tokens = {}
    output=[]
    for item in items:
        spans=brand_spans(item['text'])
        def protect(match):
            if any(start <= match.start() and match.end() <= end for start,end in spans):return match[0]
            marker = f'[[PP_KEEP_{len(tokens)}]]'
            tokens[marker] = match[0]
            return marker
        output.append({**item, 'text': re.sub(literals, protect, item['text'], flags=re.I)})
    return output, tokens


def unpack(items, values, tokens):
    if not tokens: return values
    expected = {item['id']: Counter(re.findall(r'\[\[PP_KEEP_\d+\]\]', item['text'])) for item in items}
    revised = []
    for value in values:
        text = value.get('text')
        if not isinstance(text, str) or Counter(re.findall(r'\[\[PP_KEEP_\d+\]\]', text)) != expected[value['id']]:
            raise ValueError('Нарушены защищённые значения или разметка. Сохраните каждый маркер ровно один раз.')
        revised.append({**value, 'text': re.sub(r'\[\[PP_KEEP_\d+\]\]', lambda m: tokens[m[0]], text)})
    return revised


INSTRUCTION = ('\nLiteral values and markup may be represented by [[PP_KEEP_N]] markers. '
               'Copy every marker exactly once into the SAME item, preserving tag order. '
               'Do not spell out or duplicate its value in addition to the marker. '
               'Use protected_values only to understand the text; rewrite the surrounding prose naturally.\n')
