from types import SimpleNamespace
import pytest
from app import auto_reglue
from app.mass_action_scope import matches, MassActionFilter
from app.automatic_history import changes


def test_disabled_project_excluded_from_group_selection():
    site=SimpleNamespace(is_active=True,hidden_from_projects=False,project_status='mass_actions',reglue_participation=False,brand='Brand',cache_geo='PL',site_type='monobrand')
    assert not matches(site,MassActionFilter(brand='Brand',geo='PL'))


def test_disabled_project_cannot_run_personal_automation():
    site=SimpleNamespace(reglue_participation=False,project_status='mass_actions')
    with pytest.raises(ValueError):
        auto_reglue.require_eligible(site,auto_reglue.GlobalConfig(),auto_reglue.ProjectConfig(scope='personal'))


def test_disabled_project_has_no_personal_schedule():
    site=SimpleNamespace(reglue_participation=False,project_status='mass_actions')
    assert not auto_reglue.schedule_eligible(site,auto_reglue.GlobalConfig(),auto_reglue.ProjectConfig(scope='personal',enabled=True,schedule_enabled=True))


def test_history_reports_actual_difference():
    assert changes({'Main':'a.test'},{'Main':'b.test'})==[{'field':'Main','before':'a.test','after':'b.test'}]
    assert changes({'x':1},{'x':1})==[]
