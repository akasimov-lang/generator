import base64
from io import BytesIO
from types import SimpleNamespace
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import models
from app.api import router
from app.db import get_db
from app.security import require_auth
from app.project_table_export import workbook, export_table, ProjectTableExport, NS
from test_generation_modes import db, make_site


def parse(data):
    with ZipFile(BytesIO(data)) as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            ET.fromstring(archive.read(name))
        return ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))


def test_workbook_preserves_text_numbers_and_has_no_formulas():
    site = SimpleNamespace(name='=HYPERLINK("bad")', brand='Żółć & <brand>', homepage_title='Text\x00 😃',
        cache_canon='main.test', base_url='https://other.test', cache_geo='PL', cache_language='pl',
        project_status='mass_actions', domains_count=8, network_domain_counts={'drop':0,'newreg':6,'subdomains':2},
        fibery_name='_x0041_')
    sheet=parse(workbook([site]))
    cells={c.attrib['r']:c for c in sheet.findall('.//{'+NS+'}c')}
    assert cells['B2'].attrib['t']=='inlineStr'
    assert cells['B2'].find('.//{'+NS+'}t').text==site.name
    assert cells['C2'].find('.//{'+NS+'}t').text==site.brand
    assert cells['J2'].find('{'+NS+'}v').text=='0'
    assert not sheet.findall('.//{'+NS+'}f')
    assert sheet.find('{'+NS+'}autoFilter').attrib['ref']=='A1:M2'
    assert sheet.find('.//{'+NS+'}pane').attrib['state']=='frozen'


def test_endpoint_exports_all_ids_in_requested_order_and_checks_access(db):
    first=make_site(db); first.name='first.test'
    second=models.Site(name='second.test',base_url='https://second.test',publication_endpoint='/publish',project_status='mass_actions')
    db.add(second);db.commit()
    user={'id':'user','allowed_site_ids':None}
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[require_auth]=lambda:user
    with TestClient(app) as client:
        response=client.post('/sites/export-table',json={'site_ids':[second.id,first.id,second.id]})
        assert response.status_code==200,response.text
        result=response.json();assert result['count']==2 and result['filename'].endswith('.xlsx')
        sheet=parse(base64.b64decode(result['base64']))
        names=[c.find('.//{'+NS+'}t').text for c in sheet.findall('.//{'+NS+'}c') if c.attrib['r'] in ('B2','B3')]
        assert names==['second.test','first.test']
        assert client.post('/sites/export-table',json={'site_ids':[]}).status_code==422
        user['allowed_site_ids']=[first.id]
        assert client.post('/sites/export-table',json={'site_ids':[second.id]}).status_code==404
        assert client.post('/sites/export-table',json={'site_ids':[first.id]}).status_code==200
        user['allowed_site_ids']=None;second.hidden_from_projects=True;db.commit()
        assert client.post('/sites/export-table',json={'site_ids':[second.id]}).status_code==404
        assert client.post('/sites/export-table',json={'site_ids':['missing']}).status_code==404
