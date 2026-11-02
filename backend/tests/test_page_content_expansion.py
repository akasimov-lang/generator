from copy import deepcopy
import pytest
from app.page_content_expansion import apply_additions, validate_additions, section_targets


@pytest.fixture
def content():
    return {'version': '2.28', 'meta': {'keep': True}, 'blocks': [
        {'id': 'h1', 'type': 'header', 'data': {'text': 'Choosing games', 'level': 1}},
        {'id': 'old', 'type': 'paragraph', 'data': {'text': 'Original facts about this page must stay exactly as they were.'}},
        {'id': 'asset', 'type': 'image', 'data': {'file': {'url': '/keep.png'}}},
        {'id': 'h2', 'type': 'header', 'data': {'text': 'Managing a session', 'level': 2}},
        {'id': 'link', 'type': 'paragraph', 'data': {'text': 'Read <a href="/terms/">the complete terms</a> before starting.'}},
    ]}


def paragraph(text):
    return {'type': 'paragraph', 'data': {'text': text}}


@pytest.mark.parametrize('count', [1, 2, 3])
def test_exact_total_is_inserted_into_chosen_sections_without_changing_original(content, count):
    original = deepcopy(content)
    sections = [{'id': 0, 'blocks': [paragraph(f'New angle {i}: choose a short session first and compare which controls suit your preferred rhythm.') for i in range(count)]}]
    result = apply_additions(content, validate_additions(content, {'sections': sections}, count))
    old_ids = {block['id'] for block in content['blocks']}
    assert [block for block in result['blocks'] if block['id'] in old_ids] == original['blocks']
    assert len(result['blocks']) == len(original['blocks']) + count
    assert result['blocks'][3]['type'] == 'paragraph'
    assert result['blocks'][3 + count]['id'] == 'h2'
    assert content == original and result['meta'] == original['meta']


def test_lists_and_tables_remain_native_editable_blocks(content):
    output = {'sections': [{'id': 3, 'blocks': [
        paragraph('Plan the session around a comfortable stopping point instead of extending it simply to try another option.'),
        {'type': 'list', 'data': {'style': 'unordered', 'items': ['Choose an achievable stopping point before opening the first game.', 'Leave time to review the session without rushing the next choice.']}},
        {'type': 'table', 'data': {'withHeadings': True, 'content': [['Scenario', 'Approach'], ['Short break', 'Focus on familiar controls and a clearly defined endpoint.']]}},
    ]}]}
    result = apply_additions(content, validate_additions(content, output, 1))
    assert [block['type'] for block in result['blocks'][-3:]] == ['paragraph', 'list', 'table']
    assert len({block['id'] for block in result['blocks']}) == len(result['blocks'])


@pytest.mark.parametrize('replacement', [
    'Original facts about this page must stay exactly as they were.',
    '<img src=x onerror=alert(1)> This is a long enough paragraph that must still be rejected.',
    '<script>alert(1)</script> This paragraph must not be accepted despite its sufficient length.',
])
def test_repeated_and_unsafe_additions_are_rejected(content, replacement):
    with pytest.raises(ValueError):
        validate_additions(content, {'sections': [{'id': 0, 'blocks': [paragraph(replacement)]}]}, 1)


@pytest.mark.parametrize('output,count', [
    ({'sections': [{'id': 2, 'blocks': [paragraph('This expansion should be rejected because the target is an image instead of a heading.')]}]}, 1),
    ({'sections': [{'id': 0, 'blocks': [paragraph('This is a valid new sentence developing the heading but it is only one paragraph.')]}]}, 2),
    ({'sections': [{'id': 0, 'blocks': [{'type': 'raw', 'data': {'html': '<b>Raw HTML is not allowed here.</b>'}}]}]}, 1),
    ({'sections': [{'id': 0, 'blocks': [paragraph('This is a new practical idea about choosing a useful stopping point for a session.')]}, {'id': 0, 'blocks': [paragraph('This second new practical idea should still be rejected for repeating the heading identifier.')]}]}, 2),
])
def test_invalid_targets_counts_and_blocks_do_not_mutate_input(content, output, count):
    original = deepcopy(content)
    with pytest.raises(ValueError): validate_additions(content, output, count)
    assert content == original


def test_duplicates_across_new_sections_are_rejected(content):
    value = paragraph('The same practical scenario appears twice here even though the headings are different, which adds no value.')
    with pytest.raises(ValueError, match='повторяет'):
        validate_additions(content, {'sections': [{'id': 0, 'blocks': [value]}, {'id': 3, 'blocks': [value]}]}, 2)


def test_target_ids_refer_to_original_header_indices(content):
    assert section_targets(content) == [{'id': 0, 'text': 'Choosing games'}, {'id': 3, 'text': 'Managing a session'}]
