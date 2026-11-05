from types import SimpleNamespace
from app.maintenance_evidence import enrich


def test_toc_counts_require_confirmed_save_and_public_check():
    job=SimpleNamespace(payload={'task_type':'toc_repair'})
    rows=[{'page_results':[{'slug':'/a','changed':True,'status':'confirmed','public':{'verified':True}},{'slug':'/b','changed':True,'status':'unknown'},{'slug':'/c','changed':False,'status':'already_correct'}],'pages_checked':8}]
    facts={x['label']:x['value'] for x in enrich(job,rows)[0]['facts']}
    assert facts['Страниц с содержанием']=='3'
    assert facts['Страниц с ошибкой до исправления']=='2'
    assert facts['Страниц исправлено и сохранено']=='1'
    assert facts['Проверено исправлений на сайте']=='1'
    assert 'facts' not in rows[0]


def test_showcase_plan_does_not_become_published_result():
    job=SimpleNamespace(payload={'task_type':'showcase_audit'})
    row={'project':'other','audit':{'rows':[]},'showcase_plan':{'brands':['A','B','C'],'meta_recommendation':'Recommendation'}}
    facts={x['label']:x['value'] for x in enrich(job,[row])[0]['facts']}
    assert facts['Брендов до']=='Не подтверждено'
    assert facts['Брендов после']=='Без подтверждённых изменений'
    assert facts['План — количество брендов']=='3'
