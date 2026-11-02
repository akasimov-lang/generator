from copy import deepcopy
import pytest
from fastapi import HTTPException
from app.project_interlinking import interlinking_status, local_path
from app import project_pages as pages
from test_project_pages import setup


def paragraph(text):return {'type':'paragraph','data':{'text':text}}
def project():
 return {'settings':{'canon':'main.test'},'data':{'pages':[
  {'id':1,'slug':'/','content':{'blocks':[paragraph('<a href="/one/">One</a> <a href="/nested/two/">Two</a>')]}},
  {'id':2,'slug':'/one/','content':{'blocks':[paragraph('<a href="/">Brand</a>')]}},
  {'id':3,'slug':'/nested/two/','content':{'blocks':[paragraph('<a href="https://main.test/">Brand</a>')]}},
 ]}}


def test_requires_every_page_in_both_directions_and_does_not_mutate():
 p=project();before=deepcopy(p);status=interlinking_status(p,'main.test')
 assert status['complete'] and status['internal_count']==status['linked_from_home']==status['linked_to_home']==2
 assert p==before
 p['data']['pages'][2]['content']['blocks']=[]
 status=interlinking_status(p,'main.test')
 assert not status['complete'] and status['missing_to_home']==['/nested/two'] and status['linked_to_home']==1
 p['data']['pages'][0]['content']['blocks']=[paragraph('<a href="/one/">one</a>')]
 assert interlinking_status(p,'main.test')['missing_from_home']==['/nested/two']


@pytest.mark.parametrize('blocks',[
 [{'type':'header','data':{'text':'<a href="/">Brand</a>','level':2}}],
 [paragraph('<h3><a href="/">Brand</a></h3>')],
 [{'type':'raw','data':{'html':'<footer><a href="/">Brand</a></footer>'}}],
 [{'type':'shortcode','data':{'shortcode':'header'}}],
 [{'type':'table','data':{'withHeadings':True,'content':[['<a href="/">Brand</a>'],['body']]}}],
 [{'type':'faq','data':[{'question':'<a href="/">Brand</a>','answer':'answer'}]}],
 [paragraph('<a href="https://foreign.test/">Brand</a>')],
 [paragraph('<a href="javascript:location.href=\'/\'">Brand</a>')],
 [paragraph('<a href="/"><img src="/logo.png"></a>')],
 [paragraph('<a href="#section">same page</a>')],
])
def test_headings_templates_menu_external_links_and_self_anchors_do_not_complete(blocks):
 p=project();p['data']['pages'][1]['content']['blocks']=blocks
 assert not interlinking_status(p,'main.test')['complete']


@pytest.mark.parametrize('href', ['/', 'https://main.test/', '//main.test', '../', '/?source=article#home'])
def test_home_target_normalization(href):
 p=project();p['data']['pages'][1]['content']['blocks']=[paragraph(f'<a href="{href}">Brand</a>')]
 assert interlinking_status(p,'main.test')['complete']


@pytest.mark.parametrize('p', [{}, {'data':{'pages':[]}}, {'data':{'pages':[{'slug':'/'}]}}, {'data':{'pages':[{'slug':'/'},{'slug':'/'},{'slug':'/one/'}]}}])
def test_absent_internal_pages_or_ambiguous_home_is_gray(p):
 assert not interlinking_status(p,'main.test')['complete']


def test_content_lists_table_bodies_and_faq_answers_and_relative_nested_paths():
 p=project();p['data']['pages'][0]['content']['blocks']=[{'type':'list','data':{'items':[{'content':'<a href="one">one</a>','items':[{'content':'<a href="nested/two/">two</a>'}]}]}}]
 p['data']['pages'][1]['content']['blocks']=[{'type':'table','data':{'withHeadings':True,'content':[['Head'],['<a href="../">Brand</a>']]}}]
 p['data']['pages'][2]['content']['blocks']=[{'type':'faq','data':[{'question':'Question','answer':'<a href="../../">Brand</a>'}]}]
 assert interlinking_status(p,'main.test')['complete']
 assert local_path('/one/','https://main.test','/')=='/one'
 assert local_path('https://main.test:444/','https://main.test','/one/') is None


def test_endpoint_is_registered_before_page_key_route_and_is_read_only(setup):
 client,db,site,state=setup
 state['project']=project();before=deepcopy(state['project'])
 response=client.get(f'/sites/{site.id}/pages/interlinking')
 assert response.status_code==200 and response.json()['complete'] and response.json()['source']=='webdev'
 assert state['project']==before and not state['requests'] and not state['backup_requests']
 with pytest.raises(HTTPException) as error:
  pages.interlinking(site.id,{'username':'other','allowed_site_ids':[]},db)
 assert error.value.status_code==404


def test_unverified_cache_fallback_never_shows_complete(setup,monkeypatch):
 client,db,site,state=setup
 monkeypatch.setattr(pages,'read_project',lambda *args,**kwargs:(project(),'cache','Webdev unavailable'))
 result=client.get(f'/sites/{site.id}/pages/interlinking').json()
 assert not result['complete'] and result['warning']=='Webdev unavailable'
 assert result['linked_from_home']==result['linked_to_home']==2
