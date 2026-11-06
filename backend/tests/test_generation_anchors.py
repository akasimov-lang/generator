from copy import deepcopy
from app import generation_anchors as anchors,models
from test_generation_modes import db,make_site
from test_project_pages import setup
import pytest


def item(db,site):
 task=models.GenerationTask(title='Content',geo='PL',language='pl',topics_count=1)
 row=models.ContentItem(task=task,site_id=site.id,topic='Article',slug='/article/',generated_json={},idempotency_key='anchor-test')
 db.add(row);db.commit();return row


def test_defaults_cover_all_polish_general_sites_and_all_monobrand_sites(db):
 site=make_site(db);site.site_type='general';site.cache_geo='pl_PL'
 assert anchors.settings(db,site)['anchors']==list(anchors.POLISH)
 site.site_type='monobrand';site.brand='BetOnRed';site.cache_geo='CZ'
 assert anchors.settings(db,site)['anchors']==['BetOnRed']
 site.site_type=None;site.brand='Общие ключи';site.cache_geo='PL'
 assert anchors.settings(db,site)['anchors']==list(anchors.POLISH)
 site.cache_geo='CZ';assert not anchors.settings(db,site)['anchors']


def test_pools_accept_commas_newlines_deduplicate_and_are_per_site(db):
 site=make_site(db);other=models.Site(name='other.test',base_url='https://other.test',publication_endpoint='/publish',brand='Other');db.add(other);db.commit()
 assert anchors.save_settings(db,site,'Brand, Other anchor\nBrand\n  third   anchor')['anchors']==['Brand','Other anchor','third anchor']
 assert anchors.settings(db,other)['anchors']==['Other']


def test_random_choice_is_saved_before_linking_and_retries_do_not_reroll(db,monkeypatch):
 site=make_site(db);site.site_type='general';site.cache_geo='PL';row=item(db,site);calls=[]
 def choice(pool):calls.append(pool);return pool[6]
 monkeypatch.setattr(anchors.secrets,'choice',choice)
 payload={'pages':[{'slug':'/article/','content':{'blocks':[{'type':'header','data':{'text':'Kasyna internetowe','level':2}},{'type':'paragraph','data':{'text':'Przewodnik po grach.'}},{'type':'paragraph','data':{'text':'Jak wybrać najbardziej wypłacalne kasyno online dla siebie.'}}]}},{'slug':'/','content':{'blocks':[]}}]}
 before=deepcopy(payload);result=anchors.apply_home_anchor(db,row,site,payload)
 assert len(calls)==1 and row.generation_context['homepage_anchor']==anchors.POLISH[6]
 assert result['pages'][0]['content']['blocks'][0]==before['pages'][0]['content']['blocks'][0]
 assert '<a href="/">najbardziej wypłacalne kasyno online</a>' in result['pages'][0]['content']['blocks'][2]['data']['text']
 assert result['pages'][1]==before['pages'][1] and payload==before
 assert anchors.apply_home_anchor(db,row,site,result)==result and len(calls)==1


def test_old_generated_text_gets_one_anchor_at_publication_without_heading_link(db,monkeypatch):
 site=make_site(db);site.site_type='monobrand';site.brand='BetOnRed';row=item(db,site)
 payload={'pages':[{'slug':'/bonus/','content':{'blocks':[{'type':'header','data':{'text':'BetOnRed','level':2}},{'type':'paragraph','data':{'text':'Bonus guide.'}}]}}]}
 result=anchors.apply_home_anchor(db,row,site,payload)
 assert result['pages'][0]['content']['blocks'][0]==payload['pages'][0]['content']['blocks'][0]
 assert result['pages'][0]['content']['blocks'][1]['data']['text'].count('<a href="/">BetOnRed</a>')==1
 assert anchors.apply_home_anchor(db,row,site,result)==result


def test_anchors_endpoint_defaults_and_save_are_not_page_writes(setup):
 client,db,site,state=setup;site.brand='Общие ключи';site.cache_geo='PL';db.commit();path=f'/sites/{site.id}/pages/generation-anchors'
 assert client.get(path).json()['anchors']==list(anchors.POLISH)
 assert client.put(path,json={'anchors':'first anchor,second anchor\nfirst anchor'}).json()['anchors']==['first anchor','second anchor']
 assert client.get(path).json()['source']=='custom'
 assert client.put(path,json={'anchors':'<a>HTML</a>'}).status_code==400
 assert client.put(path,json={'anchors':''}).status_code==400
 assert not state['requests'] and not state['backup_requests']


def test_independent_choices_can_repeat_without_balancing(db,monkeypatch):
 site=make_site(db);site.site_type='general';site.cache_geo='PL';first=item(db,site)
 second=models.ContentItem(task_id=first.task_id,site_id=site.id,topic='Second',slug='/second/',generated_json={},idempotency_key='second-anchor')
 db.add(second);db.commit();calls=[]
 monkeypatch.setattr(anchors.secrets,'choice',lambda pool:(calls.append(list(pool)) or pool[0]))
 assert anchors.select_anchor(db,first,site)==anchors.select_anchor(db,second,site)==anchors.POLISH[0]
 assert len(calls)==2 and all(len(pool)==10 for pool in calls)


def test_heading_links_are_removed_while_visible_heading_text_is_preserved(db):
 site=make_site(db);site.site_type='monobrand';site.brand='BetOnRed';row=item(db,site)
 payload={'pages':[{'slug':'/bonus/','content':{'blocks':[{'type':'header','data':{'text':'About <a href="/">BetOnRed</a> <strong>bonuses</strong>','level':2}},{'type':'paragraph','data':{'text':'BetOnRed article.'}}]}}]}
 result=anchors.apply_home_anchor(db,row,site,payload)
 assert result['pages'][0]['content']['blocks'][0]['data']['text']=='About BetOnRed <strong>bonuses</strong>'
 assert '<a href="/">BetOnRed</a>' in result['pages'][0]['content']['blocks'][1]['data']['text']


@pytest.mark.parametrize('mode,kind', [('article','article'), ('menu_page','article'), ('menu_page','technical_page')])
def test_every_new_general_page_gets_relative_home_link_even_with_legacy_optout(db, mode, kind):
 site=make_site(db);site.site_type='general';site.brand='Общие ключи';site.cache_geo='DE';site.cache_language='de';site.cache_canon='old.test'
 row=item(db,site);row.section_content_mode=mode;row.generation_context={'homepage_interlinking':False,'content_kind':kind}
 payload={'pages':[{'slug':'/article/','content':{'blocks':[{'type':'paragraph','data':{'text':'Informationen über diese Seite und ihre Inhalte.'}}]}}]}
 result=anchors.apply_home_anchor(db,row,site,payload)
 text=result['pages'][0]['content']['blocks'][0]['data']['text']
 assert text.count('<a href="/">')==1 and 'Startseite' in text and 'old.test' not in text
 assert row.generation_context['homepage_interlinking'] is True
 site.cache_canon='new.test'
 assert anchors.apply_home_anchor(db,row,site,result)==result


def test_new_page_without_text_paragraph_cannot_pass_publication_link_check(db):
 site=make_site(db);site.site_type='general';site.cache_language='de';site.cache_geo='DE';row=item(db,site)
 with pytest.raises(ValueError,match='абзаца'):
  anchors.apply_home_anchor(db,row,site,{'pages':[{'slug':'/article/','content':{'blocks':[]}}]})
