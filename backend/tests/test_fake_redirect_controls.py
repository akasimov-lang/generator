import pytest
from app.fake_redirect_controls import configure_old_redirects


def test_toggle_preserves_every_other_alternate_setting():
    alternate = {'fakeMain': ['/old/', '/now'], 'currentFakeMain': '/now', 'enableDynamicRoutes': True, 'custom': {'keep': True}}
    result = configure_old_redirects({'settings': {'alternate': alternate}}, True)
    assert result == {**alternate, 'redirectFakeMainsToCurrent': True}
    assert 'redirectFakeMainsToCurrent' not in alternate


def test_can_disable_without_current_fake_page():
    assert configure_old_redirects({'settings': {'alternate': {}}}, False) == {'redirectFakeMainsToCurrent': False}


def test_cannot_enable_without_current_fake_page():
    with pytest.raises(ValueError, match='действующую'):
        configure_old_redirects({'settings': {'alternate': {'fakeMain': ['/old/']}}}, True)


def test_missing_remote_settings_are_not_overwritten():
    with pytest.raises(ValueError, match='Не получены'):
        configure_old_redirects({}, False)
