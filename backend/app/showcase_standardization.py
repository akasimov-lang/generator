"""Conservative adapters for replacing connected legacy showcase markup.

The planner is pure: it preserves datasets and text outside identified cards.
The caller must persist its full plan, recheck the revision and confirm each write.
"""
from copy import deepcopy
from html import escape
import re
from app.showcase_management import Tree,VOID,table_rows
from app.showcase_inventory import identity,unique_brands,rendered_brands,valid_logo,page_inventory
from app.showcase_editor import digest


class PositionedTree(Tree):
    def __init__(self,markup):
        self.markup=markup
        self.lines=[0]
        self.lines.extend(match.end() for match in re.finditer('\n',markup))
        super().__init__(markup)
    def source_offset(self):
        line,column=self.getpos()
        return self.lines[line-1]+column
    def handle_starttag(self,tag,attrs):
        start=self.source_offset();parent=self.stack[-1]
        super().handle_starttag(tag,attrs)
        node=parent.children[-1];node.start=start;node.end=start+len(self.get_starttag_text());node.closed=tag in VOID
    def handle_endtag(self,tag):
        node=next((n for n in reversed(self.stack) if n.tag==tag),None)
        if node:
            node.end=self.markup.find('>',self.source_offset())+1;node.closed=True
        super().handle_endtag(tag)


def card_nodes(markup):
    nodes=[]
    for node in PositionedTree(markup).root.walk():
        if not getattr(node,'closed',False):continue
        if not any(c in {'casino','casino-card','columnItem','rowItem','card'} or re.search(r'(?:casino|brand|offer)[-_]?(?:card|item)$|rofus-offer',c,re.I) for c in node.classes):continue
        brands=rendered_brands(markup[node.start:node.end])
        if len(brands)==1:nodes.append((node,brands[0]))
    # Replace the outermost complete single-brand card; its action remains included.
    return [(n,b) for n,b in nodes if not any(p.start<=n.start and p.end>=n.end and p is not n for p,_ in nodes)]


def safe_url(value):
    return isinstance(value,str) and value.startswith(('https://','http://','/')) and not value.startswith('//')


def card_record(markup,node,brand):
    from app.showcase_management import html_rows
    own=html_rows(markup[node.start:node.end],'card')
    own=next((row for row in own if identity(row['brand'])==identity(brand)),{})
    fields={f['key']:f['value'] for f in own.get('fields',[])}
    image=next((n for n in node.walk() if n.tag=='img' and valid_logo(n.attrs.get('alt')) and safe_url(n.attrs.get('src'))),None)
    bonus=node.first({'bonus-value','bonusText','casinoBonus','card_bonus'})
    if not fields.get('bonus') and bonus:fields['bonus']=bonus.text()
    if not fields.get('bonus'):raise ValueError('Не определено точное бонусное предложение: '+brand)
    actions=[]
    for a in (n for n in node.walk() if n.tag=='a' and safe_url(n.attrs.get('href')) and n.text()):
        actions.append('<a href="'+escape(a.attrs['href'],quote=True)+'" target="'+escape(a.attrs.get('target','_blank'),quote=True)+'" rel="'+escape(a.attrs.get('rel','nofollow sponsored noopener'),quote=True)+'">'+escape(a.text())+'</a>')
    return {'brand':brand,'bonus':fields['bonus'],'rating':fields.get('rating',''),'conditions':node.text(),
            'logo_src':image.attrs['src'] if image else None,'actions_html':' '.join(dict.fromkeys(actions))}


def table_records(block):
    cells=(block.get('data') or {}).get('content') or []
    rows=table_rows(cells,'table')
    if not rows or len(rows)!=len(cells)-1:raise ValueError('Таблица содержит неподтверждённые строки.')
    from app.showcase_brands import plain
    result=[]
    for row,values in zip(rows,cells[1:]):
        fields={f['key']:f['value'] for f in row['fields']}
        tree=Tree(' '.join(str(x) for x in values)).root
        image=next((n for n in tree.walk() if n.tag=='img' and valid_logo(n.attrs.get('alt')) and safe_url(n.attrs.get('src'))),None)
        actions=['<a href="'+escape(n.attrs['href'],quote=True)+'" target="_blank" rel="nofollow sponsored noopener">'+escape(n.text())+'</a>' for n in tree.walk() if n.tag=='a' and safe_url(n.attrs.get('href')) and n.text()]
        result.append({'brand':row['brand'],'bonus':fields['bonus'],'rating':fields.get('rating',''),
                       'conditions':'\n'.join(plain(label)+': '+plain(value) for label,value in zip(cells[0],values)),
                       'logo_src':image.attrs['src'] if image else None,'actions_html':' '.join(actions)})
    return result


STYLE='''<style>
.pp-standard{display:grid;gap:16px;width:100%;grid-column:1/-1;flex:1 0 100%;margin:20px 0;font-family:inherit}
.pp-standard.pp-standard .pp-standard-card{display:grid;grid-template-columns:minmax(130px,180px) minmax(0,1fr) minmax(130px,200px);gap:20px;align-items:center;width:100%;box-sizing:border-box;padding:22px;border:1px solid #8b94a666;border-radius:14px;background:var(--showcase-card-bg,#fff);color:var(--showcase-card-color,#1c2638)}
.pp-standard .pp-standard-brand{min-width:0;text-align:center}.pp-standard .pp-standard-brand img{display:block;width:150px;max-width:100%;height:82px;object-fit:contain;margin:0 auto 10px}.pp-standard .casino-brand{display:block;overflow-wrap:anywhere;font-size:18px;line-height:1.3;font-weight:700}
.pp-standard .bonus-value{font-size:20px;line-height:1.4;font-weight:700;overflow-wrap:anywhere}.pp-standard .casino-rating{display:block;margin-top:8px;font-weight:600}.pp-standard .pp-standard-actions{display:grid;gap:8px}.pp-standard .pp-standard-actions a{display:block;padding:12px;border-radius:8px;background:var(--showcase-button-bg,#3557d6);color:#fff;text-decoration:none;text-align:center;font-weight:700;line-height:1.3}
.pp-standard .pp-standard-terms{grid-column:1/-1;margin:0;font-size:13px}.pp-standard .pp-standard-terms p{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.5}.pp-standard summary{cursor:pointer}
@media(max-width:640px){.pp-standard.pp-standard .pp-standard-card{grid-template-columns:1fr;gap:14px;padding:16px}.pp-standard .casino-brand{font-size:16px}.pp-standard .bonus-value{text-align:center;font-size:18px}.pp-standard .pp-standard-actions,.pp-standard .pp-standard-terms{grid-column:1}}
</style>'''


def template(group,details_label):
    v=lambda key:'{{findValueInObjectByKey this "'+key+'" "value" false}}'
    return STYLE+'<section class="pp-standard">{{#each casinos.'+group+'}}<article class="casino-card pp-standard-card"><div class="pp-standard-brand">{{#if (findLogo this ../casinos.basic "src")}}<img src="{{findLogo this ../casinos.basic "src"}}" alt="'+v('brand')+'" loading="lazy">{{/if}}<strong class="casino-brand">'+v('brand')+'</strong><span class="casino-rating">'+v('rating')+'</span></div><div class="bonus-value">'+v('bonus')+'</div><div class="pp-standard-actions">{{{findValueInObjectByKey this "actions_html" "value" false}}}</div><details class="pp-standard-terms"><summary>'+escape(details_label)+'</summary><p>'+v('conditions')+'</p></details></article>{{/each}}</section>'


def prepare(project,public_html,expected_brands,details_label='Details'):
    """Prepare every connected legacy table/card block, failing closed on ambiguity."""
    planned=deepcopy(project);data=planned.setdefault('data',{});casinos=data.setdefault('casinos',{})
    if not isinstance(casinos,dict):raise ValueError('Формат данных casinos требует отдельного адаптера.')
    basic=casinos.setdefault('basic',[])
    if not isinstance(basic,list):raise ValueError('Не определён формат галереи логотипов.')
    gallery=next((f for f in basic if f.get('key')=='logo' and f.get('type')=='gallery'),None)
    if gallery is None:gallery={'key':'logo','type':'gallery','data':[]};basic.append(gallery)
    if not isinstance(gallery.get('data'),list):raise ValueError('Не определена галерея логотипов.')
    public_records={identity(brand):card_record(public_html,node,brand) for node,brand in card_nodes(public_html) if identity(brand) in {identity(x) for x in expected_brands}}
    original_defs={s['name'].removesuffix('.hbs'):s for s in project.get('shortcodes',[]) if isinstance(s,dict) and isinstance(s.get('data'),str)}
    used=set()
    def visit(name):
        name=str(name).removesuffix('.hbs')
        if name in used or name in {'header','footer','menu','navigation'}:return
        used.add(name)
        for sub in re.findall(r'{{>\s*["\']?([\w .-]+?)["\']?\s*}}',str(original_defs.get(name,{}).get('data',''))):visit(sub)
    for page in data.get('pages',[]):
        for block in (page.get('content') or {}).get('blocks',[]):
            if block.get('type')=='shortcode' and isinstance(block.get('data'),dict):visit(block['data'].get('shortcode',''))
    for sub in re.findall(r'{{>\s*["\']?([\w .-]+?)["\']?\s*}}',str(project.get('layout') or '')):visit(sub)
    groups={};new_templates=[];logo_ids={str(x.get('id')) for x in gallery['data']};next_logo=1790000000000
    def group_for(records):
        nonlocal next_logo
        key=tuple(identity(r['brand']) for r in records)
        if key in groups:return groups[key]
        group='pagepilot_standard_'+str(len(groups)+1);name='casinos-standard-'+str(len(groups)+1)
        if group in casinos or name in original_defs:raise ValueError('Обнаружен существующий шаблон стандартизации. Требуется повторное чтение.')
        cards=[]
        for record in records:
            fields=[{'key':key,'type':'text','value':record.get(key,'')} for key in ('brand','bonus','rating','conditions','actions_html')]
            if record.get('logo_src'):
                while str(next_logo) in logo_ids:next_logo+=1
                logo_ids.add(str(next_logo));gallery['data'].append({'id':next_logo,'src':record['logo_src'],'alt':record['brand']})
                fields.append({'key':'logo','type':'logo','id':next_logo});next_logo+=1
            cards.append(fields)
        casinos[group]=cards;new_templates.append({'name':name+'.hbs','data':template(group,details_label)});groups[key]=name
        return name
    changed_templates=[];changed_pages=[]
    for name in sorted(used):
        source=original_defs.get(name)
        if not source:continue
        markup=source['data'];nodes=card_nodes(markup)
        if not nodes:continue
        names=[brand for _,brand in nodes]
        if len(unique_brands(names))!=len(names):raise ValueError('Повторяющиеся карточки в шаблоне '+name)
        if any(identity(brand) not in public_records for brand in names):raise ValueError('Не подтверждены публичные карточки шаблона '+name)
        replacement=group_for([public_records[identity(brand)] for brand in names]);new=markup
        for index,(node,_) in reversed(list(enumerate(nodes))):new=new[:node.start]+('{{> '+replacement+'}}' if index==0 else '')+new[node.end:]
        changed={**source,'data':new};changed_templates.append((source,changed))
        actual=next(s for s in planned['shortcodes'] if s.get('name')==source['name']);actual['data']=new
    for page in data.get('pages',[]):
        original=deepcopy(page);blocks=[];changed=False
        for block in (page.get('content') or {}).get('blocks',[]):
            kind=block.get('type');value=block.get('data') or {}
            if kind=='table' and isinstance(value,dict):
                try:records=table_records(block)
                except ValueError:blocks.append(block);continue
                if not records or any(identity(r['brand']) not in {identity(x) for x in expected_brands} for r in records):blocks.append(block);continue
                name=group_for(records);blocks.append({'id':block.get('id'),'type':'shortcode','data':{'shortcode':name}});changed=True
            elif kind in {'code','raw'} and isinstance(value,dict):
                field='code' if kind=='code' else 'html';markup=value.get(field,'');nodes=card_nodes(markup)
                if not nodes:blocks.append(block);continue
                names=[brand for _,brand in nodes]
                if any(identity(b) not in public_records for b in names):raise ValueError('Не подтверждена карточка HTML-блока.')
                name=group_for([public_records[identity(b)] for b in names]);cursor=0
                for index,(node,_) in enumerate(nodes):
                    fragment=markup[cursor:node.start]
                    if fragment:blocks.append({**block,'id':str(block.get('id','code'))+'-part-'+str(index),'data':{**value,field:fragment}})
                    if index==0:blocks.append({'id':str(block.get('id','code'))+'-standard','type':'shortcode','data':{'shortcode':name}})
                    cursor=node.end
                if markup[cursor:]:blocks.append({**block,'id':str(block.get('id','code'))+'-tail','data':{**value,field:markup[cursor:]}})
                changed=True
            else:blocks.append(block)
        if changed:
            page['content']={**(page.get('content') or {}),'blocks':blocks};changed_pages.append((original,deepcopy(page)))
    planned.setdefault('shortcodes',[]).extend(new_templates)
    if not groups:raise ValueError('Не найден поддерживаемый источник нестандартной витрины.')
    home=next((p for p in data.get('pages',[]) if not str(p.get('slug') or '').strip('/')),None)
    if home is None:raise ValueError('Не определена главная страница.')
    brands=page_inventory(planned,home)['brands']
    if {identity(x) for x in brands}!={identity(x) for x in expected_brands}:raise ValueError('Состав брендов после подготовки не совпадает с исходным. Публикация остановлена.')
    return {'before_revision':digest(project),'casinos_before':(project.get('data') or {}).get('casinos'),
            'casinos_after':casinos,'templates':changed_templates,'new_templates':new_templates,
            'pages':changed_pages,'brands_before':expected_brands,'brands_after':brands,'planned_project':planned}


def publish(db,site,remote,plan,report_id,actor='anton'):
    """Apply one saved plan with durable receipts; never repeat an unconfirmed POST."""
    from datetime import datetime,timezone
    from uuid import UUID,uuid5
    from urllib.parse import quote
    from app import models
    from app.project_pages import page_key,editable
    current=remote.project()
    if digest(current)!=plan['before_revision']:raise ValueError('Проект изменился после подготовки. Требуется обновить план.')
    receipts=[]
    def send(kind,key,before,after,path,payload,read,confirmed=lambda a,b:a==b):
        request_id=str(uuid5(UUID(report_id),site.id+':showcase-standard:'+kind+':'+key))
        op=db.get(models.ProjectPageEdit,request_id)
        actual=read(remote.project())
        if op:
            if op.status=='confirmed' and confirmed(actual,after):receipts.append(op.id);return
            raise ValueError('Предыдущая отправка требует проверки; автоматический повтор запрещён.')
        if actual!=before:raise ValueError('Изменился источник витрины: '+key)
        op=models.ProjectPageEdit(id=request_id,site_id=site.id,page_key=digest(['showcase-standard',kind,key]),requested_by=actor,
              fingerprint=digest(after),before_page={'node':before},after_page={'node':after},status='pending')
        db.add(op);db.commit()
        try:
            code,_=remote.request('POST',path,payload);op.response_status=code
        except Exception as exc:op.error=str(exc)[:500]
        try:ok=confirmed(read(remote.project()),after)
        except Exception as exc:ok=False;op.error=str(exc)[:500]
        op.status='confirmed' if ok else 'unknown'
        if not ok:op.error=op.error or 'Результат записи не подтверждён чтением Webdev.'
        db.commit();receipts.append(op.id)
        if not ok:raise ValueError(op.error)
    if getattr(remote,'client',None):remote.client.headers['Accept']='application/json;v=2'
    send('casinos','cards',plan['casinos_before'],plan['casinos_after'],'/projects/casinos',
         {'project':site.name,'casinos':plan['casinos_after'],'initiator':actor},lambda p:(p.get('data') or {}).get('casinos'))
    def get_template(p,name):
        found=next((s for s in p.get('shortcodes',[]) if s.get('name')==name),None)
        return {k:found[k] for k in ('name','data')} if found else None
    for before,after in [(None,s) for s in plan['new_templates']]+plan['templates']:
        after={k:after[k] for k in ('name','data')};before={k:before[k] for k in ('name','data')} if before else None
        filename=after['name'].removesuffix('.hbs')
        send('template',filename,before,after,'/projects/shortcode',
             {'project':site.name,'filename':filename,'contents':quote(after['data'],safe=";/?:@&=+$,-_.!~*'()#"),'initiator':actor},
             lambda p,name=after['name']:get_template(p,name))
    for before,after in plan['pages']:
        after=deepcopy(after);after['updatedTime']=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        def read_page(p,key=page_key(before)):
            return next((x for x in (p.get('data') or {}).get('pages',[]) if page_key(x)==key),None)
        send('page',page_key(before),before,after,'/projects/update',
             {'folder':site.name,'id':int(before['id']) if str(before['id']).isdigit() else before['id'],'page':after,'initiator':actor,'dateTime':after['updatedTime']},
             read_page,lambda a,b:a is not None and editable(a)==editable(b))
    actual=remote.project()
    home=next(p for p in actual['data']['pages'] if not str(p.get('slug') or '').strip('/'))
    if {identity(b) for b in page_inventory(actual,home)['brands']}!={identity(b) for b in plan['brands_before']}:raise ValueError('После записи не подтверждён исходный состав брендов.')
    return {'receipt_ids':receipts,'project':actual}
