from sqlalchemy import select
from app import models, project_cache as cache, project_inventory_cleanup as cleanup
from test_project_cache_sync import make_session


def test_manual_removal_archives_and_survives_full_cache_sync(monkeypatch):
    monkeypatch.setattr(cache, '_working_project_canons', lambda: set())
    with make_session() as db:
        site=models.Site(name='removed.test',base_url='https://removed.test',publication_endpoint='',external_project_id='removed')
        db.add(site);db.commit();sid=site.id
        cleanup.archive_and_delete(db,site,{'actor':'test','exclude_from_import':True})
        assert db.get(models.Site,sid) is None
        assert db.get(models.AutoReglueConfig,'removed-project:'+sid).value['tables']['sites'][0]['name']=='removed.test'
        def project(name):return {'id':name,'name':name,'settings':{'canon':name,'domains':[name]},'data':{'pages':[]}}
        result=cache.sync_project_cache(db,[project('REMOVED.TEST.'),project('keep.test')])
        assert result['created_count']==1
        assert [s.name for s in db.scalars(select(models.Site))]==['keep.test']
        # A newly confirmed remote project may recover from ordinary inventory cleanup.
        db.add(models.AutoReglueConfig(key='removed-project:old',value={'project':'recovered.test','evidence':{'absent_from_full_cache':True}}));db.commit()
        assert cache.sync_project_cache(db,[project('recovered.test')])['created_count']==1


def test_server_inventory_does_not_fetch_or_reimport_excluded_names(monkeypatch):
    with make_session() as db:
        db.add(models.AutoReglueConfig(key='removed-project:test',value={'project':'removed.test','evidence':{'exclude_from_import':True}}));db.commit()
        monkeypatch.setattr(cache,'fetch_project_cache',lambda:[])
        monkeypatch.setattr(cache,'fetch_server_project_inventories',lambda ids:({'deer':{'removed.test'}},{}))
        monkeypatch.setattr(cache,'_fetch_project_from_server_id',lambda *a:(_ for _ in ()).throw(AssertionError('Excluded project must not be fetched')))
        cache.reconcile_server_project_inventory(db)
        assert list(db.scalars(select(models.Site)))==[]
