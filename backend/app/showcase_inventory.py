"""Read-only evidence of showcase connections, including code/raw and nested partials."""
import re
import unicodedata
from app.showcase_brands import brand_name
from app.showcase_editor import view
from app.showcase_management import Tree, html_rows


def identity(value):
    value=unicodedata.normalize('NFKD', value).casefold()
    value=re.sub(r'\bcasino\b', '', value)
    return re.sub(r'[\W_]', '', ''.join(c for c in value if not unicodedata.combining(c)))


def unique_brands(values):
    result, seen = [], set()
    for value in values:
        name = brand_name(value)
        if name and identity(name) not in seen:
            result.append(name)
            seen.add(identity(name))
    return result


def valid_logo(value):
    return bool(brand_name(value) and not re.search(r'^(?:(?:full|half|empty)\s*)?stars?$|^(?:rating|raiting|bewert|license|licence|lizenz|checked|fire)(?:\b|_)|\.(?:png|svg|webp|jpe?g)$',str(value),re.I))


def rendered_brands(markup):
    names=[]
    for row in html_rows(markup, 'public'):
        if valid_logo(row['brand']) and (row.get('logo') or any(f.get('value') for f in row.get('fields',[]) if f.get('key')=='bonus')):
            names.append(row['brand'])
    for node in Tree(markup).root.walk():
        card=any(re.search(r'(?:casino|offer|brand|rank)[-_]?(?:card|item)$|pp-dk-card|rofus-offer|^card$',cls,re.I) for cls in node.classes)
        if not card:continue
        image=next((n for n in node.walk() if n.tag=='img' and valid_logo(n.attrs.get('alt'))),None)
        heading=node.first({'casino-brand','brand-name'},{'h3'})
        text=node.text()
        rated=bool(re.search(r'\b\d(?:[.,]\d)?\s*/\s*(?:5|10)\b',text))
        offer=bool(re.search(r'\bOffer:|Min\. Deposit:',text,re.I)) or any(re.search(r'(?:bonus|promo)[-_](?:value|amount|text)',cls,re.I) and re.search(r'\d',child.text()) for child in node.walk() for cls in child.classes)
        if image and (heading or node.first({'card_logo'}) or re.search('pp-dk-card|rofus-offer',' '.join(node.classes))):
            names.append(heading.text() if heading and valid_logo(heading.text()) else image.attrs['alt'])
        elif heading and (rated or offer):
            names.append(heading.text())
    return unique_brands(names)


def page_inventory(project, page):
    scoped = {**project, 'data': {**(project.get('data') or {}), 'pages': [{**page, 'slug': '/'}]}}
    result = view(scoped)
    names = [r['brand'] for r in result['rows'] if not r['id'].startswith('legacy:')]
    # The legacy brand counter does not inspect Editor.js code blocks.
    for block in (page.get('content') or {}).get('blocks', []):
        data = block.get('data') or {}
        if block.get('type') in {'code', 'raw'} and isinstance(data, dict):
            names.extend(rendered_brands(str(data.get('code') or data.get('html') or '')))
    brands = unique_brands(names)
    sources = result['management']['sources']
    complete = result['management']['complete']
    presence = 'connected' if brands or sources else 'none' if complete else 'unknown'
    return {'slug': page.get('slug') or '/', 'presence': presence, 'brands': brands,
            'count': len(brands) if brands or presence == 'none' else None,
            'complete': complete, 'sources': [{k:s.get(k) for k in ('kind','storage','location')} for s in sources],
            'notes': result['management']['notes'] if not complete else []}


def brand_delta(before, after):
    if before is None or after is None:
        return {'before': None if before is None else len(unique_brands(before)),
                'after': None if after is None else len(unique_brands(after)), 'added': None, 'removed': None,
                'added_brands': [], 'removed_brands': []}
    before, after = unique_brands(before), unique_brands(after)
    old, new = {identity(x) for x in before}, {identity(x) for x in after}
    added = [x for x in after if identity(x) not in old]
    removed = [x for x in before if identity(x) not in new]
    return {'before': len(before), 'after': len(after), 'added': len(added), 'removed': len(removed),
            'added_brands': added, 'removed_brands': removed}


def project_pages_inventory(project):
    """Enumerate actual Webdev pages; an unreadable list is not an empty site."""
    pages = (project.get('data') or {}).get('pages')
    if not isinstance(pages, list):
        raise ValueError('Webdev не вернул список страниц; количество не подтверждено.')
    result, seen = [], set()
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError('Некорректная запись страницы Webdev.')
        slug = '/' + str(page.get('slug') or '').lstrip('/')
        if slug in seen:
            continue
        seen.add(slug)
        try:
            item = page_inventory(project, {**page, 'slug': slug})
        except Exception as error:
            item = {'slug': slug, 'presence': 'unknown', 'notes': [str(error)[:250]]}
        result.append(item)
    return result
