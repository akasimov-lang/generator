"""Whole-page rewrite contracts: editorial freedom, unchanged technical behavior."""
from collections import Counter
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import math
import re


FOCUSES = (
    'Practical account access and the first steps, with concise explanations.',
    'Payment methods and account management, explaining the relevant conditions.',
    'Mobile access and navigation, distinguishing the browser from a native app.',
    'Games and choosing a format, with useful context rather than promotional filler.',
    'Bonuses and their conditions, explaining restrictions in connected prose.',
    'A balanced guide to the service, answering practical reader questions.',
)


def response_json(response):
    """Do not prose-clean JSON: escaped HTML quotes/newlines are significant."""
    from app.site_templates import parse_json
    candidates = response.get('candidates') or []
    if not candidates or not isinstance(candidates[0], dict): raise ValueError('Модель не вернула полный документ.')
    candidate = candidates[0]
    if candidate.get('finishReason') == 'MAX_TOKENS':
        raise ValueError('Ответ модели обрезан лимитом длины: полный рерайт не сохранён.')
    parts = (candidate.get('content') or {}).get('parts') or []
    raw = ''.join(part['text'] for part in parts if isinstance(part, dict)
                  and isinstance(part.get('text'), str) and not part.get('thought'))
    return parse_json(raw)


def group_briefs(site_ids, seed):
    """Stable, roughly half shorter/half longer; never reroll a saved draft."""
    ids = sorted({str(value) for value in site_ids})
    ordered = sorted(ids, key=lambda value: hashlib.sha256((str(seed)+':whole-page:'+value).encode()).digest())
    result = {}
    for index, site_id in enumerate(ordered):
        entropy = hashlib.sha256((str(seed)+':volume:'+site_id).encode()).digest()
        lower = index < (len(ordered)+1)//2
        ratio = (30 if lower else 115) + int.from_bytes(entropy[:4], 'big') % 56
        result[site_id] = {'rewrite_target_ratio': ratio/100,
                          'rewrite_focus': FOCUSES[index % len(FOCUSES)]}
    return result


def editorial_brief(draft):
    from app.page_word_count import page_word_count
    metadata = dict(draft.input_metadata or {})
    ratio = metadata.get('rewrite_target_ratio', 1.0)
    if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not math.isfinite(ratio) or not .3 <= ratio <= 1.7:
        raise ValueError('Объём полного рерайта должен составлять 30–170% исходного текста.')
    focus = metadata.get('rewrite_focus', 'Keep a balanced overview of the original page topics.')
    if not isinstance(focus, str) or not focus.strip() or len(focus) > 2000:
        raise ValueError('Укажите краткий редакционный акцент рерайта.')
    words = metadata.get('rewrite_source_word_count', page_word_count({'content': draft.input_content}))
    if type(words) is not int or words < 1:
        raise ValueError('Для полного рерайта нужен исходный текст страницы.')
    metadata.update(rewrite_target_ratio=float(ratio), rewrite_focus=focus.strip(), rewrite_source_word_count=words)
    draft.input_metadata = metadata
    return {'target_ratio': float(ratio), 'focus': focus.strip(), 'source_words': words,
            'target_words': max(1, round(words*ratio)), 'min_words': max(1, math.ceil(words*.3)),
            'max_words': max(1, math.floor(words*1.7))}


EDITORIAL_TAGS = {'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'small', 'mark',
                  'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td',
                  'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
INERT_TAGS = {'script', 'style', 'template', 'noscript', 'pre', 'code'}
VOID_TAGS = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
TRACKING_ID = re.compile(r'^rewrite-(?:source|added)-[\w-]+$')
TOKENS = re.compile(r'\{\{[\s\S]*?\}\}|\[[\w-]+(?:\s+[^\]]*)?\]|[\w.+-]+@[\w.-]+\.\w+|https?://[^\s<>]+')


class TechnicalMarkup(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.events, self.stack, self.inert = [], [], []
        self.feed(source); self.close()

    def handle_starttag(self, tag, attrs):
        attrs = [(k, v) for k, v in attrs if not (tag == 'p' and k == 'id' and TRACKING_ID.fullmatch(v or ''))]
        protected = bool(attrs) or tag not in EDITORIAL_TAGS or bool(self.inert)
        if protected: self.events.append(('start', tag, tuple(sorted(attrs))))
        if tag not in VOID_TAGS: self.stack.append((tag, protected))
        if tag in INERT_TAGS: self.inert.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS: self.handle_endtag(tag)

    def handle_endtag(self, tag):
        found = next((i for i in range(len(self.stack)-1, -1, -1) if self.stack[i][0] == tag), None)
        protected = self.stack[found][1] if found is not None else tag not in EDITORIAL_TAGS
        if protected: self.events.append(('end', tag))
        if found is not None: del self.stack[found:]
        if self.inert and tag == self.inert[-1]: self.inert.pop()

    def handle_data(self, text):
        if self.inert: self.events.append(('inert', text))
        else: self.events.extend(('token', value) for value in TOKENS.findall(text))

    def handle_entityref(self, name):
        if self.inert: self.events.append(('entity', name))

    def handle_charref(self, name):
        if self.inert: self.events.append(('char', name))

    def handle_comment(self, data): self.events.append(('comment', data))


def source_document(content):
    """Give legacy blocks stable IDs without modifying the saved input."""
    result = deepcopy(content)
    if not isinstance(result, dict) or not isinstance(result.get('blocks'), list):
        raise ValueError('Некорректный исходный документ.')
    used = {block.get('id') for block in result['blocks'] if isinstance(block, dict) and block.get('id')}
    for index, block in enumerate(result['blocks']):
        if not isinstance(block, dict): raise ValueError('Некорректный блок исходного документа.')
        if not block.get('id'):
            key = 'rewrite-source-block-'+str(index)
            while key in used: key += '-source'
            block['id'] = key; used.add(key)
    from app.full_content_rewrite import fields
    for index, path, source in list(fields(result)):
        class ParagraphIds(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=False)
                self.edits, self.hidden = [], []
                self.lines = [0, *[m.end() for m in re.finditer('\n', source)]]

            def handle_starttag(self, tag, attrs):
                if tag in INERT_TAGS: self.hidden.append(tag)
                if tag != 'p' or self.hidden or 'id' in dict(attrs): return
                line, col = self.getpos()
                offset = self.lines[line-1]+col
                key = hashlib.sha256((result['blocks'][index]['id']+repr(path)+str(offset)).encode()).hexdigest()[:16]
                self.edits.append((offset+2, ' id="rewrite-source-'+key+'"'))

            def handle_endtag(self, tag):
                if self.hidden and tag == self.hidden[-1]: self.hidden.pop()

        parser = ParagraphIds(); parser.feed(source)
        for offset, insertion in reversed(parser.edits): source = source[:offset]+insertion+source[offset:]
        target = result['blocks'][index]['data']
        for key in path[:-1]: target = target[key]
        target[path[-1]] = source
    return result


def block_contract(block):
    from app.full_content_rewrite import fields
    kind = block.get('type')
    if kind == 'shortcode': return deepcopy(block), []
    value = deepcopy(block)
    events = []
    editable_fields = list(fields({'blocks': [block]}))
    for _, path, text in editable_fields:
        events.extend(TechnicalMarkup(text).events)
        target = value['data']
        for key in path[:-1]: target = target[key]
        target[path[-1]] = ''
    # Paragraphs, lists and tables may be restructured. Unrecognized data,
    # styles and behavior remain protected even in those blocks.
    if kind in {'paragraph', 'list', 'table'}:
        for key in {'text', 'items', 'style', 'content', 'withHeadings', 'stretched'}:
            value.get('data', {}).pop(key, None)
        value['type'] = 'editorial'
    return value, events


def validate_document(before, after):
    if not isinstance(after, dict) or not isinstance(after.get('blocks'), list) or not after['blocks']:
        raise ValueError('Получен неполный документ страницы.')
    if {k:v for k,v in before.items() if k != 'blocks'} != {k:v for k,v in after.items() if k != 'blocks'}:
        raise ValueError('Изменены служебные настройки документа.')
    old = {block['id']: block for block in before['blocks']}
    if len(old) != len(before['blocks']): raise ValueError('Исходные ID блоков повторяются.')
    new = {}
    for block in after['blocks']:
        if (not isinstance(block, dict) or not isinstance(block.get('id'), str) or not block['id']
                or not isinstance(block.get('data'), dict) or not isinstance(block.get('type'), str)):
            raise ValueError('Некорректный блок результата.')
        if block['id'] in new: raise ValueError('ID блоков результата повторяются.')
        new[block['id']] = block
    protected_order = []
    for key, block in old.items():
        contract, events = block_contract(block)
        removable = block['type'] in {'paragraph','list','table'} and not events and not contract.get('data') and set(contract) <= {'id','type','data'}
        if key not in new:
            if not removable: raise ValueError('Удалён технический блок, ссылка или действие страницы.')
            continue
        new_contract, new_events = block_contract(new[key])
        if contract != new_contract or events != new_events:
            raise ValueError('Изменены техническая разметка, шорткод, ссылка или действие страницы.')
        if not removable: protected_order.append(key)
    if [block['id'] for block in after['blocks'] if block['id'] in protected_order] != protected_order:
        raise ValueError('Изменён порядок технических блоков страницы.')
    for key, block in new.items():
        if key in old: continue
        contract, events = block_contract(block)
        allowed = block['type'] in {'paragraph','list','table','header'}
        data = contract.get('data') or {}
        if block['type'] == 'header':
            allowed &= type(data.get('level')) is int and 2 <= data['level'] <= 6
            data = {k:v for k,v in data.items() if k not in {'text','level'}}
        if not allowed or events or data or set(contract)-{'id','type','data'}:
            raise ValueError('Новый блок содержит неподтверждённую разметку, ссылку или действие.')
    from app.full_heading_rewrite import all_targets
    if sum(h['level']==1 for h in all_targets(after)) != sum(h['level']==1 for h in all_targets(before)):
        raise ValueError('Количество H1 страницы изменилось.')


def paragraph_changes(before, after):
    """Identify added/deleted paragraphs, including plain HTML p without IDs."""
    def identities(content):
        from app.full_content_rewrite import fields
        result = []
        for block in content.get('blocks', []):
            if block.get('type') == 'paragraph': result.append('block:'+block['id'])
            for _, path, text in fields({'blocks':[block]}):
                class Paragraphs(HTMLParser):
                    def __init__(self):
                        super().__init__(); self.index = 0; self.hidden = []
                    def handle_starttag(self, tag, attrs):
                        if tag in INERT_TAGS: self.hidden.append(tag)
                        if tag == 'p' and not self.hidden:
                            attr = dict(attrs)
                            result.append('html:'+block['id']+':'+str(path)+':'+(attr.get('id') or str(self.index)))
                            self.index += 1
                    def handle_endtag(self, tag):
                        if self.hidden and tag == self.hidden[-1]: self.hidden.pop()
                Paragraphs().feed(text)
        return Counter(result)
    old, new = identities(before), identities(after)
    return {'added_ids': list((new-old).elements()), 'removed_ids': list((old-new).elements())}
