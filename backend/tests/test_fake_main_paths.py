import pytest
from app.fake_main import normalize_fake_path, create_fake_settings, select_fake_settings, delete_fake_settings, fake_paths, fake_canonical_markup, retarget_fake_head

@pytest.mark.parametrize('value,expected',[('events','/events'),('/events','/events'),('/events/','/events/'),(' /index.php ','/index.php'),('/folder/index.html','/folder/index.html')])
def test_preserves_requested_path_format(value,expected):
    assert normalize_fake_path(value)==expected

@pytest.mark.parametrize('value',['/','../page','/page/../other','/api/path','/index.php?x=1','https://host/path','/page#fragment'])
def test_unsafe_paths_remain_rejected(value):
    with pytest.raises(ValueError):normalize_fake_path(value)

def test_slashless_create_select_delete_and_canonical():
    project={'settings':{'alternate':{'fakeMain':['/old/'],'currentFakeMain':'/old/'}},'data':{'pages':[]}}
    settings=create_fake_settings(project,'/index.php',activate=True)
    assert settings['currentFakeMain']=='/index.php'
    assert fake_paths(settings)==['/old/','/index.php']
    project['settings']['alternate']=settings
    assert select_fake_settings(project,'/old/')['currentFakeMain']=='/old/'
    assert delete_fake_settings(project,'/old/')['fakeMain']==['/index.php']
    assert fake_canonical_markup('/index.php').endswith('/index.php" />')

def test_regular_page_collision_ignores_trailing_slash():
    with pytest.raises(ValueError,match='обычная страница'):
        create_fake_settings({'data':{'pages':[{'slug':'/events/'}]}},'/events')

def test_retargets_existing_php_fake_page_without_forcing_slash():
    state={'canon':'example.com','alternateMarkup':'<link rel="alternate" href="https://example.com/index.php" />'}
    assert retarget_fake_head(state,'/index.php','/events')['alternateMarkup']=='<link rel="alternate" href="https://example.com/events" />'
