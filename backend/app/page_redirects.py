"""Merge a single settings.pageRedirects rule into the latest native snapshot."""
from copy import deepcopy
from urllib.parse import urlsplit
from app.domain_redirects import redirect_domain


def source_path(value):
    value=value.strip()
    if (not value.startswith('/') or value.startswith('//') or '#' in value or '\\' in value
            or any(c.isspace() or ord(c)<32 for c in value)):
        raise ValueError('Откуда: укажите путь с /, без домена, пробелов и #, например /play/.')
    return value


def target_url(value):
    value=value.strip()
    try:
        url=urlsplit(value)
        if (url.scheme not in {'http','https'} or not url.hostname or url.username or url.password
                or url.fragment or '\\' in value or any(c.isspace() or ord(c)<32 for c in value)):
            raise ValueError()
        redirect_domain(url.hostname)
        if url.port is not None and not 0<url.port<65536:raise ValueError()
    except ValueError:
        raise ValueError('Куда: укажите полный адрес с http:// или https://, без пробелов и #.') from None
    return value


def update(project, domain, source, target, original_domain='', original_source='', delete=False):
    current=(project.get('settings') or {}).get('pageRedirects',[])
    if not isinstance(current,list) or any(not isinstance(g,dict) or not isinstance(g.get('domain'),str)
            or not isinstance(g.get('redirects'),list) or any(not isinstance(r,dict)
            or not isinstance(r.get('url'),str) or not isinstance(r.get('value'),str) for r in g['redirects']) for g in current):
        raise ValueError('Webdev не вернул полный список постраничных редиректов. Обновите данные.')
    result=deepcopy(current)
    domain=redirect_domain(domain);source=source_path(source)
    if delete and not original_source:raise ValueError('Не указан редирект для удаления.')
    original_domain=redirect_domain(original_domain or domain) if original_source else ''
    original_source=source_path(original_source) if original_source else ''
    matches=[(g,r) for g,group in enumerate(result) for r,row in enumerate(group['redirects'])
             if group['domain'].lower().rstrip('.')==original_domain and row['url']==original_source] if original_source else []
    if original_source and len(matches)!=1:
        raise ValueError('Редирект изменился или отсутствует. Обновите данные перед сохранением.')
    old=matches[0] if matches else None
    if delete:
        result[old[0]]['redirects'].pop(old[1]);return result
    target=target_url(target)
    if any(group['domain'].lower().rstrip('.')==domain and row['url']==source and (g,r)!=old
           for g,group in enumerate(result) for r,row in enumerate(group['redirects'])):
        raise ValueError('Редирект с этого адреса уже существует. Измените существующую строку.')
    row={**(result[old[0]]['redirects'][old[1]] if old else {}),'url':source,'value':target}
    if old:result[old[0]]['redirects'].pop(old[1])
    groups=[i for i,g in enumerate(result) if g['domain'].lower().rstrip('.')==domain]
    if len(groups)>1:raise ValueError('В Webdev повторяются группы этого домена. Обновите данные.')
    if not groups:result.append({'domain':domain,'redirects':[]});groups=[len(result)-1]
    index=old[1] if old and old[0]==groups[0] else len(result[groups[0]]['redirects'])
    result[groups[0]]['redirects'].insert(index,row)
    # Domain + path identifies the source independently of HTTP/HTTPS.
    edges={}
    for g in result:
        for r in g['redirects']:
            url=urlsplit(r['value'])
            edges[(g['domain'].lower().rstrip('.'),r['url'])]=((url.hostname or '').lower(),(url.path or '/')+('?' + url.query if url.query else ''))
    for node in edges:
        visited=set();current_node=node
        while current_node in edges:
            if current_node in visited:raise ValueError('Редирект создаёт цикл перенаправлений.')
            visited.add(current_node);current_node=edges[current_node]
    return result
