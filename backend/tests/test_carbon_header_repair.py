from copy import deepcopy
from contextlib import nullcontext
from types import SimpleNamespace
from urllib.parse import unquote
import pytest
from app import models,carbon_header_repair as repair
from test_project_network import env


def project():
    return {'settings':{'canon':'carboncraftworks.com'},'styles':'body{color:white}',
            'data':{'menu':{'header':[{'slug':'/games/','title':'Hry'}]},'pages':[{'id':1,'slug':'/'},{'id':2,'slug':'/games/'}]},
            'shortcodes':[{'name':'header.hbs','data':'<header><a href="#uvod"><div class="logo"></div></a><div class="header-actions"><button data-split="reg">Registrovat</button></div></header>'}]}


def test_header_preserves_tracking_and_connects_saved_menu_without_changing_pages():
    original=project();snapshot=deepcopy(original)
    result=repair.proposed(original)
    assert original==snapshot
    assert '<button data-split="reg">Registrovat</button>' in result['header']
    assert '{{#each headerMenu}}' in result['header'] and 'href="{{this.slug}}"' in result['header']
    assert 'class="cc-brand" href="/"' in result['header']


def test_unpublished_menu_destination_blocks_repair():
    original=project();original['data']['menu']['header'].append({'slug':'/missing/','title':'Missing'})
    with pytest.raises(ValueError,match='опубликованные страницы'):repair.proposed(original)


def test_native_write_is_confirmed_and_idempotent(env,monkeypatch):
    db,site,_=env;monkeypatch.setattr(repair,'SITE',site.id)
    current=project();before=deepcopy(current);calls=[]
    class Remote:
        client=SimpleNamespace(headers={})
        def project(self):return deepcopy(current)
        def request(self,method,endpoint,payload):
            calls.append(endpoint)
            if endpoint=='/projects/update-style':current['styles']=payload['contents']
            elif endpoint=='/projects/shortcode':current['shortcodes'][0]['data']=unquote(payload['contents'])
            else:pytest.fail('Unexpected write')
            return 201,{}
    monkeypatch.setattr(repair,'Remote',lambda *args:nullcontext(Remote()))
    repair.apply(db);repair.apply(db)
    assert len(calls)==2 and current['data']==before['data'] and current['settings']==before['settings']
    ledger=db.get(models.AutoReglueConfig,repair.KEY)
    assert ledger.value['before']==repair.fields(before)
    assert all(r['status']=='confirmed' for r in ledger.value['receipts'])
