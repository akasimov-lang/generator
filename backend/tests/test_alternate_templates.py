from app.alternate_templates import template_catalog


def test_import_retains_all_projects_and_ambiguities():
    catalog=template_catalog()
    assert len(catalog)==19
    assert sum('after' in p['variants'] for p in catalog)==7
    row=next(p for p in catalog if p['project']=='theworkathomewomanshop.com')
    assert row['notes']==['poland-verdecasino.com']
    assert next(p for p in catalog if p['project']=='janzywaxco.com')['variants'].keys()=={'before'}

