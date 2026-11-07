"""Shared editorial brief and lossless layout changes for reviewed rewrites."""
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import re
from app.content_metrics import target_percent

VERSION = 2
NUMERIC_CONDITIONS = (
    'Keep numerical offer conditions unchanged: bonus/deposit/withdrawal amounts, percentages, '
    'free-spin counts, wagering multipliers, minimums, maximums, fees and validity/processing periods. '
    'Preserve each value together with its currency or unit, applicable condition and qualifiers such as '
    '"up to", "from" and "at least". Do not swap values between conditions, round them, convert currencies, '
    'spell a number out or substitute a competitor offer. For example, 100% up to 500 PLN with wagering '
    'x35 must retain all three conditions. Rewrite the surrounding prose freely; this rule protects '
    'numerical conditions, not the wording, sentence order or original explanation. '
)
INSTRUCTIONS = (
    'Rewrite naturally in the original language. New meanings, angles and explanations are allowed in '
    'rewritten and newly added paragraphs when relevant to the page and supplied brand/GEO knowledge. '
    'Preserve the main topic and do not contradict the offer; sentence-by-sentence equivalence is not required. '
    + NUMERIC_CONDITIONS +
    'Some paragraphs should be fully rephrased on the same topic at roughly the same length. '
    'Use lists or tables only when they clarify the material. Never create a list with fewer than 2 items. '
    'Add at most 2 new lists per project, including tables converted to lists. '
    'New tables must have at most 5 columns and at least 5 substantive data rows, excluding a header. '
    'Never invent facts to fill a table. Appropriate semantic emojis in tables are allowed, not required. '
    'Comparable lists may become tables and field/value tables may become lists, preserving all information. '
    'For branded CTA buttons use a short label: brand + registration, brand + GEO, brand + login, brand + official site, or a localized "Get bonus" label '
    '(localized to the page language and matching the actual button action; official site means opening the brand website). Avoid long directions such as '
    '"Go to the registration form". Preserve every button destination and action. '
    'Any requested uniqueness percentage is a rewriting target, never a fabricated measurement. '
)


def brief(draft):
    metadata = dict(draft.input_metadata or {})
    policy = metadata.get('rewrite_policy')
    if not isinstance(policy, dict) or policy.get('version') != VERSION:
        policy = {'version': VERSION, 'uniqueness_target_percent': target_percent(draft.id, draft.site_id),
                  'new_lists_max': 2, 'list_items_min': 2, 'table_columns_max': 5,
                  'table_data_rows_min': 5, 'semantic_table_emojis': True}
        draft.input_metadata = {**metadata, 'rewrite_policy': policy}
    return policy


def prompt(policy):
    return '\n' + INSTRUCTIONS + f"Aim for about {policy['uniqueness_target_percent']}% rephrasing against the supplied version; meaning and factual accuracy take priority. Keep the required output schema.\n"


class Structure(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.lists=[]; self.stack=[]; self.tables=[]; self.table_stack=[]; self.hidden=[];self.text=[]
        self.feed(source); self.close()

    def handle_starttag(self, tag, attrs):
        if tag in {'script','style','template','noscript'}: self.hidden.append(tag)
        if self.hidden:return
        if tag in {'ul','ol'}: self.stack.append(0)
        elif tag=='li' and self.stack:self.stack[-1]+=1
        if tag=='table':self.table_stack.append({'rows':[],'in_header':False})
        elif tag=='thead' and self.table_stack:self.table_stack[-1]['in_header']=True
        elif tag=='tr' and self.table_stack:self.table_stack[-1]['rows'].append({
            'width':0,'header':True,'header_region':self.table_stack[-1]['in_header'],'substantive':False})
        elif tag in {'td','th'} and self.table_stack and self.table_stack[-1]['rows']:
            row=self.table_stack[-1]['rows'][-1]
            try:width=int(dict(attrs).get('colspan','1'))
            except (ValueError,TypeError):width=99
            row['width']+=max(1,width);row['header']&=tag=='th'

    def handle_data(self, text):
        if self.hidden:return
        self.text.append(text)
        if text.strip() and self.table_stack and self.table_stack[-1]['rows']:
            self.table_stack[-1]['rows'][-1]['substantive']=True

    def handle_endtag(self, tag):
        if self.hidden:
            if tag==self.hidden[-1]:self.hidden.pop()
            return
        if tag in {'ul','ol'} and self.stack:self.lists.append(self.stack.pop())
        if tag=='thead' and self.table_stack:self.table_stack[-1]['in_header']=False
        if tag=='table' and self.table_stack:self.tables.append(self.table_stack.pop())


def block_lists(block):
    if block.get('type')!='list':return []
    def walk(items):
        if not isinstance(items,list):raise ValueError('Некорректный список.')
        result=[len(items)]
        for item in items:
            if isinstance(item,dict) and item.get('items'):result+=walk(item['items'])
        return result
    return walk(block.get('data',{}).get('items',[]))


def markup_fields(block):
    """Inspect editable text fields, including inline HTML in paragraphs and lists."""
    from app.full_content_rewrite import fields
    for _,path,value in fields({'blocks':[block]}):
        if re.search(r'<[A-Za-z][^>]*>',value):yield path,value


def markup(block):
    return '\n'.join(value for _,value in markup_fields(block))


def substantive(value):
    return isinstance(value,str) and bool(''.join(Structure(value).text).strip())


def new_list_count(before, after):
    old={b.get('id',str(i)):b for i,b in enumerate(before.get('blocks',[]))}
    total=0
    for i,b in enumerate(after.get('blocks',[])):
        previous=old.get(b.get('id',str(i)),{})
        count=lambda v:len(block_lists(v))+len(Structure(markup(v)).lists)
        total+=max(0,count(b)-count(previous))
    return total


def validate(before, after):
    old={b.get('id',str(i)):b for i,b in enumerate(before.get('blocks',[]))}
    for i,b in enumerate(after.get('blocks',[])):
        prior=old.get(b.get('id',str(i)),{})
        structure=Structure(markup(b))
        if any(n<2 for n in block_lists(b)+structure.lists+structure.stack):
            raise ValueError('В каждом списке должно быть не менее 2 пунктов.')
        if b.get('type')=='table' and prior.get('type')!='table':
            data=b.get('data') or {};rows=data.get('content') or []
            body=rows[1:] if data.get('withHeadings') else rows
            count=sum(isinstance(row,list) and any(substantive(cell) for cell in row) for row in body)
            if count<5 or any(not isinstance(row,list) or not 1<=len(row)<=5 for row in rows):
                raise ValueError('Новая таблица: не более 5 столбцов и не менее 5 содержательных строк.')
        old_tables=Structure(markup(prior)).tables
        for n,table in enumerate(structure.tables):
            if n<len(old_tables):continue
            if sum(not row['header'] and not row['header_region'] and row['substantive'] for row in table['rows'])<5 or any(not 1<=row['width']<=5 for row in table['rows']):
                raise ValueError('Новая HTML-таблица: не более 5 столбцов и не менее 5 содержательных строк.')
    if new_list_count(before,after)>2:raise ValueError('Разрешено добавить не более 2 новых списков на проект.')


def normalize_singletons(content):
    changes=[]
    def item_text(item):
        if isinstance(item,str):return item
        if not isinstance(item,dict) or set(item)-{'content','items','meta'} or item.get('meta'):return None
        if not isinstance(item.get('content'),str):return None
        children=[item_text(child) for child in item.get('items',[])]
        return '<br/>'.join([item['content'],*children]) if all(text is not None for text in children) else None
    for index,b in enumerate(content.get('blocks',[])):
        data=b.get('data') or {};key=b.get('id',str(index))
        if b.get('type')=='list' and len(data.get('items',[]))<=1:
            single=item_text(data['items'][0]) if data.get('items') else ''
            if single is not None:
                b.update(type='paragraph',data={'text':single})
                changes.append({'block_id':key,'from':'list','to':'paragraph','reason':'single_item' if single else 'empty_list'})
        for path,source in list(markup_fields(b)):
            # Only a plain one-item list can be unwrapped automatically. Nested
            # or malformed cases are rejected by validate, never silently lost.
            pattern=r'<(ul|ol)(\s[^>]*|)>\s*<li(\s[^>]*|)>((?:(?!</?li\b|</?(?:ul|ol)\b)[\s\S])*)</li>\s*</\1>'
            from app.full_content_rewrite import VisibleText
            visible=VisibleText(source).spans
            matches=[m for m in re.finditer(pattern,source,re.I)
                     if any(start<m.end(4) and end>m.start(4) for start,end in visible)]
            for match in reversed(matches):
                # A list item can already contain a paragraph or another block.
                # Wrapping those in <p> would create invalid, browser-repaired HTML.
                block_tag=re.search(r'<(?:address|article|aside|blockquote|div|dl|fieldset|figure|footer|form|h[1-6]|header|hr|main|nav|p|pre|section|table)\b',match[4],re.I)
                wrapper='div' if block_tag else 'p'
                source=source[:match.start()]+f'<div{match[2]}><{wrapper}{match[3]}>{match[4]}</{wrapper}></div>'+source[match.end():]
            target=b['data']
            for token in path[:-1]:target=target[token]
            target[path[-1]]=source
            if matches:changes.append({'block_id':key,'from':'html_single_list','to':'paragraph','count':len(matches)})
    return changes


def reshape(before, rewritten, seed):
    """At most one appropriate structural conversion; source cells are copied intact."""
    content=deepcopy(rewritten);changes=normalize_singletons(content)
    order=['table','list'] if hashlib.sha256(str(seed).encode()).digest()[0]%2 else ['list','table']
    converted=False
    for kind in order:
        if converted:break
        for index,b in enumerate(content.get('blocks',[])):
            if b.get('type')!=kind:continue
            data=b.get('data') or {};key=b.get('id',str(index))
            if kind=='table':
                rows=data.get('content') or []
                if not rows or set(data)-{'content','withHeadings','stretched'} or any(not isinstance(r,list) or len(r)!=2 or not all(isinstance(v,str) for v in r) for r in rows):continue
                headers=rows[0] if data.get('withHeadings') else None
                body=rows[1:] if headers else rows
                if len(body)<2:continue
                items=[f'{headers[0]}: {a}; {headers[1]}: {c}' if headers else f'{a}: {c}' for a,c in body]
                b.update(type='list',data={'style':'unordered','items':items})
                change={'block_id':key,'from':'table','to':'list','items':len(items)}
            else:
                items=data.get('items') or []
                if data.get('style')!='unordered' or len(items)<5 or not all(isinstance(v,str) for v in items):continue
                rows=[v.split(': ',1) for v in items]
                if any(len(r)!=2 or not r[0].strip() or not r[1].strip() or len(r[0])>60 or re.search(r'[<>/]',r[0]) for r in rows):continue
                # No invented heading, row or ordinal: preserve each label/value.
                b.update(type='table',data={'content':rows,'withHeadings':False,'stretched':False})
                change={'block_id':key,'from':'list','to':'table','rows':len(rows),'columns':2}
            changes.append(change);converted=True;break
    validate(before,content)
    return content,changes
