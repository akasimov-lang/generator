"""Discover connected showcase sources and retain internal management instructions.

Only native casino records are edited inline. Other adapters read content and
identify its actual owner; they never rewrite HTML or publish a whole project.
"""
from html.parser import HTMLParser
import hashlib
import json
import re
from uuid import NAMESPACE_URL, uuid5
from app.showcase_brands import brand_name, plain

VOID = {'img','br','hr','input','meta','link','source','wbr','area','base','embed','param','track','col'}
CARD = {'casino','casino-card','columnItem','rowItem','lf-card'}
IGNORE = {'header','footer','menu','navigation','nav-menu'}
PARTIAL = re.compile(r'{{>\s*["\']?([\w .-]+?)["\']?\s*}}')
LABELS = {'bonus':'Бонус','rating':'Рейтинг','minDep':'Мин. депозит','wager':'Вейджер'}

class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []
        self.parent = None
    @property
    def classes(self): return set((self.attrs.get('class') or '').split())
    def walk(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.walk()
    def text(self):
        if self.tag in {'script','style','button','svg'}: return ''
        return plain(' '.join(c.text() if isinstance(c,Node) else c for c in self.children))
    def first(self, classes=(), tags=()):
        return next((n for n in self.walk() if n.classes.intersection(classes) or n.tag in tags), None)

class Tree(HTMLParser):
    def __init__(self, markup):
        super().__init__(convert_charrefs=True);self.root=Node();self.stack=[self.root];self.feed(markup)
    def handle_starttag(self, tag, attrs):
        node=Node(tag,attrs);node.parent=self.stack[-1];self.stack[-1].children.append(node)
        if tag not in VOID:self.stack.append(node)
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID:self.handle_endtag(tag)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:self.stack=self.stack[:i];break
    def handle_data(self,data):self.stack[-1].children.append(data)


def field_rows(brand, values, row_id, source_id, logo=None):
    if not (brand := brand_name(brand)) or '{{' in brand:
        return None
    fields=[{'id':key,'key':key,'label':LABELS.get(key,key),'value':value,'list':False}
            for key,value in values.items() if value and '{{' not in value]
    return {'id':row_id,'brand':brand,'fields':fields,'editable':False,'group':'',
            'source_id':source_id,'logo':logo}


def html_rows(markup, source_id):
    root=Tree(markup).root;result=[]
    for card in (n for n in root.walk() if n.classes & CARD):
        title=card.first({'casino-brand','card-title','title','name','lf-brand'}, {'h3'})
        info=card.first({'casino-info'})
        rating_block=card.first({'rating-block'})
        if title is None and info:title=info.first(tags={'strong'})
        if title is None and rating_block:title=rating_block.first(tags={'p'})
        img=next((n for n in card.walk() if n.tag=='img' and not re.search(r'star|icon|license|licence|rating|hodnocen',str(n.attrs),re.I)),None)
        brand=(brand_name(title.text()) if title else None) or (img.attrs.get('alt','') if img else '')
        bonus=card.first({'bonus-value','bonusText','casinoBonus','lf-offer'})
        if bonus is None:
            box=card.first({'bonus'})
            if box:bonus=box.first({'text'}, {'p'}) or box
        if bonus is None and info:bonus=info.first(tags={'span'})
        values={'bonus':bonus.text() if bonus else ''}
        # Preserve separately labelled offers instead of merging their amounts.
        for box in (n for n in card.walk() if n.classes & {'meta-row','casino-chip'}):
            label=box.first(tags={'span'});value=box.first(tags={'strong','b'})
            if label and value and re.search(r'bonus|spin',label.text(),re.I):
                key='bonus' if re.search(r'vstupní|vkladový',label.text(),re.I) else label.text().rstrip(':')
                values[key]=value.text()
        rating=card.first({'casino-rating','rating-info','rating-row'})
        if rating is None:
            rating=card.first({'rating','lf-rating'})
            if rating:rating=rating.first({'text','lf-rating-value'}) or rating.first(tags={'b','span'})
        if rating:
            match=re.search(r'\d+(?:[.,]\d+)?(?:\s*/\s*10)?',rating.text())
            if match:values['rating']=match.group()
        owner=card.parent if card.parent and 'casinos-wrapper' in card.parent.classes else card
        deposit=owner.first({'min-dep','minDep'})
        if deposit:
            value=deposit.first(tags={'span'})
            if value:values['minDep']=value.text()
        row=field_rows(brand,values,f'{source_id}:card:{len(result)}',source_id,img.attrs.get('src') if img else None)
        if row:result.append(row)
    for table in (n for n in root.walk() if n.tag=='table'):
        cells=[[c.text() for c in row.children if isinstance(c,Node) and c.tag in {'td','th'}] for row in table.walk() if row.tag=='tr']
        result.extend(table_rows(cells,source_id,offset=len(result)))
    return result


def table_rows(cells, source_id, offset=0):
    if not cells or not isinstance(cells[0],list):return []
    labels=[plain(c).lower() for c in cells[0]]
    brand_col=next((i for i,c in enumerate(labels) if re.fullmatch(r'(?:nazwa |online |nové |nové české )?(?:kasyna|kasino|casino|brand)(?: name)?',c)),None)
    bonus_col=next((i for i,c in enumerate(labels) if 'bonus' in c),None)
    if brand_col is None or bonus_col is None:return []
    columns={'bonus':bonus_col}
    for key,pattern in [('minDep',r'min.*(?:depo|vklad)'),('wager',r'wager|protočen'),('rating',r'rating|hodnocen|ocena')]:
        found=next((i for i,c in enumerate(labels) if re.search(pattern,c)),None)
        if found is not None:columns[key]=found
    result=[]
    for i,row in enumerate(cells[1:]):
        if not isinstance(row,list) or len(row)<=max([brand_col,*columns.values()]):continue
        item=field_rows(row[brand_col],{k:plain(row[n]) for k,n in columns.items()},f'{source_id}:table:{offset+i}',source_id)
        if item:result.append(item)
    return result


def inspect(project, native_rows=()):
    data=project.get('data') or {};sources=[];legacy=[];visited=set();missing=[]
    templates={str(s.get('name','')).removesuffix('.hbs'):s.get('data','') for s in project.get('shortcodes',[]) if isinstance(s,dict)}
    homes=[p for p in data.get('pages',[]) if isinstance(p,dict) and not str(p.get('slug') or '').strip('/')]
    def add(kind,locator,markup='',cells=None):
        sid=kind+':'+locator
        rows=table_rows(cells,sid) if cells is not None else html_rows(markup,sid)
        groups=re.findall(r'{{#each\s+(?:\.\./)?casinos(?:\.([\w]+))?\s*}}',markup)
        external=bool(re.search(r'<(?:iframe|script)\b[^>]*src=',markup,re.I)) and bool(re.search(r'casino|showcase|vitrin',markup,re.I))
        if rows or groups or external:
            mode='native' if groups else kind
            action={'native':'Редактировать карточки и логотипы в этой таблице.',
                    'page_table':'Редактор главной страницы → таблица.',
                    'page_code':'Редактор главной страницы → блок кода.',
                    'page_raw':'Редактор главной страницы → HTML-блок.',
                    'shortcode':'Webdev → шорткоды → указанный файл.',
                    'layout':'Webdev → шаблон страницы.',
                    'banner':'Webdev → баннер, подключённый к главной странице.'}.get(mode,'Проверить поставщика внешней витрины.')
            if external and not rows and not groups:mode='external';action='Внешний источник: управление у поставщика. Локальное редактирование не подтверждено.'
            sources.append({'id':sid,'kind':mode,'storage':kind,'location':locator,'count':len(rows),
                            'inline_edit':mode=='native','action':action,'digest':hashlib.sha256(markup.encode() if cells is None else json.dumps(cells,ensure_ascii=False).encode()).hexdigest()})
            legacy.extend(rows)
        for name in PARTIAL.findall(markup):visit(name)
    def visit(name,kind='shortcode'):
        name=str(name).strip().removesuffix('.hbs')
        if not name:return  # An empty editor placeholder does not reference a missing template.
        if name in visited or name in IGNORE:return
        visited.add(name)
        if name not in templates:missing.append(name);return
        add(kind,name+'.hbs',templates[name])
    if len(homes)==1:
        home=homes[0]
        for i,b in enumerate((home.get('content') or {}).get('blocks',[])):
            if not isinstance(b,dict) or not isinstance(b.get('data'),dict):continue
            kind,value=b.get('type'),b['data'];locator='home.blocks.'+str(b.get('id') or i)
            if kind=='shortcode':visit(value.get('shortcode',''))
            elif kind in {'code','raw'}:add('page_'+kind,locator,str(value.get('code' if kind=='code' else 'html','')))
            elif kind=='table':add('page_table',locator,cells=value.get('content') or [])
        for b in home.get('banners',[]) if isinstance(home.get('banners'),list) else []:
            if isinstance(b,str):visit(b,'banner')
            elif isinstance(b,dict):
                name=b.get('shortcode') or b.get('name')
                if name:visit(name,'banner')
    add('layout','layout',str(project.get('layout') or ''))
    if native_rows and not any(s['kind']=='native' for s in sources):
        sources.insert(0,{'id':'native:cache','kind':'native','storage':'casinos','location':'data.casinos','count':len(native_rows),'inline_edit':True,'action':'Редактировать карточки и логотипы в этой таблице. Подключение шаблона уточняется при обновлении.'})
    notes=['Изменять только источник, реально подключённый к главной странице. Не публиковать весь проект ради одной витрины.',
           'Перед записью: резервная копия и проверка версии; после записи: чтение Webdev и проверка публичной страницы.',
           'Сохранять существующие карточки и бонусы при добавлении брендов. Не смешивать условия разных предложений.',
           'Галерея basic и неиспользуемые шаблоны не являются размещёнными брендами. Сохранять ключи переходов и привязки логотипов.']
    if missing:notes.append('Кеш не содержит подключённые шаблоны: '+', '.join(missing)+'. Обновите данные из Webdev.')
    if any(not s['inline_edit'] for s in sources):notes.append('HTML, таблицы и шорткоды показаны для чтения. Используйте указанный редактор источника; массовое преобразование не выполнялось.')
    canon=(project.get('settings') or {}).get('canon','')
    origin=canon if '://' in canon else 'https://'+canon
    for row in legacy:
        if row.get('logo') and row['logo'].startswith('/') and not row['logo'].startswith('//') and canon:row['logo']=origin.rstrip('/')+row['logo']
        elif row.get('logo') and not row['logo'].startswith(('https://','http://')):row['logo']=None
    return {'version':1,'complete':not missing and len(homes)==1,'sources':sources,'notes':notes},legacy


def remember(db,site,user,management):
    """Durable system notes in the existing audit ledger, isolated by page_key."""
    if not management['complete']:return None
    from app import models
    fingerprint=hashlib.sha256(json.dumps(management,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    key=str(uuid5(NAMESPACE_URL,'pagepilot:showcase-management:'+site.id+':'+fingerprint))
    if db.get(models.ProjectPageEdit,key) is None:
        db.add(models.ProjectPageEdit(id=key,site_id=site.id,page_key='showcase:management',requested_by=user['username'],fingerprint=fingerprint,before_page={},after_page={'management':management},status='confirmed'))
        try:db.commit()
        except Exception:
            db.rollback()
            if db.get(models.ProjectPageEdit,key) is None:raise
    return key
