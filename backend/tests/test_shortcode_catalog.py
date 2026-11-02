import copy
from app import project_pages as pages
from test_project_pages import setup

def test_inventory_counts_saved_site_references_without_exposing_template_code(setup):
    client,db,site,state=setup
    project=state['project']
    project['data']['pages'][1]['content']['blocks'] += [
        {'type':'shortcode','data':{'shortcode':'promo','custom':'keep'}},
        {'type':'shortcode','data':{'shortcode':'promo.hbs'}},
        {'type':'shortcode','data':{'shortcode':'undefined'}}]
    project['data']['pages'][0]['content']['blocks']=[{'type':'shortcode','data':'promo'}]
    before=copy.deepcopy(project)
    key=pages.page_key(project['data']['pages'][1])
    result=client.get(f'/sites/{site.id}/pages/{key}?refresh=true').json()
    assert result['shortcodes']==[
        {'name':'promo','uses_on_site':3,'pages_count':2,'defined':True},
        {'name':'undefined','uses_on_site':1,'pages_count':1,'defined':False}]
    assert result['revision']==pages.digest(before['data']['pages'][1])
    assert 'Original promo' not in str(result['shortcodes'])
    assert state['project']==before and not state['requests']

def test_missing_definitions_are_unknown_instead_of_falsely_missing():
    project={'data':{'pages':[{'id':'1','slug':'/','content':{'blocks':[{'type':'shortcode','data':{'shortcode':'banner'}}]}}]}}
    assert pages.shortcode_catalog(project)==[{'name':'banner','uses_on_site':1,'pages_count':1,'defined':None}]
