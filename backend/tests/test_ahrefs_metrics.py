import base64
import csv
import io
from uuid import uuid4
import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from app import models
from app.db import Base
from app.ahrefs_metrics import parse_export,read,key,import_exports


def csv_data(rows,headers=None):
    output=io.StringIO()
    writer=csv.writer(output,delimiter='\t')
    writer.writerow(headers or ['Target','Mode','Protocol','Domain Rating','Backlinks / All','Ref. domains / All'])
    writer.writerows(rows)
    return output.getvalue().encode('utf-16')


def export(data,time='12-30-08'):
    return {'filename':f'batch_analysis_2026-11-25_{time}.csv','data_base64':base64.b64encode(data).decode()}


@pytest.fixture
def env():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        job=models.BackgroundJob(id=str(uuid4()),kind='maintenance_report',status='running',payload={'task_type':'ahrefs_batch_audit'},result={'entries':[{'site_id':'one','project':'one.test','domains':['www.one.test','child.one.test'],'status':'waiting'}]})
        db.add(job);db.commit()
        yield db,job


def test_utf16_export_uses_all_columns_preserves_zero_and_missing_values():
    rows=parse_export(csv_data([['www.one.test/','subdomains','both','0','0',''],['child.one.test/','subdomains','both','4.2','','12']]),export(b'')['filename'])
    assert rows[0]['dr']==rows[0]['backlinks_all']==0
    assert rows[0]['referring_domains_all'] is None
    assert rows[1]['dr']==4.2 and rows[1]['backlinks_all'] is None
    assert rows[0]['domain']=='www.one.test' and rows[1]['domain']=='child.one.test'
    assert rows[0]['target_mode']=='subdomains' and rows[0]['protocol']=='both'
    assert rows[0]['exported_at']=='2026-11-25T12:30:08+03:00'


def test_ambiguous_live_columns_cannot_replace_all_metrics():
    with pytest.raises(ValueError,match='точных столбцов'):
        parse_export(csv_data([],['Target','Mode','Protocol','Domain Rating','Backlinks / Live','Ref. domains / Live']),export(b'')['filename'])


def test_out_of_range_dr_is_rejected():
    with pytest.raises(ValueError,match='dr'):
        parse_export(csv_data([['www.one.test/','subdomains','both','101','1','1']]),export(b'')['filename'])


def test_fractional_backlink_count_is_rejected():
    with pytest.raises(ValueError,match='backlinks_all'):
        parse_export(csv_data([['www.one.test/','subdomains','both','20','1.5','1']]),export(b'')['filename'])


def test_wrong_target_mode_is_not_imported_as_domain_metrics():
    with pytest.raises(ValueError,match='область'):
        parse_export(csv_data([['www.one.test/','prefix','both','20','1','1']]),export(b'')['filename'])


def test_dry_run_does_not_write_metrics(env):
    db,job=env
    result=import_exports(db,job.id,[export(csv_data([['www.one.test/','subdomains','both','20','1','1']]))])
    assert result['updated']==1
    assert read(db,['www.one.test'])=={}
    assert db.get(models.BackgroundJob,job.id).status=='running'


def test_newer_export_wins_and_reimport_is_idempotent(env):
    db,job=env
    older=export(csv_data([['www.one.test/','subdomains','both','20','1','1']]))
    newer=export(csv_data([['www.one.test/','subdomains','both','21','9','3'],['child.one.test/','subdomains','both','0','','']]),'12-32-09')
    result=import_exports(db,job.id,[newer,older],apply=True)
    assert result['unique_domains']==2 and result['duplicates']==1
    assert result['report_status']=='completed' and result['projects_completed']==1
    values=read(db,['www.one.test','child.one.test'])
    assert values['www.one.test']['dr']==21
    assert values['child.one.test']['backlinks_all'] is None
    assert import_exports(db,job.id,[older,newer],apply=True)['updated']==0
    assert read(db,['www.one.test'])=={'www.one.test':values['www.one.test']}


def test_domain_outside_report_stops_entire_import(env):
    db,job=env
    with pytest.raises(ValueError,match='составе отчёта'):
        import_exports(db,job.id,[export(csv_data([['www.one.test/','subdomains','both','20','1','1'],['foreign.test/','subdomains','both','20','1','1']]))],apply=True)
    assert read(db,['www.one.test'])=={}


def test_metrics_do_not_leak_between_www_root_or_child_domains(env):
    db,job=env
    import_exports(db,job.id,[export(csv_data([['www.one.test/','subdomains','both','20','1','1']]))],apply=True)
    assert read(db,['one.test','child.one.test'])=={}
    assert read(db,['www.one.test'])['www.one.test']['dr']==20
    assert len(key('x'*240+'.test'))<=80


def test_conflicting_values_with_same_export_time_are_rejected(env):
    db,job=env
    with pytest.raises(ValueError,match='Противоречивые'):
        import_exports(db,job.id,[export(csv_data([['www.one.test/','subdomains','both','20','1','1']])),export(csv_data([['www.one.test/','subdomains','both','21','1','1']]))],apply=True)
