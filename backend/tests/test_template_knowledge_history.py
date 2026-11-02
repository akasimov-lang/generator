from copy import deepcopy
import hashlib
from sqlalchemy import select
from app import models
from app.template_knowledge_library import import_previous_sources,listing,remember_template_sources
from app.template_knowledge import attach_sources
from app.site_templates_api import enqueue
from test_site_templates import db
from test_template_knowledge import setup_template

HTML='<html><title>Saved competitor</title><body><p>'+('Useful original competitor content. '*25)+'</p></body></html>'


def previous(db,user,brand='pelican casino',geo='PL',html=HTML,capture=None):
    template=models.SiteTemplate(created_by_user_id=user.id,brand=brand,geo=geo,language='pl',request_data={},status='failed')
    db.add(template);db.flush()
    source=models.TemplateSource(template_id=template.id,url='',google_html=html,
        capture=capture if capture is not None else {'source':'manual_html','status':'google_ready','revision':3})
    db.add(source);db.flush();return template,source


def test_failed_old_tasks_are_imported_idempotently_and_brand_aliases_match(db):
    user,_,_=setup_template(db)
    old,source=previous(db,user);_,duplicate=previous(db,user,brand='Pelican')
    _,bad=previous(db,user,html='blocked',capture={'source':'manual_html','status':'invalid_html'})
    before=deepcopy(source.capture);digest=hashlib.sha256(source.google_html.encode()).hexdigest()
    result=import_previous_sources(db);db.commit()
    assert result['counts']=={'imported':1,'duplicate':1,'skipped':1,'full':0}
    assert listing(db,'Pelican','PL')['count']==listing(db,'pelican casino','PL')['count']==1
    assert listing(db,'Pelican','CZ')['count']==0
    assert listing(db,'Fontan','PL')['count']==0
    assert import_previous_sources(db)['counts']['imported']==0
    assert source.capture==before and hashlib.sha256(source.google_html.encode()).hexdigest()==digest
    new=models.SiteTemplate(created_by_user_id=user.id,brand='Pelican',geo='PL',language='pl',request_data={})
    db.add(new);db.flush();attach_sources(db,new)
    sources=db.scalars(select(models.TemplateSource).where(models.TemplateSource.template_id==new.id)).all()
    assert len(sources)==1 and sources[0].google_html==HTML
    row=db.scalar(select(models.TemplateKnowledgeExample))
    assert row.created_at==source.created_at and row.brand=='Pelican'


def test_generic_old_html_without_url_is_shared_across_geo_and_never_parsed_without_domain(db):
    user,_,_=setup_template(db)
    old,source=previous(db,user,brand='Общие ключи')
    assert import_previous_sources(db)['counts']['imported']==1;db.commit()
    assert listing(db,'Онлайн казино','CZ')['count']==listing(db,'Общие ключи','DE')['count']==1
    assert not db.scalars(select(models.BackgroundJob)).all()
    row=db.scalar(select(models.TemplateKnowledgeExample))
    assert row.geo=='*' and row.html==HTML
    # The upload in the original task remains an editable source, not an extra copy.
    attach_sources(db,old)
    assert len(db.scalars(select(models.TemplateSource).where(models.TemplateSource.template_id==old.id)).all())==1
    assert 'knowledge_id' not in source.capture


def test_task_enqueue_remembers_upload_without_duplicating_manual_source_or_self_learning(db):
    user,_,_=setup_template(db)
    template,source=previous(db,user,brand='BetOnRed',geo='CZ')
    assert listing(db,'BetOnRed','CZ')['count']==0
    enqueue(db,template,stage='research')
    assert listing(db,'betonred','CZ')['count']==1
    assert len(db.scalars(select(models.TemplateSource)).all())==1
    new=models.SiteTemplate(created_by_user_id=user.id,brand='BetOnRed',geo='CZ',language='cs',request_data={})
    db.add(new);db.flush();attach_sources(db,new)
    assert remember_template_sources(db,new)==[{'status':'skipped'}]
    assert listing(db,'BetOnRed','CZ')['count']==1
    # A later actual upload revision is a new immutable example; the first stays intact.
    source.google_html=HTML.replace('Saved competitor','Updated competitor')
    remember_template_sources(db,template);db.commit()
    assert listing(db,'BetOnRed','CZ')['count']==2


def test_user_edit_of_a_knowledge_snapshot_is_saved_as_new_example(db):
    user,_,_=setup_template(db)
    original,source=previous(db,user,brand='BetOnRed',geo='CZ')
    remember_template_sources(db,original);db.commit()
    task=models.SiteTemplate(created_by_user_id=user.id,brand='BetOnRed',geo='CZ',language='cs',request_data={})
    db.add(task);db.flush();attach_sources(db,task)
    copied=db.scalar(select(models.TemplateSource).where(models.TemplateSource.template_id==task.id))
    copied.capture={**copied.capture,'source':'manual_html'}
    assert remember_template_sources(db,task)==[{'status':'skipped'}]
    copied.google_html=HTML.replace('Saved competitor','User revision')
    assert remember_template_sources(db,task)[0]['status']=='imported'
    attach_sources(db,task);db.commit()
    assert len(db.scalars(select(models.TemplateSource).where(models.TemplateSource.template_id==task.id)).all())==1
    assert listing(db,'BetOnRed','CZ')['count']==2
    assert source.google_html==HTML
