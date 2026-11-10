from types import SimpleNamespace
from uuid import uuid4
from app import models, auto_pilot, maintenance_reports, pilot_task_cache
from app.pilot_report_groups import group, partition
from app.report_list_visibility import hide
from test_pilot_task_cache import session

USER = {'username':'anton', 'allowed_site_ids':None}

def job(kind='maintenance_report', **payload):
    return SimpleNamespace(kind=kind, payload=payload, result={})


def test_single_included_brand_is_separate_from_mass_reglues():
    assert group(job('mass_reglue_list', planning_filter={'brands':['Lemon Casino']})) == 'brands'
    assert group(job('auto_pilot_preview', planning_filter={'brand':'Pelican'})) == 'brands'


def test_excluded_brands_do_not_turn_mass_program_into_brand_program():
    assert group(job('mass_reglue_list', planning_filter={'brands':['Lemon'], 'scope_mode':'exclude'})) == 'reglues'


def test_multiple_brands_and_general_keywords_stay_in_mass_group():
    assert group(job('mass_reglue_list', planning_filter={'brands':['Lemon','Pelican']})) == 'reglues'
    assert group(job('auto_pilot_preview', planning_filter={'brands':['Общие ключи']})) == 'reglues'


def test_brand_name_in_layout_title_is_not_a_brand_reglue():
    assert group(job(name='Pelican · Favicon на проектах без значка')) == 'layout'
    assert group(job(name='BetOnRed и Lemon · Микроразметка',task_type='structured_data')) == 'layout'


def test_showcase_inventory_and_mixed_maintenance_keep_showcase_group():
    assert group(job(task_type='showcase_inventory')) == 'showcases'
    assert group(job(task_type='site_maintenance',name='IonicKiss · витрина, дата и перелинковка')) == 'showcases'


def test_preserved_showcase_snapshot_does_not_classify_footer_as_showcase_work():
    report=job(task_type='site_maintenance', name='Mendoza · Хлебные крошки, футер', preserve_existing_showcases=True)
    report.result={'entries':[{'showcase_design':{'style':'original'}}]}
    assert group(report)=='layout'


def test_legacy_brand_programs_use_saved_network_operations():
    report=job(name='BetOnRed · Контент и сетки',text_revision_20261027=True)
    report.result={'entries':[{'network_operation_ids':['operation']}]}
    assert group(report)=='brands'
    assert group(job(task_type='brand_content_network_program'))=='brands'


def test_unknown_report_is_visible_in_other_and_explicit_intent_wins():
    report=job(task_type='generation_error_recovery',name='Восстановление генераций')
    assert group(report)=='other'
    report.payload['report_group']='layout'
    assert group(report)=='layout'


def test_counts_and_group_filter_precede_pagination_and_respect_search_permissions_and_hidden_reports():
    with session() as db:
        site=models.Site(name='visible.test',base_url='https://visible.test',publication_endpoint='/publish')
        denied=models.Site(name='private.test',base_url='https://private.test',publication_endpoint='/publish')
        db.add_all([site,denied]);db.commit()
        def add(name,s=site,actor='anton'):
            return maintenance_reports.upsert(db,str(uuid4()),name,actor,[s.id])
        first=add('Витрина — первая');second=add('Витрина — вторая');layout=add('Хлебные крошки')
        hidden=add('Витрина — скрытая');hide(db,hidden.id,USER)
        add('Витрина — чужая',actor='other');add('Витрина — недоступная',s=denied)
        user={**USER,'allowed_site_ids':[site.id]}
        view=auto_pilot.tasks(db,user,limit=1,group='showcases')
        assert view['total']==2 and view['has_more'] and len(view['items'])==1
        assert view['group_counts']=={'all':3,'layout':1,'showcases':2,'brands':0,'reglues':0,'other':0}
        next_page=auto_pilot.tasks(db,user,offset=1,limit=1,group='showcases')
        assert not next_page['has_more'] and view['items'][0]['id']!=next_page['items'][0]['id']
        assert next_page['group_counts']==view['group_counts']
        found=auto_pilot.tasks(db,user,q='первая',group='showcases')
        assert found['total']==1 and found['items'][0]['id']==first.id and found['group_counts']['all']==1
        empty=auto_pilot.tasks(db,user,group='brands')
        assert empty['total']==0 and empty['group_counts']['all']==3


def test_grouped_cache_never_returns_another_group(monkeypatch):
    with session() as db:
        calls=[]
        def build(*args,group='all',**kwargs):
            calls.append(group);return {'items':[],'group':group}
        monkeypatch.setattr(auto_pilot,'tasks',build)
        assert pilot_task_cache.tasks(db,USER,group='layout')['group']=='layout'
        assert pilot_task_cache.tasks(db,USER,group='brands')['group']=='brands'
        assert pilot_task_cache.tasks(db,USER,group='layout')['group']=='layout'
        assert calls==['layout','brands']
