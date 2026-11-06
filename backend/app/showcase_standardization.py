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
    bonus=node.first({'bonus-value','bonusText','casinoBonus','card_bonus','promo-value'})
    if not bonus:
        bonus=next((n for n in node.walk() if any('bonus' in c.lower() for c in n.classes) and re.search(r'\d',n.text()) and len(n.text())<500),None)
    if not bonus:
        bonus=next((n for n in node.walk() if n.tag in {'p','div','span','strong'} and re.search(r'\d.*(?:%|free spins|\bFS\b|Welcome Package)|(?:\$|€|£)\s*\d',n.text(),re.I) and len(n.text())<180 and not re.search(r'Min\. Deposit|Payout|Payments:',n.text(),re.I)),None)
    if not fields.get('bonus') and bonus:fields['bonus']=bonus.text()
    if not fields.get('bonus'):raise ValueError('Не определено точное бонусное предложение: '+brand)
    from app.showcase_brands import plain
    controls=[n for n in node.walk() if getattr(n,'closed',False) and (n.tag=='a' and (n.attrs.get('href') or n.attrs.get('onclick') or n.attrs.get('data-split')) or n.tag=='button') and plain(markup[n.start:n.end])]
    actions=[markup[n.start:n.end] for n in controls if not any(parent.start<n.start and parent.end>n.end for parent in controls)]
    if not fields.get('rating'):
        match=re.search(r'\b\d+(?:[.,]\d+)?\s*/\s*(?:5|10)\b',node.text())
        if match:fields['rating']=match.group()
    return {'brand':brand,'bonus':fields['bonus'],'rating':fields.get('rating',''),'conditions':node.text(),
            'logo_src':image.attrs['src'] if image else None,'actions_html':' '.join(dict.fromkeys(actions)),
            'icons_html':' '.join(markup[n.start:n.end] for n in node.walk() if n.tag=='img' and n is not image and not re.search(r'star|rating|check|tick',str(n.attrs),re.I))}


def table_records(block):
    cells=(block.get('data') or {}).get('content') or []
    rows=table_rows(cells,'table')
    if not rows or len(rows)!=len(cells)-1:raise ValueError('Таблица содержит неподтверждённые строки.')
    from app.showcase_brands import plain
    result=[]
    for row,values in zip(rows,cells[1:]):
        fields={f['key']:f['value'] for f in row['fields']}
        bonus_column=next(i for i,label in enumerate(cells[0]) if 'bonus' in plain(label).lower())
        bonus_markup=str(values[bonus_column]);cleaned=bonus_markup
        controls=[n for n in PositionedTree(bonus_markup).root.walk() if n.tag in {'a','button'} and getattr(n,'closed',False)]
        for control in sorted(controls,key=lambda n:n.start,reverse=True):cleaned=cleaned[:control.start]+cleaned[control.end:]
        if plain(cleaned):fields['bonus']=plain(cleaned)
        cell_markup=' '.join(str(x) for x in values);tree=PositionedTree(cell_markup).root
        image=next((n for n in tree.walk() if n.tag=='img' and valid_logo(n.attrs.get('alt')) and safe_url(n.attrs.get('src'))),None)
        actions=[cell_markup[n.start:n.end] for n in tree.walk() if getattr(n,'closed',False) and n.tag in {'a','button'} and (n.attrs.get('href') or n.tag=='button') and plain(cell_markup[n.start:n.end])]
        result.append({'brand':row['brand'],'bonus':fields['bonus'],'rating':fields.get('rating',''),
                       'conditions':'\n'.join(plain(label)+': '+plain(value) for label,value in zip(cells[0],values)),
                       'logo_src':image.attrs['src'] if image else None,'actions_html':' '.join(actions),
                       'icons_html':' '.join(cell_markup[n.start:n.end] for n in tree.walk() if n.tag=='img' and n is not image and not re.search(r'star|rating|check|tick',str(n.attrs),re.I))})
    return result


def markup_tables(markup):
    result=[]
    for node in PositionedTree(markup).root.walk():
        if node.tag!='table' or not getattr(node,'closed',False):continue
        cells=[]
        for row in node.walk():
            if row.tag!='tr':continue
            parent=row.parent
            while parent and parent.tag!='table':parent=parent.parent
            if parent is not node:continue
            cells.append([markup[cell.start:cell.end] for cell in row.children if hasattr(cell,'tag') and cell.tag in {'td','th'} and getattr(cell,'closed',False)])
        try:records=table_records({'data':{'content':cells}})
        except ValueError:continue
        if records:result.append((node,records))
    return result


STYLE='''<style>
.pp-standard{container-type:inline-size;display:grid;gap:16px;width:100%;grid-column:1/-1;flex:1 0 100%;margin:20px 0;font-family:inherit}
.pp-standard.pp-standard .pp-standard-card{display:grid;grid-template-columns:minmax(130px,180px) minmax(0,1fr) minmax(130px,200px);gap:20px;align-items:center;width:100%;box-sizing:border-box;padding:22px;border:1px solid #8b94a666;border-radius:14px;background:var(--showcase-card-bg,#fff);color:var(--showcase-card-color,#1c2638)}
.pp-standard .pp-standard-brand{min-width:0;text-align:center}.pp-standard .pp-standard-brand img{display:block;width:150px;max-width:100%;height:82px;object-fit:contain;margin:0 auto 10px}.pp-standard .casino-brand{display:block;overflow-wrap:anywhere;font-size:18px;line-height:1.3;font-weight:700}
.pp-standard .bonus-value{font-size:20px;line-height:1.4;font-weight:700;overflow-wrap:anywhere}.pp-standard .casino-rating{display:block;margin-top:8px;font-weight:600}.pp-standard .pp-standard-actions{display:grid;gap:8px}.pp-standard .pp-standard-actions a,.pp-standard .pp-standard-actions button{display:block;padding:12px;border-radius:8px;background:var(--showcase-button-bg,#3557d6);color:#fff;text-decoration:none;text-align:center;font-weight:700;line-height:1.3}
.pp-standard .pp-standard-terms{grid-column:1/-1;margin:0;font-size:13px}.pp-standard .pp-standard-terms p{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.5}.pp-standard .pp-standard-actions a>button{padding:0;background:transparent;border:0;color:inherit;width:100%}.pp-standard .pp-standard-icons{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.pp-standard .pp-standard-icons img{height:24px!important;max-height:24px!important;width:auto;object-fit:contain}.pp-standard summary{cursor:pointer}
@container(max-width:640px){.pp-standard.pp-standard .pp-standard-card{grid-template-columns:1fr}}
@media(max-width:640px){.pp-standard.pp-standard .pp-standard-card{grid-template-columns:1fr;gap:14px;padding:16px}.pp-standard .casino-brand{font-size:16px}.pp-standard .bonus-value{text-align:center;font-size:18px}.pp-standard .pp-standard-actions,.pp-standard .pp-standard-terms{grid-column:1}}
</style>'''


def template(group,details_label):
    v=lambda key:'{{findValueInObjectByKey this "'+key+'" "value" false}}'
    return STYLE+'<section class="pp-standard">{{#each casinos.'+group+'}}<article class="casino-card pp-standard-card"><div class="pp-standard-brand">{{#if (findLogo this ../casinos.basic "src")}}<img src="{{findLogo this ../casinos.basic "src"}}" alt="'+v('brand')+'" loading="lazy">{{/if}}<strong class="casino-brand">'+v('brand')+'</strong><span class="casino-rating">'+v('rating')+'</span></div><div class="bonus-value">'+v('bonus')+'</div><div class="pp-standard-actions">{{{findValueInObjectByKey this "actions_html" "value" false}}}</div><details class="pp-standard-terms"><summary>'+escape(details_label)+'</summary><p>'+v('conditions')+'</p><div class="pp-standard-icons">{{{findValueInObjectByKey this "icons_html" "value" false}}}</div></details></article>{{/each}}</section>'


def prepare(project,public_html,expected_brands,details_label='Details',public_pages=None):
    """Prepare every connected legacy table/card block, failing closed on ambiguity."""
    planned=deepcopy(project);data=planned.setdefault('data',{});casinos=data.setdefault('casinos',{})
    if not isinstance(casinos,dict):raise ValueError('Формат данных casinos требует отдельного адаптера.')
    basic=casinos.setdefault('basic',[])
    if not isinstance(basic,list):raise ValueError('Не определён формат галереи логотипов.')
    gallery=next((f for f in basic if f.get('key')=='logo' and f.get('type')=='gallery'),None)
    if gallery is None:gallery={'key':'logo','type':'gallery','data':[]};basic.append(gallery)
    if not isinstance(gallery.get('data'),list):raise ValueError('Не определена галерея логотипов.')
    public_pages={**(public_pages or {}),'/':public_html}
    def source_records(source_nodes,public_markup):
        candidates=card_nodes(public_markup);result=[]
        for source_node,brand in source_nodes:
            matches=[n for n,b in candidates if identity(b)==identity(brand)]
            exact=[n for n in matches if n.text()==source_node.text()]
            selected=exact or matches
            if not selected:raise ValueError('Не подтверждена публичная карточка: '+brand)
            records=[card_record(public_markup,n,brand) for n in selected]
            unique={digest(record) for record in records}
            if len(unique)>1:
                class_matches=[n for n in selected if n.classes==source_node.classes]
                records=[card_record(public_markup,n,brand) for n in class_matches]
                if not records or len({digest(record) for record in records})>1:raise ValueError('Неоднозначное предложение бренда: '+brand)
            result.append(records[0])
        return result
    original_defs={s['name'].removesuffix('.hbs'):s for s in project.get('shortcodes',[]) if isinstance(s,dict) and isinstance(s.get('data'),str)}
    used=set();owners={}
    def visit(name,slug,path=()):
        name=str(name).removesuffix('.hbs')
        if name in path or name in {'header','footer','menu','navigation'}:return
        used.add(name);owners.setdefault(name,set()).add(slug)
        for sub in re.findall(r'{{>\s*["\']?([\w .-]+?)["\']?\s*}}',str(original_defs.get(name,{}).get('data',''))):visit(sub,slug,(*path,name))
    for page in data.get('pages',[]):
        for block in (page.get('content') or {}).get('blocks',[]):
            if block.get('type')=='shortcode' and isinstance(block.get('data'),dict):visit(block['data'].get('shortcode',''),page.get('slug') or '/')
    for sub in re.findall(r'{{>\s*["\']?([\w .-]+?)["\']?\s*}}',str(project.get('layout') or '')):visit(sub,'/')
    groups={};new_templates=[];logo_ids={str(x.get('id')) for x in gallery['data']};next_logo=1790000000000
    def group_for(records):
        nonlocal next_logo
        key=digest(records)
        if key in groups:return groups[key]
        index=len(groups)+1
        group='pagepilot_standard_'+str(index);name='casinos-standard-'+str(index)
        while group in casinos or name in original_defs:
            index+=1;group='pagepilot_standard_'+str(index);name='casinos-standard-'+str(index)
        cards=[]
        for record in records:
            fields=[{'key':key,'type':'text','value':record.get(key,'')} for key in ('brand','bonus','rating','conditions','actions_html','icons_html')]
            if record.get('logo_src'):
                while str(next_logo) in logo_ids:next_logo+=1
                logo_ids.add(str(next_logo));gallery['data'].append({'id':next_logo,'src':record['logo_src'],'alt':record['brand']})
                fields.append({'key':'logo','type':'logo','id':next_logo});next_logo+=1
            cards.append(fields)
        casinos[group]=cards;new_templates.append({'name':name+'.hbs','data':template(group,details_label)});groups[key]=name
        return name
    def markup_edits(markup,public_variants):
        tables=markup_tables(markup)
        nodes=[(n,b) for n,b in card_nodes(markup) if not any(t.start<=n.start and t.end>=n.end for t,_ in tables)]
        tables=[(t,r) for t,r in tables if not any(n.start<=t.start and n.end>=t.end for n,_ in nodes)]
        edits=[]
        segments=[]
        for node,brand in nodes:
            previous=segments[-1][-1][0] if segments else None
            between=re.sub(r'<!--.*?-->','',markup[previous.end:node.start],flags=re.S).strip() if previous else ''
            if previous is None or previous.parent is not node.parent or between:segments.append([])
            segments[-1].append((node,brand))
        for segment in segments:
            own=None
            for public_variant in public_variants:
                try:own=source_records(segment,public_variant);break
                except ValueError:continue
            if own is None:raise ValueError('Не подтверждены публичные карточки подключённого источника.')
            name=group_for(own)
            edits.extend((node.start,node.end,name if index==0 else None) for index,(node,_) in enumerate(segment))
        edits.extend((node.start,node.end,group_for(records)) for node,records in tables)
        edits.sort()
        if any(edits[i][1]>edits[i+1][0] for i in range(len(edits)-1)):raise ValueError('Пересекаются источники витрины; автоматическая замена остановлена.')
        return edits
    changed_templates=[];changed_pages=[]
    for name in sorted(used):
        source=original_defs.get(name)
        if not source:continue
        markup=source['data']
        if name.startswith('casinos-standard-') and '{{#each casinos.pagepilot_standard_' in markup:continue
        edits=markup_edits(markup,[public_pages[slug] for slug in sorted(owners.get(name,{'/'})) if slug in public_pages])
        if not edits:continue
        new=markup
        for start,end,replacement in reversed(edits):new=new[:start]+('{{> '+replacement+'}}' if replacement else '')+new[end:]
        changed={**source,'data':new};changed_templates.append((source,changed))
        actual=next(s for s in planned['shortcodes'] if s.get('name')==source['name']);actual['data']=new
    for page in data.get('pages',[]):
        original=deepcopy(page);blocks=[];changed=False
        for block in (page.get('content') or {}).get('blocks',[]):
            kind=block.get('type');value=block.get('data') or {}
            if kind=='table' and isinstance(value,dict):
                try:records=table_records(block)
                except ValueError:blocks.append(block);continue
                if not records:blocks.append(block);continue
                name=group_for(records);blocks.append({'id':block.get('id'),'type':'shortcode','data':{'shortcode':name}});changed=True
            elif kind in {'code','raw'} and isinstance(value,dict):
                field='code' if kind=='code' else 'html';markup=value.get(field,'')
                edits=markup_edits(markup,[public_pages.get(page.get('slug') or '/',public_html)])
                if not edits:blocks.append(block);continue
                cursor=0
                for index,(start,end,name) in enumerate(edits):
                    fragment=markup[cursor:start]
                    if fragment:blocks.append({**block,'id':str(block.get('id','code'))+'-part-'+str(index),'data':{**value,field:fragment}})
                    if name:blocks.append({'id':str(block.get('id','code'))+'-standard-'+str(index),'type':'shortcode','data':{'shortcode':name}})
                    cursor=end
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
    if {identity(x) for x in brands}!={identity(x) for x in expected_brands}:raise ValueError('Состав брендов после подготовки не совпадает с исходным. Было: '+', '.join(expected_brands)+'; подготовлено: '+', '.join(brands))
    for old_page in (project.get('data') or {}).get('pages',[]):
        new_page=next((p for p in data.get('pages',[]) if p.get('id')==old_page.get('id') and p.get('slug')==old_page.get('slug')),None)
        if new_page is None:raise ValueError('Не найдена страница после подготовки.')
        old_inventory=page_inventory(project,old_page)
        old_brands=old_inventory['brands']
        if old_brands and old_inventory['complete'] and {identity(x) for x in old_brands}!={identity(x) for x in page_inventory(planned,new_page)['brands']}:
            raise ValueError('Изменился состав витрины страницы '+str(old_page.get('slug') or '/'))
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
    if digest(current)!=plan['before_revision']:
        # Resume the confirmed, still-unused dataset stage without resending it.
        saved_id=str(uuid5(UUID(report_id),site.id+':showcase-standard:'+plan['before_revision']+':casinos:cards'))
        saved=db.get(models.ProjectPageEdit,saved_id) if db is not None else None
        restored=deepcopy(current)
        if saved and saved.status=='confirmed' and (current.get('data') or {}).get('casinos')==plan['casinos_after']:
            if plan['casinos_before'] is None:restored.get('data',{}).pop('casinos',None)
            else:restored.setdefault('data',{})['casinos']=plan['casinos_before']
        if digest(restored)!=plan['before_revision'] and saved and saved.status=='confirmed' and plan['casinos_before'] is None:
            restored.setdefault('data',{})['casinos']=None
        if digest(restored)!=plan['before_revision']:raise ValueError('Проект изменился после подготовки. Требуется обновить план.')
    receipts=[]
    def send(kind,key,before,after,path,payload,read,confirmed=lambda a,b:a==b):
        request_id=str(uuid5(UUID(report_id),site.id+':showcase-standard:'+plan['before_revision']+':'+kind+':'+key))
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
        if before is None:
            send('template_create',filename,None,{'name':after['name'],'created':True},'/projects/shortcode/new',
                 {'project':site.name,'filename':filename,'requiredPermission':'create-shortcode','initiator':actor},
                 lambda p,name=after['name']:get_template(p,name),lambda a,b:a is not None and a.get('name')==b['name'])
            before=get_template(remote.project(),after['name'])
        send('template_save',filename,before,after,'/projects/shortcode',
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
