import json
from pathlib import Path
import pytest
from app.showcase_management import inspect, table_rows, remember
from app import models
from test_project_pages import setup

FIXTURES=json.loads((Path(__file__).parent/'fixtures/showcase/connected_sources.json').read_text())

@pytest.mark.parametrize('name,count,first',[
 ('onlinecasino-czech.com',10,'Forbes Casino'),('maleextrasexpill.com',4,'Betano Casino'),
 ('lamcoadvisory.com',3,'Betano Casino online CZ'),('palinforamerica.com',8,'Tipsport Vegas'),
 ('play-game-win-money.com',10,'Tipsport Vegas'),('junckerassociates.com',5,'Tipsport Vegas'),
 ('top-polskie-kasyno.pl',5,"Hit'n'spin"),('casino-online-polska.com',10,'Lemon Casino')])
def test_connected_production_formats(name,count,first):
 p=next(p for p in FIXTURES if p['case']==name);before=json.dumps(p,sort_keys=True)
 management,rows=inspect(p)
 assert management['complete'] and len(rows)==count and rows[0]['brand']==first
 assert all(not r['editable'] and r['fields'] for r in rows)
 assert not {'star','Hodnocení','Licence'}.intersection(r['brand'] for r in rows)
 assert json.dumps(p,sort_keys=True)==before


def test_separate_bonuses_are_not_silently_combined():
 p=next(p for p in FIXTURES if p['case']=='play-game-win-money.com')
 row=inspect(p)[1][0];fields={f['key']:f['value'] for f in row['fields']}
 assert fields['bonus']=='100% do 50 000 Kč'
 assert fields['Bonus bez vkladu']=='500 Kč zdarma'


def test_nested_banner_and_layout_sources_exclude_unused_templates():
 card='<div class="casino-card"><h3>Example Casino</h3><div class="bonus-value">100 EUR</div></div>'
 p={'layout':'{{> wrapper}}','data':{'pages':[{'slug':'/','banners':['banner'],'content':{'blocks':[]}}]},'shortcodes':[
 {'name':'wrapper.hbs','data':'{{> banner}}'}, {'name':'banner.hbs','data':card},{'name':'unused.hbs','data':card.replace('Example','Unused')}]}
 m,rows=inspect(p)
 assert [r['brand'] for r in rows]==['Example Casino']
 assert m['sources'][0]['storage']=='banner'


def test_missing_template_is_incomplete_not_empty_confirmed():
 m,rows=inspect({'layout':'{{> missing}}','data':{'pages':[{'slug':'/','content':{'blocks':[]}}]}})
 assert not m['complete'] and not rows and 'missing' in m['notes'][-1]


def test_non_bonus_table_is_not_a_showcase():
 assert table_rows([['Casino','License'],['Example','Country']], 'table')==[]


def test_malformed_short_table_does_not_crash():
 assert table_rows([['Casino','Bonus','Min deposit'],['Example']], 'table')==[]


def test_external_widget_is_marked_unmanaged():
 p={'data':{'pages':[{'slug':'/','content':{'blocks':[{'type':'raw','data':{'html':'<div class="showcase"><iframe src="https://example.com/widget"></iframe></div>'}}]}}]}}
 m,rows=inspect(p)
 assert not rows and m['sources'][0]['kind']=='external' and not m['sources'][0]['inline_edit']


def test_management_notes_are_persisted_idempotently_separately_from_edits(setup):
 client,db,site,state=setup
 management={'complete':True,'version':1,'sources':[],'notes':['Read actual source']}
 key=remember(db,site,{'username':'tester'},management)
 assert remember(db,site,{'username':'tester'},management)==key
 receipt=db.get(models.ProjectPageEdit,key)
 assert receipt.page_key=='showcase:management' and receipt.status=='confirmed'
 assert receipt.after_page['management']==management
 assert remember(db,site,{'username':'tester'},{'complete':False}) is None


def test_boolean_class_attribute_does_not_break_showcase_tree():
    from app.showcase_management import Tree, html_rows
    markup='<div class><article class="casino-card"><h3>Example Casino</h3><span class="bonus-value">100 EUR</span><img class src="/logo.png" alt="Example Casino"></article></div>'
    tree=Tree(markup)
    assert next(tree.root.walk()).classes==set()
    assert html_rows(markup,'test')[0]['brand']=='Example Casino'
