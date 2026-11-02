"""Structural shortening that always leaves an H1 and a substantive paragraph."""
from copy import deepcopy
from uuid import uuid4
from html import escape
import math


def trim(content, action, title=''):
    result=deepcopy(content)
    blocks=result['blocks']
    paragraphs=[(i,b) for i,b in enumerate(blocks) if b.get('type')=='paragraph' and str((b.get('data') or {}).get('text') or '').strip()]
    if not paragraphs:
        raise ValueError('На странице нет абзаца, который можно оставить после обрезки.')
    h1=next((b for b in blocks if b.get('type')=='header' and (b.get('data') or {}).get('level')==1),None)
    heading_source=h1
    if h1 is None:
        heading=next((b for b in blocks if b.get('type')=='header' and (b.get('data') or {}).get('text')),None)
        if heading:
            heading_source=heading
            h1=deepcopy(heading);h1['data']['level']=1
        elif title:
            h1={'id':uuid4().hex,'type':'header','data':{'text':escape(title),'level':1}}
        else:
            raise ValueError('Не найден H1 или название страницы для сохранения заголовка.')
    if action=='trim_99':
        result['blocks']=[h1,paragraphs[0][1]]
    elif action=='trim_50':
        end=paragraphs[max(0,math.ceil(len(paragraphs)/2)-1)][0]
        result['blocks']=[h1,*[b for b in blocks[:end+1] if b is not heading_source and not (b.get('type')=='header' and (b.get('data') or {}).get('level')==1)]]
    else:raise ValueError('Неизвестный режим обрезки.')
    return result
