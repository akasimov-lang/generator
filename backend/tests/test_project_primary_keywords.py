import pytest
from app.project_primary_keywords import additions
from app.generation_anchors import keyword_instruction, save_settings
from test_generation_modes import db, make_site

@pytest.mark.parametrize('geo,language,expected',[
 ('pl-PL','pl_PL',['online casino','casino pl','najlepsze kasyna']),
 ('da_DK','dk_DK',['online casino','casino dk','bedste casinoer']),
 ('se-SV','se_SV',['online casino','casino se','bästa casinon']),
 ('cs_CZ','cz-CZ',['online casino','casino cz','nejlepší kasina']),
 ('bg','nl',['online casino','casino bg','beste casino’s']),
 ('en_AU','au',['online casino','casino au','best casinos']),
])
def test_short_geo_and_project_language(geo,language,expected):
 assert additions(geo,language)==expected


def test_all_saved_keys_are_generation_context(db):
 site=make_site(db);save_settings(db,site,['online casino','casino dk','bedste casinoer'])
 prompt=keyword_instruction(db,site)
 assert 'online casino' in prompt and 'casino dk' in prompt and 'bedste casinoer' in prompt
 assert 'Do not force unrelated keywords' in prompt
