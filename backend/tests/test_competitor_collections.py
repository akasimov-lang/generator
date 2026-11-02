from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select

from app import models
from app.template_knowledge_library import competitor_identity, listing
from test_site_templates import db
from test_template_knowledge import setup_template
from test_template_knowledge_library import client

HTML = '<html><head><title>Competitor casino — bonus guide</title><link rel="canonical" href="https://competitor.test/"></head><body><p>' + 'Useful original competitor information. ' * 30 + '</p></body></html>'


def draft(db,user,html=HTML,revision=2):
    row=models.TemplateSourceDraft(user_id=user.id,url='',google_html=html,
        capture={'source':'manual_html','status':'google_ready','revision':revision})
    db.add(row);db.commit();return row


def test_save_html_creates_collection_and_knowledge_without_starting_generation(db):
    user,provider,_=setup_template(db);api=client(db,user)
    row=draft(db,user)
    result=api.post('/site-templates/knowledge/save-drafts',json={'brand':'Pelican','geo':'PL','language':'pl',
        'source_drafts':[{'id':row.id,'revision':2}]})
    assert result.status_code==201,result.text
    assert result.json()['saved']==1
    saved=result.json()['collection']
    assert saved['status']=='sources_ready' and saved['html'] is None and not saved['has_html']
    assert not db.get(models.TemplateSourceDraft,row.id)
    assert not db.scalars(select(models.BackgroundJob)).all()
    assert listing(db,'Pelican','PL')['count']==1 and listing(db,'Pelican','CZ')['count']==0
    source=db.scalar(select(models.TemplateSource).where(models.TemplateSource.template_id==saved['id']))
    assert source.google_html==HTML and source.url=='https://competitor.test/'
    summary=next(item for item in api.get('/site-templates').json() if item['id']==saved['id'])
    assert summary['competitors']==[{'domain':'competitor.test','title':'Competitor casino — bonus guide','url':'https://competitor.test/'}]
    assert not summary['has_html']
    # A separate, explicit action is still required to start the template pipeline.
    assert api.post(f"/site-templates/{saved['id']}/generate-content").status_code==202
    assert db.scalar(select(models.BackgroundJob)).kind=='site_template'


def test_revisions_and_ownership_are_checked_before_any_library_save(db):
    user,_,_=setup_template(db);api=client(db,user)
    first=draft(db,user);second=draft(db,user,HTML.replace('guide','details'))
    result=api.post('/site-templates/knowledge/save-drafts',json={'brand':'BetOnRed','geo':'CZ','language':'cs',
        'source_drafts':[{'id':first.id,'revision':2},{'id':second.id,'revision':1}]})
    assert result.status_code==409
    assert db.get(models.TemplateSourceDraft,first.id) and db.get(models.TemplateSourceDraft,second.id)
    assert not db.scalar(select(models.TemplateKnowledgeExample))
    other=models.User(username='other',password_hash='',is_active=True);db.add(other);db.commit()
    foreign=draft(db,other)
    assert api.post('/site-templates/knowledge/save-drafts',json={'brand':'Pelican','geo':'PL',
        'source_drafts':[{'id':foreign.id,'revision':2}]}).status_code==404


def test_generic_html_without_domain_is_preserved_without_starting_parser(db):
    user,_,_=setup_template(db);api=client(db,user)
    row=draft(db,user,HTML.replace('<link rel="canonical" href="https://competitor.test/">',''))
    result=api.post('/site-templates/knowledge/save-drafts',json={'brand':'Общие ключи','geo':'PL','language':'pl',
        'source_drafts':[{'id':row.id,'revision':2}]})
    assert result.status_code==201,result.text
    assert listing(db,'Общие ключи','CZ')['count']==1
    assert db.scalar(select(models.TemplateKnowledgeExample)).structure['status']=='needs_url'
    assert not db.scalars(select(models.BackgroundJob)).all()


def test_list_separates_actual_generated_html_and_reports_saved_source_title(db):
    user,provider,_=setup_template(db);api=client(db,user)
    row=models.SiteTemplate(created_by_user_id=user.id,brand='Ready',geo='DE',language='de',status='ready',
        request_data={},html='<html>Generated template</html>')
    db.add(row);db.commit()
    response=api.get('/site-templates').json()
    assert next(item for item in response if item['id']==row.id)['has_html']
    assert competitor_identity(HTML)['domain']=='competitor.test'
    assert competitor_identity('<title>Only a title</title>', 'javascript:alert(1)')=={'title':'Only a title','url':'','domain':''}
