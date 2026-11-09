from types import SimpleNamespace
from app import maintenance_worklist as work, maintenance_reports as reports

def job(payload=None,entries=None):
 return SimpleNamespace(payload=payload or {},result={'entries':entries or []})

def test_plan_and_terminal_status_are_not_completed_work():
 row={'site_id':'x','status':'completed','plan':{'actions':['Добавить футер']}}
 assert work.describe(row,set(),verify_receipts=True)['done']==[]

def test_small_layout_report_is_work_list_but_large_inventory_is_not():
 row={'site_id':'x','showcase_actions':['Настроена витрина']}
 assert work.is_work_report(job(entries=[row]))
 assert not work.is_work_report(job({'task_type':'showcase_inventory'},[row]))
 assert not work.is_work_report(job({'repeat':True},[row]))
 assert not work.is_work_report(job(entries=[row]*11))

def test_confirmed_receipt_is_scoped_to_its_project():
 row={'site_id':'x','receipt_ids':['r'],'showcase_actions':['Настроена витрина'],'public_verification':{'ok':True}}
 assert not work.describe(row,{('other','r')},verify_receipts=True)['done']
 assert work.describe(row,{('x','r')},verify_receipts=True)['done']==['Настроена витрина']

def test_partial_breadcrumbs_keep_routing_failures():
 row={'site_id':'x','breadcrumbs_result':{'status':'partial','receipt_ids':['r'],'configured_internal_pages':37,'public_verified_pages':7,'routing_failures':['404']*30}}
 result=work.describe(row,{('x','r')},verify_receipts=True)
 assert '37' in result['done'][0] and '7' in result['checks'][0] and '30' in result['issues'][0]
