from copy import deepcopy
from types import SimpleNamespace
import re
from app.content_toc import normalize_toc_blocks
from app.services import build_blocks_from_ai_text, build_project_page_payload, normalize_editor_inline_markup


def source():
    return [{'id':'one','type':'header','data':{'text':'Płatności &amp; bonusy','level':2}},
            {'id':'toc','type':'toc','data':[{'heading':'Stale heading','checked':True}]},
            {'id':'two','type':'header','data':{'text':'Płatności &amp; bonusy','level':2}},
            {'type':'paragraph','data':{'text':'Unchanged body.'}}]


def test_toc_links_have_unique_real_targets_and_labels_and_do_not_mutate_source():
    blocks=source(); before=deepcopy(blocks); result=normalize_toc_blocks(blocks)
    assert blocks==before
    assert result[1]['type']=='list'
    targets=[re.search('id="([^"]+)"', result[i]['data']['text'])[1] for i in [0,2]]
    assert len(set(targets))==2
    assert [re.search('href="#([^"]+)"',x)[1] for x in result[1]['data']['items']]==targets
    assert 'Stale heading' not in str(result)
    assert normalize_toc_blocks(result)==result
    assert result[-1]==blocks[-1]


def test_generation_inserts_linked_contents():
    blocks=build_blocks_from_ai_text('## First section\nBody one.\n## Second section\nBody two.', 'Guide',None,True,False)
    toc=next(b for b in blocks if b.get('pagepilot_toc'))
    assert all('href="#pp-section-' in item for item in toc['data']['items'])


def test_publication_repairs_legacy_contents_before_transport():
    item=SimpleNamespace(topic='Guide',slug='/guide/',section_source_slug=None,generated_json={'pages':[{'content':{'blocks':source()}}]})
    site=SimpleNamespace(name='test.example')
    result=build_project_page_payload(item,site,'token')
    assert result['page']['content']['blocks'][1]['data']['items'][0].startswith('<a href="#')
    assert result['page']['content']['blocks'][0]['data']['text'].startswith('<span id=')


def test_duplicate_copied_heading_targets_are_repaired():
    blocks=normalize_toc_blocks(source())
    blocks.insert(3,deepcopy(blocks[0]))
    result=normalize_toc_blocks(blocks)
    ids=re.findall('id="([^"]+)"',str(result))
    assert len(ids)==len(set(ids))
    assert normalize_toc_blocks(result)==result


def test_without_contents_leaves_heading_markup_unchanged():
    blocks=[source()[0]]
    assert normalize_toc_blocks(blocks)==blocks
