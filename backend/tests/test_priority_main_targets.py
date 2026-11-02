from uuid import uuid4
import pytest
from sqlalchemy import select
from app import models, auto_reglue as auto, auto_pilot as pilot, cross_reglue_batch as batch, mass_reglue_launch as launch, reglue_reserves as stock
from app.domain_transfer_policy import set_ban
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool, reserve, finish


def plan(db, site):
    db.info['prefer_own_domains'] = True
    return batch.build(db, [site], 'test')


def test_20bet_shape_eight_own_newregs_before_stock_and_executes_locally(pool):
    db, source, target, remotes, add = pool
    site = add('20bet-casino-hu.test', free=8, geo='HU', brand='20Bet')
    stock.import_domains(db, 'reserve-drop.test', 'drop', '', 'test')
    preview = plan(db, site); p = preview['plans'][0]
    assert p['new_main'] == 'free-0-20bet-casino-hu.test'
    assert p['local_target'] and p['source_site_id'] == site.id
    assert p['main_target_kind'] == 'newreg' and not p.get('reserve_pool_id')
    assert all(not r.calls for r in remotes.values())
    finish(db, reserve(db, preview))
    assert remotes[site.id].data['settings']['canon'] == p['new_main']
    assert not any(path in ('/site-config/create', '/site-config/delete') for path, _ in remotes[site.id].calls)
    assert db.scalar(select(models.ReglueReserveDomain)).status == 'available'


@pytest.mark.parametrize('block', ['history', 'ban', 'amp'])
def test_blocked_newreg_skipped_then_own_drop_before_stock(pool, block):
    db, source, target, remotes, add = pool
    site = add('own.test', free=2, geo='HU')
    newreg, drop = 'free-0-own.test', 'free-1-own.test'
    site.domain_types = {newreg:'newreg', drop:'drop'}
    if block == 'history': site.main_domain_history = ['www.' + newreg]
    if block == 'ban': set_ban(db, site, newreg, True, 'test')
    if block == 'amp': remotes[site.id].data['settings']['amp'] = newreg
    db.commit(); stock.import_domains(db, 'reserve.test', 'drop', '', 'test')
    p = plan(db, site)['plans'][0]
    assert p['new_main'] == drop and p['local_target'] and not p.get('reserve_pool_id')


def test_installed_reserve_keeps_priority(pool):
    db, source, target, remotes, add = pool
    site = add('own.test', free=2, geo='HU')
    remotes[site.id].data['settings']['reserve'] = 'free-1-own.test'
    p = plan(db, site)['plans'][0]
    assert p['new_main'] == 'free-1-own.test' and p['use_selected_reserve']


def test_stock_after_own_exhausted_then_larger_matching_donor(pool):
    db, source, target, remotes, add = pool
    site = add('recipient.test', geo='HU'); donor = add('donor.test', free=2, geo='HU')
    stock.import_domains(db, 'reserve.test', 'drop', '', 'test')
    assert plan(db, site)['plans'][0]['new_main'] == 'reserve.test'
    row = db.scalar(select(models.ReglueReserveDomain)); row.brand = 'Other'; db.commit()
    p = plan(db, site)['plans'][0]
    assert p['source_site_id'] == donor.id and not p.get('reserve_pool_id')


def test_az_excludes_stock_drops(pool):
    db, source, target, remotes, add = pool
    stock.import_domains(db, 'reserve.test', 'drop', '', 'test')
    p = plan(db, target)['plans'][0]
    assert p['source_site_id'] == source.id and p['new_main'] == 'next.test'


def test_all_own_domains_claimed_before_donors(pool):
    db, source, target, remotes, add = pool
    db.info['prefer_own_domains'] = True
    p = batch.build(db, [source, target], 'test')
    assert len(p['plans']) == 1 and p['plans'][0]['site_id'] == source.id
    assert p['plans'][0]['new_main'] == 'next.test'
    assert any(s['site_id'] == target.id for s in p['skipped'])


def test_old_preview_cannot_launch_after_planner_change(pool):
    db, source, target, remotes, add = pool
    user = {'username':'test', 'allowed_site_ids':None}
    job = pilot.create(db, uuid4(), user)
    launch.execute_step(db, job.id, lambda _:pytest.fail('Preview cannot dispatch'))
    job.payload = {k:v for k,v in job.payload.items() if k != 'planner_version'}; db.commit()
    assert pilot.view(db, job)['plan_outdated']
    with pytest.raises(ValueError, match='Обновите план'):
        pilot.start(db, job.id, user)
    assert all(not r.calls for r in remotes.values())


def test_future_alternate_uses_saved_plan_and_resolves_new_main(pool):
    db, source, target, remotes, add = pool
    before = '<link rel="alternate" hreflang="hu" href="https://{{settings.canon}}/old/" />'
    after = '<link rel="alternate" hreflang="hu" href="https://{{settings.canon}}/new/" />'
    data = pilot.describe(db, {'site_id':target.id, 'old_main':'old.test','new_main':'new.test',
        'alternateMarkup':after,'enableAlternates':True,'alternates_before':{'markup':before,'enabled':True}})
    assert data['alternate'] == after.replace('{{settings.canon}}', 'new.test')
    assert data['alternate_before'] == before.replace('{{settings.canon}}', 'old.test')
    assert data['alternate_markup'] == after


def test_banned_reserve_without_donor_uses_stock_except_az(pool):
    db,source,target,remotes,add=pool
    site=add('austria.test',free=1,geo='AT',brand='Solo')
    remotes[site.id].data['settings']['reserve']='free-0-austria.test'
    set_ban(db,site,'free-0-austria.test',True,'test')
    stock.import_domains(db,'fallback.test','drop','','test')
    preview=plan(db,site);p=preview['plans'][0]
    assert p['new_main']=='fallback.test' and p.get('replace_banned_reserve') and p['reserve_pool_id']
    finish(db,reserve(db,preview))
    assert remotes[site.id].data['settings']['canon']=='fallback.test'


def test_known_webdev_alternate_domain_template_does_not_block_future_plan(pool):
    db,source,target,remotes,add=pool
    site=add('az-brand.test',free=1,geo='AZ');site.cache_language='az';db.commit()
    r=remotes[site.id]
    r.data['head']['alternateMarkup']='<link rel="alternate" href="https://{{settings.alternate.alternateDomain}}/" hreflang="x-default" />'
    r.data['settings']['alternate']={'alternateDomain':'actual-parent.test','currentFakeMain':'/az/','fakeMain':['/az/'],'enableDynamicRoutes':True}
    db.info['auto_pilot_preview']=True
    p=plan(db,site)['plans'][0]
    assert '{{settings.alternate.alternateDomain}}' not in p['alternateMarkup']
    assert p['alternates_before']['markup']==r.data['head']['alternateMarkup']
    assert all(not remote.calls for remote in remotes.values())
