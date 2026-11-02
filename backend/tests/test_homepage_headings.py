from copy import deepcopy
import pytest
from app.homepage_headings import extract, from_html
from app.reglue_title_h1 import page_metadata


def project(blocks=(), shortcodes=(), banners=(), layout='{{{renderedBlocks}}}'):
    return {'settings': {'brand': 'Casino'}, 'layout': layout,
            'shortcodes': [{'name': name + '.hbs', 'data': data} for name, data in shortcodes],
            'data': {'pages': [{'slug': '', 'title': 'Homepage title', 'banners': list(banners), 'content': {'blocks': list(blocks)}}]}}


def test_only_used_shortcode_and_nested_partials_not_all_definitions():
    p = project([{'type': 'shortcode', 'data': {'shortcode': 'bannerIndex'}}], [
        ('unused', '<h1>Old unused heading</h1>'),
        ('bannerIndex', '{{> hero}}'),
        ('hero', '<h1>Online casino 2026: bedste <span>spillesider</span>, bonusser og udbetalinger</h1>'),
    ])
    before = deepcopy(p)
    m = page_metadata(p)
    assert m['h1'] == 'Online casino 2026: bedste spillesider, bonusser og udbetalinger'
    assert m['h1_source'] == 'shortcode:bannerIndex' and m['h1_status'] == 'found'
    assert not m['editable_h1'] and p == before


def test_banners_layout_and_editorjs_headings_have_sources_and_multiple_count():
    p = project([{'type': 'header', 'data': {'text': 'Article H1', 'level': 1}}],
                [('banner', '<h1>Banner H1</h1>'), ('header', '<h1>{{settings.brand}} online</h1>')],
                ['banner'], '{{> header}}{{{renderedBlocks}}}')
    m = page_metadata(p)
    assert [h['text'] for h in m['headings']] == ['Casino online', 'Banner H1', 'Article H1']
    assert not m['editable_h1']


@pytest.mark.parametrize('key', ['html', 'code', 'text'])
def test_raw_markup_and_entities(key):
    p = project([{'type': 'raw', 'data': {key: '<H1 class="hero">Casino &amp; casino games<br/>online</H1>'}}])
    m = page_metadata(p)
    assert m['h1'] == 'Casino & casino games online' and m['editable_h1']


def test_comment_script_template_and_attribute_h1_are_not_headings():
    assert from_html('<!-- <h1>old</h1> --><script>"<h1>js</h1>"</script>'
                     '<style>/* <h1>css</h1> */</style><template><h1>unused</h1></template>'
                     '<p title="<h1>attribute</h1>">text</p><h1>Real <b>heading</b></h1>') == ['Real heading']


def test_missing_h1_is_not_synthesized_from_title_or_h2():
    p = project([{'type': 'header', 'data': {'level': 2, 'text': 'Secondary'}},
                 {'type': 'code', 'data': {'code': '<pre>&lt;h1&gt;Example code&lt;/h1&gt;</pre>'}}],
                layout='{{!-- <h1>Commented template</h1> --}}{{{renderedBlocks}}}')
    m = page_metadata(p)
    assert m['h1'] == '' and m['h1_status'] == 'not_found' and not m['editable_h1']


def test_unknown_expression_is_unresolved_and_cyclic_partial_terminates():
    p = project(shortcodes=[('a', '{{> b}}'), ('b', '{{> a}}<h1>{{customHelper page.title}}</h1>')], layout='{{> a}}')
    assert extract(p)['h1_status'] == 'unresolved'


def test_title_variable_is_used_only_inside_actual_h1_and_escaped():
    p = project(layout='<h1>{{page.title}}</h1>')
    p['data']['pages'][0]['title'] = 'Casino <online> & bonus'
    assert extract(p)['h1'] == 'Casino <online> & bonus'
    p['layout'] = '<p>{{page.title}}</p>'
    assert not extract(p)['h1']
