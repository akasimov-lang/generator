"""Hide technical HTML attributes from the writer and restore them verbatim."""
from collections import Counter
from copy import deepcopy
from html.parser import HTMLParser
import re


def transform(content, function, *, encoded=False):
    from app.full_content_rewrite import fields
    output=deepcopy(content)
    targets=list(fields(output))
    if encoded:
        existing={(index,path) for index,path,_ in targets}
        for index,block in enumerate(output.get('blocks',[])):
            if block.get('type')!='code':continue
            for key in ('html','code','text'):
                value=(block.get('data') or {}).get(key)
                if (index,(key,)) not in existing and isinstance(value,str) and re.search(r'PP_INERT_\d+_END',value):
                    targets.append((index,(key,),value))
    for index,path,value in targets:
        node=output['blocks'][index]['data']
        for key in path[:-1]:node=node[key]
        node[path[-1]]=function(value)
    return output


class Tags(HTMLParser):
    def __init__(self,text,callback):
        super().__init__(convert_charrefs=False)
        self.source=text;self.lines=[0,*[m.end() for m in re.finditer('\n',text)]]
        self.callback=callback;self.replacements=[];self.feed(text);self.close()
    def handle_starttag(self,tag,attrs):
        raw=self.get_starttag_text();line,col=self.getpos();start=self.lines[line-1]+col
        replacement=self.callback(tag,attrs,raw)
        if replacement is not None:self.replacements.append((start,start+len(raw),replacement))
    handle_startendtag=handle_starttag
    def result(self):
        result=self.source
        for start,end,value in reversed(self.replacements):result=result[:start]+value+result[end:]
        return result


def pack(content):
    markers={};inert={}
    def encode(value):
        def hide(match):
            token='PP_INERT_'+str(len(inert))+'_END';inert[token]=match[0];return token
        value=re.sub(r'<(script|style|template|noscript|pre|code)\b[^>]*>[\s\S]*?</\1\s*>',hide,value,flags=re.I)
        def start(tag,attrs,raw):
            if not attrs:return None
            token='m'+str(len(markers))
            optional=tag=='p' and all(k=='id' and re.fullmatch(r'rewrite-(source|added)-[\w-]+',v or '') for k,v in attrs)
            markers[token]={'tag':tag,'raw':raw,'required':not optional}
            return '<'+tag+' data-pp='+token+(' />' if raw.endswith('/>') else '>')
        return Tags(value,start).result()
    return transform(content,encode),{'markers':markers,'inert':inert}


def unpack(content,contract):
    seen=Counter();inert_seen=Counter()
    def decode(value):
        def start(tag,attrs,raw):
            attr=dict(attrs)
            if 'data-pp' not in attr:return None
            token=attr['data-pp'];entry=contract['markers'].get(token)
            if not entry or entry['tag']!=tag or set(attr)!={'data-pp'}:raise ValueError('Changed technical marker '+str(token))
            seen[token]+=1
            return entry['raw']
        value=Tags(value,start).result()
        for token,original in contract['inert'].items():
            inert_seen[token]+=value.count(token);value=value.replace(token,original)
        return value
    output=transform(content,decode,encoded=True)
    if any(seen[token]!=(1 if entry['required'] else min(seen[token],1)) for token,entry in contract['markers'].items()):
        raise ValueError('Missing or duplicate technical marker')
    if any(inert_seen[token]!=1 for token in contract['inert']):raise ValueError('Missing or duplicate protected code')
    return output
