import asyncio,json
from copy import deepcopy
from sqlalchemy import select
import pytest
from app import models,services,structure_research as research
from test_generation_modes import db,make_site

TOPIC='Nowe kasyna online w Polsce warunki bonusów'


def make(db):
 site=make_site(db);site.brand='Общие ключи';site.site_type='general';site.cache_geo='PL';site.cache_language='pl'
 provider=models.AiProvider(name='Gemini',provider_type='gemini',endpoint_url='https://example.test',model='test',api_key='test',is_active=True)
 db.add(provider);db.flush()
 task=models.GenerationTask(title='Menu',site_id=site.id,ai_provider_id=provider.id,geo='PL',language='pl',topics_count=1,generation_mode='menu_structure',collect_competitors=True)
 item=models.ContentItem(task=task,site_id=site.id,topic='Nowe Kasyna',slug='/nowe-kasyna/',section_content_mode='menu_page',generation_context={'current_section':{'name':'Nowe Kasyna','path':'/nowe-kasyna/','breadcrumb':['Kasyna','Nowe Kasyna']}},generated_json={},idempotency_key='short-label')
 db.add(item);db.commit();return site,task,item


def response(topic):return {'candidates':[{'content':{'parts':[{'text':json.dumps({'topic':topic},ensure_ascii=False)}]}}]}


def test_topic_precedes_queries_and_serp_and_is_reused(db,monkeypatch):
 site,task,item=make(db);events=[]
 assert services.ensure_competitor_queries(db,item,'PL','pl')==[] and item.competitor_research_status=='topic_pending'
 original=(item.topic,item.slug,deepcopy(item.generation_context['current_section']))
 async def gemini(provider,prompt):events.append(('topic',prompt));return response(TOPIC)
 async def serp(provider,keyword,geo,language):events.append(('serp',keyword));return {'tasks':[{'result':[{'items':[]}]}]}
 monkeypatch.setattr(services,'call_gemini',gemini);monkeypatch.setattr(services,'call_dataforseo_google_serp',serp);monkeypatch.setattr(services,'get_dataforseo_provider',lambda db:object())
 asyncio.run(services.collect_competitor_serp_for_item(db,item))
 assert events[0][0]=='topic' and all(event[0]=='serp' for event in events[1:])
 assert research.expanded_topic(item,'PL','pl')==TOPIC and 5<=research.word_count(TOPIC)<=9
 queries=db.scalars(select(models.CompetitorQuery).where(models.CompetitorQuery.content_item_id==item.id)).all()
 assert queries and all(q.query!='nowe kasyna' for q in queries)
 assert [q.query for q in queries]==[value for event,value in events if event=='serp']
 assert all(set(q.query.split())<=set(TOPIC.lower().split()) for q in queries)
 assert (item.topic,item.slug,item.generation_context['current_section'])==original
 asyncio.run(research.prepare(db,item,task,site));assert sum(event=='topic' for event,_ in events)==1


def test_invalid_topic_blocks_search_and_retries_with_exact_bounds(db,monkeypatch):
 site,task,item=make(db);calls=[]
 async def gemini(provider,prompt):calls.append(prompt);return response('Nowe Kasyna')
 monkeypatch.setattr(services,'call_gemini',gemini)
 monkeypatch.setattr(services,'get_dataforseo_provider',lambda db:pytest.fail('Search must not start before valid topic'))
 with pytest.raises(ValueError,match='5–9'):
  asyncio.run(services.collect_competitor_serp_for_item(db,item))
 assert len(calls)==3 and 'article_research_topic' not in item.generation_context
 assert not db.scalars(select(models.CompetitorQuery)).all()


def test_manual_queries_survive_topic_preparation(db,monkeypatch):
 site,task,item=make(db);services.replace_competitor_queries(db,item,['nowe kasyna opinie graczy']);db.commit()
 async def gemini(provider,prompt):return response(TOPIC)
 monkeypatch.setattr(services,'call_gemini',gemini)
 asyncio.run(research.prepare(db,item,task,site))
 assert services.ensure_competitor_queries(db,item,'PL','pl')[0].query=='nowe kasyna opinie graczy'
 assert research.expanded_topic(item,'PL','pl')==TOPIC


def test_non_structure_and_long_labels_are_unchanged(db,monkeypatch):
 site,task,item=make(db)
 monkeypatch.setattr(services,'call_gemini',lambda *args:pytest.fail('Unexpected Gemini call'))
 item.topic='Nowe kasyna online z bonusami dla graczy'
 asyncio.run(research.prepare(db,item,task,site));assert 'article_research_topic' not in item.generation_context
 item.topic='Nowe Kasyna';item.section_content_mode='nested';item.generation_context={}
 asyncio.run(research.prepare(db,item,task,site));assert not research.defer_queries(item,'PL','pl')
 assert services.ensure_competitor_queries(db,item,'PL','pl')


def test_reading_queries_does_not_reset_running_topic_stage(db):
 site,task,item=make(db);item.competitor_research_status='preparing_topic';db.commit()
 assert services.ensure_competitor_queries(db,item,'PL','pl')==[]
 assert item.competitor_research_status=='preparing_topic'


def test_expanded_topic_is_used_for_article_and_selected_anchor_in_prompt(db,monkeypatch):
 site,task,item=make(db)
 item.generation_context={**item.generation_context,'article_research_topic':{'label':item.topic,'topic':TOPIC,'geo':'PL','language':'pl'}};db.commit();captured={}
 async def build(**kwargs):
  captured.update(kwargs)
  return {'pages':[{'slug':item.slug,'content':{'blocks':[{'type':'paragraph','data':{'text':'Poradnik kasyna internetowe.'}}]}}]}
 async def images(db,item,site,result,provider):return result
 monkeypatch.setattr(services,'build_ai_content',build);monkeypatch.setattr(services,'generated_content_uses_language',lambda *args:True)
 monkeypatch.setattr(services,'apply_brand_content_buttons',lambda result,*args:result)
 from app import article_images,generation_anchors
 monkeypatch.setattr(article_images,'generate_for_content',images);monkeypatch.setattr(generation_anchors.secrets,'choice',lambda pool:pool[2])
 result=asyncio.run(services._build_task_content(db,item,site=site,provider=None,topic=item.topic,geo='PL',language='pl',prompt_template='Write article'))
 assert captured['topic']==TOPIC and item.topic=='Nowe Kasyna'
 assert 'kasyna internetowe' in captured['prompt_template'] and 'Never insert hyperlinks in headings' in captured['prompt_template']
 assert '<a href="/">kasyna internetowe</a>' in result['pages'][0]['content']['blocks'][0]['data']['text']
