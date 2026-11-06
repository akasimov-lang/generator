from test_project_pages import setup
from types import SimpleNamespace
from datetime import datetime,timezone
from app.showcase_inventory import rendered_brands,brand_delta,page_inventory
from app.showcase_history import receipt_changes,summary_text
from app.maintenance_reports import view


def test_rendered_brand_cards_exclude_star_and_payment_icons():
    markup='<div class="casino-card"><h3>Star Casino</h3><img alt="full star" src="star.svg"><img alt="Visa.png" src="visa.png"><img alt="Star Casino" src="logo.png"></div>'
    assert rendered_brands(markup)==['Star Casino']


def test_text_only_brand_cards_are_distinguished_from_article_sections():
    markup='<div class="bg-brand-card"><h3>JackpotCity Casino</h3><p>4.9 / 5.0</p><p>Min. Deposit: $10</p></div><div class="bg-brand-card"><h3>Ontario Regulation</h3><p>Licence and consumer safety</p></div>'
    assert rendered_brands(markup)==['JackpotCity Casino']


def test_brand_delta_counts_membership_not_alias_or_order_changes():
    assert brand_delta(['Casino DrückGlück','Roby Casino'],['Roby Casino casino','DrückGlück','Betinia'])=={'before':2,'after':3,'added':1,'removed':0,'added_brands':['Betinia'],'removed_brands':[]}
    assert brand_delta(['Old'],['New'])['removed_brands']==['Old']


def test_missing_before_does_not_invent_added_count():
    delta=brand_delta(None,['New'])
    assert delta['before'] is None and delta['added'] is None
    assert 'не подтверждено' in summary_text(delta)


def test_unused_dataset_is_not_an_installed_showcase():
    project={'data':{'casinos':{'standard':[{'brand':'Unused'}]},'pages':[]},'layout':'','shortcodes':[]}
    assert page_inventory(project,{'slug':'/','content':{'blocks':[]}})['presence']=='none'


def test_receipt_counts_only_changed_group_and_ignores_logo_gallery():
    before={'casinos':{'dk':[{'brand':'A'},{'brand':'B'}],'basic':[{'brand':'logo'}],'unused':[{'brand':'X'}]}}
    after={'casinos':{'dk':[{'brand':'B'},{'brand':'C'}],'basic':[{'brand':'logo2'}],'unused':[{'brand':'X'}]}}
    changes=receipt_changes(before,after)
    assert len(changes)==1
    assert changes[0][1]=={'before':2,'after':2,'added':1,'removed':1,'added_brands':['C'],'removed_brands':['A']}


def test_inventory_report_returns_compact_evidence_without_full_project_backups():
    now=datetime.now(timezone.utc)
    job=SimpleNamespace(id='id',created_at=now,started_at=now,updated_at=now,finished_at=now,status='completed',payload={'task_type':'showcase_inventory','name':'Inventory','scope':{'excluded_today':[]}},result={'entries':[{'site_id':'x','project':'x.test','status':'completed','before':{'pages':['large backup']},'migration':{'status':'planned','plan':{'large':'source backup'}},'inventory':{'internal_total':0}}]})
    report=view(job)
    assert 'before' not in report['entries'][0]
    assert 'plan' not in report['entries'][0]['migration']
    assert report['progress']['unit']=='projects'
    assert report['entries'][0]['inventory']['internal_total']==0


def test_inventory_audit_creates_one_project_history_record_and_no_site_mutation(setup):
    from uuid import uuid4
    from app import maintenance_reports,models
    from app.showcase_history import events
    _,db,site,state=setup
    before=site.showcase_payload
    row={'site_id':site.id,'status':'completed','inventory':{'home':{'public':{'presence':'present','brands':['A','B','C']}}}}
    job=maintenance_reports.upsert(db,uuid4(),'Audit','anton',[site.id],[row],status='completed')
    maintenance_reports.upsert(db,job.id,'Audit','anton',[site.id],[row],status='completed')
    history=events(db,site.id)
    assert len(history)==1
    assert history[0]['showcase_delta']['before']==history[0]['showcase_delta']['after']==3
    assert history[0]['showcase_delta']['added']==history[0]['showcase_delta']['removed']==0
    assert site.showcase_payload==before and not state['requests']


def test_text_only_promo_cards_count_as_showcase_brands():
    assert rendered_brands('<div class="casino-card"><h3 class="casino-title">Kingsbet</h3><div class="promo-value">555 FREE SPINŮ</div><button>Otevřít casino</button></div>')==['Kingsbet']


def test_running_showcase_work_keeps_unknown_result_until_publication_is_confirmed(setup):
    from uuid import uuid4
    from app import maintenance_reports
    from app.showcase_history import events
    _,db,site,_=setup
    row={'site_id':site.id,'status':'running','migration':{'status':'running','started_at':'2026-11-06T00:00:00Z','before_count':3}}
    job=maintenance_reports.upsert(db,uuid4(),'Migration','anton',[site.id],[row])
    first=events(db,site.id)
    assert len(first)==1 and first[0]['status']=='running' and not first[0]['confirmed']
    assert first[0]['showcase_delta']['after'] is None and first[0]['showcase_delta']['added'] is None
    row.update(status='completed',showcase_change={'before':3,'after':3,'added':0,'removed':0})
    maintenance_reports.upsert(db,job.id,'Migration','anton',[site.id],[row],status='completed')
    final=events(db,site.id)
    assert len(final)==1 and final[0]['confirmed'] and final[0]['showcase_delta']['after']==3


def test_confirmed_migration_with_audit_baseline_records_work_not_read_only_audit(setup):
    from uuid import uuid4
    from app import maintenance_reports
    from app.showcase_history import events
    _,db,site,_=setup
    row={'site_id':site.id,'status':'completed','inventory':{'home':{'public':{'presence':'present','brands':['A']}}},
         'migration':{'status':'confirmed','started_at':'2026-11-06T00:00:00Z'},
         'showcase_change':{'before':1,'after':2,'added':1,'removed':0,'description':'Стандартная витрина опубликована.'}}
    maintenance_reports.upsert(db,uuid4(),'Migration','anton',[site.id],[row],status='completed')
    history=events(db,site.id)
    assert len(history)==1 and history[0]['showcase_delta']['after']==2
    assert 'Изменения сайта не выполнялись' not in history[0]['message']
    assert 'Стандартная витрина опубликована' in history[0]['message']
