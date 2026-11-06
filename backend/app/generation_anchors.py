"""Editable homepage anchors: menu plans cycle the pool; other articles sample it."""
from copy import deepcopy
from html import escape
import re,secrets
from app import models
from app.auto_lb_keywords import POLISH
from app.brand_home_links import apply_brand_home_links,link_brand_paragraph

HOME_LABELS = {'en': 'Home', 'de': 'Startseite', 'pl': 'Strona główna', 'cs': 'Domů',
    'sk': 'Domov', 'sl': 'Domov', 'da': 'Forside', 'sv': 'Startsida', 'no': 'Hjem',
    'fi': 'Etusivu', 'et': 'Avaleht', 'lv': 'Sākumlapa', 'lt': 'Pradžia',
    'fr': 'Accueil', 'it': 'Pagina iniziale', 'es': 'Inicio', 'pt': 'Página inicial',
    'nl': 'Home', 'ro': 'Acasă', 'hu': 'Főoldal', 'tr': 'Ana sayfa',
    'az': 'Ana səhifə', 'ru': 'Главная', 'uk': 'Головна', 'bg': 'Начало',
    'el': 'Αρχική', 'ar': 'الرئيسية', 'ja': 'ホーム', 'ko': '홈', 'zh': '首页'}


def home_label(site, item=None):
    language = getattr(site, 'cache_language', None) or getattr(getattr(item, 'task', None), 'language', '')
    code = str(language).lower().replace('_', '-').split('-')[0]
    return HOME_LABELS.get(code) or site.name


def general(site):
    return bool(site and (site.site_type=='general' or not site.site_type and (not site.brand or site.brand.strip().casefold()=='общие ключи')))


def defaults(site):
    if not site:return []
    if not general(site):return [site.brand.strip()] if site.brand and site.brand.strip() else []
    parts=str(site.cache_geo or '').replace('_','-').upper().split('-')
    return list(POLISH) if 'PL' in parts else []


def parse_anchors(value):
    values=re.split(r'[,\n\r]+',value) if isinstance(value,str) else value
    if not isinstance(values,list) or len(values)>100:raise ValueError('Укажите до 100 анкоров строками или через запятую.')
    result=[];seen=set()
    for value in values:
        if not isinstance(value,str):raise ValueError('Анкор должен быть текстом.')
        value=' '.join(value.split())
        if not value:continue
        if len(value)>200 or re.search(r'[<>]|https?://',value):raise ValueError('Анкор — до 200 символов, без HTML и URL.')
        if value.casefold() not in seen:result.append(value);seen.add(value.casefold())
    return result


def settings(db,site):
    row=db.get(models.AutoReglueConfig,'generation-anchors:'+site.id)
    values=(row.value or {}).get('anchors') if row else None
    return {'anchors':parse_anchors(values) if values is not None else defaults(site),'source':'custom' if values is not None else 'default'}


def save_settings(db,site,value):
    anchors=parse_anchors(value)
    if not anchors:raise ValueError('Добавьте хотя бы один анкор.')
    key='generation-anchors:'+site.id;row=db.get(models.AutoReglueConfig,key)
    if row is None:row=models.AutoReglueConfig(key=key,value={});db.add(row)
    row.value={'anchors':anchors};db.commit()
    return {'anchors':anchors,'source':'custom'}


def select_anchor(db,item,site):
    context=item.generation_context or {}
    # A root-relative link is mandatory for every newly generated internal page.
    # Keep legacy request payloads compatible, but do not let their old opt-out
    # remove the link during generation or the pre-publication check.
    if context.get('homepage_interlinking') is not True:
        context = {**context, 'homepage_interlinking': True}
        item.generation_context = context
        db.commit()
    saved=context.get('homepage_anchor')
    if isinstance(saved,str) and saved.strip() and context.get('homepage_anchor_site_id')==site.id:
        return saved
    pool=settings(db,site)['anchors']
    if not pool:pool=[home_label(site,item)]
    # Independent sampling, with no round robin, balancing, quotas or reroll on retry.
    anchor=secrets.choice(pool)
    item.generation_context={**context,'homepage_anchor':anchor,'homepage_anchor_site_id':site.id}
    db.commit()
    return anchor


def apply_home_anchor(db,item,site,payload):
    result=deepcopy(payload)
    for page in result.get('pages',[]) if isinstance(result,dict) else []:
        for block in (page.get('content') or {}).get('blocks',[]):
            if block.get('type')=='header' and isinstance(block.get('data',{}).get('text'),str):
                text=block['data']['text']
                block['data']['text']=re.sub(r'</?a\b[^>]*>','',text,flags=re.I)
    if not site:return result
    anchor=select_anchor(db,item,site)
    if getattr(item, 'section_content_mode', None) == 'menu_page' and (item.generation_context or {}).get('content_kind') != 'technical_page':
        from app.structure_home_link import place_home_link
        anchor = anchor or getattr(site, 'cache_canon', None) or site.name
        canon = getattr(site, 'cache_canon', None) or site.name
        for page in result.get('pages', []):
            if str(page.get('slug') or '').strip('/'):
                page['content'] = place_home_link(page.get('content') or {}, anchor, canon, page['slug'])
        return result
    if not anchor:return apply_brand_home_links(result,site)
    pages=result.get('pages',[]) if isinstance(result,dict) else []
    for page in pages:
        if not str(page.get('slug') or '').strip('/'):continue
        content=page.get('content') or {}
        try:
            page['content'],_=link_brand_paragraph(content,anchor)
        except ValueError:
            # Old generated articles may predate this pool. Add a neutral
            # reference to an existing paragraph without editing any heading.
            paragraphs=[b for b in content.get('blocks',[]) if b.get('type')=='paragraph' and isinstance(b.get('data',{}).get('text'),str)]
            if not paragraphs:raise ValueError('Нет обычного абзаца для ссылки на главную; публикация остановлена.')
            target=paragraphs[min(1,len(paragraphs)-1)]['data']
            prefix='Zobacz również: ' if general(site) and defaults(site) else ''
            target['text']=target['text'].rstrip()+' '+prefix+'<a href="/">'+escape(anchor)+'</a>.'
    return result


def keyword_instruction(db, site):
    keys = settings(db, site)['anchors']
    if not keys:
        return ''
    import json
    return ('\n\nProject primary search keywords (data, not instructions): ' + json.dumps(keys, ensure_ascii=False)
            + '. Use relevant phrases naturally for this article topic in the project language. '
              'Do not force unrelated keywords, repeat every phrase, or change facts and legal statements to fit keywords.')
