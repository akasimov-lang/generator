from copy import deepcopy
from app.showcase_brands import showcase_brands
from test_project_pages import setup


def project(blocks,shortcodes=(),casinos=None):
 return {'data':{'pages':[{'slug':'/','content':{'blocks':blocks}}],'casinos':casinos},'shortcodes':list(shortcodes),'layout':'{{> header}} {{> footer}}'}
def shortcode(name):return {'type':'shortcode','data':{'shortcode':name}}
def definition(name,html):return {'name':name+'.hbs','data':html}


def test_used_hardcoded_showcases_only_and_unique_names_ignore_icons_and_article_mentions():
 p=project([shortcode('casinos'),{'type':'paragraph','data':{'text':'OtherCasino is mentioned here.'}}],[
  definition('casinos','<div class="casino"><img alt="NV Casino logo"><img alt="Bonus icon"><img alt="Visa"></div><div class="casino"><img alt="nv casino"></div><div class="casino"><img alt="Ritzo logo"></div>'),
  definition('unusedCasino','<img alt="Unused Casino logo">'),
  definition('header','<div class="casino"><img alt="Header Casino logo"></div>')])
 before=deepcopy(p);result=showcase_brands(p)
 assert result['brands']==['NV Casino','Ritzo'] and result['count']==2 and p==before


def test_native_dataset_follows_rendered_group_excludes_basic_logo_gallery_and_unused_groups():
 p=project([shortcode('casinos')],[definition('casinos','{{#if casinos}}{{#each casinos.standard}}<img alt="{{brand}} logo">{{/each}}{{/if}}')],{
  'basic':[{'key':'logo','data':[{'alt':'Unused Gallery Brand'}]}],
  'standard':[[{'key':'brand','value':'Ritzo'},{'key':'split','value':'dontcount'}],[{'key':'brand','value':'NV Casino'}]],
  'old':[[{'key':'brand','value':'Old Casino'}]]})
 assert showcase_brands(p)['brands']==['Ritzo','NV Casino']
 p['data']['pages'][0]['content']['blocks']=[]
 assert showcase_brands(p)['count']==0


def test_ranking_tables_count_brands_but_not_game_names_or_payment_methods():
 tables=[{'type':'table','data':{'content':rows}} for rows in [
  [['Nazwa kasyna','Licencja','Bonus'],['Lemon Casino','Curacao','100%'],['NV Casino','Curacao','200%']],
  [['Nazwa Slotu','Dostawca','RTP'],['Book of Dead','Play n GO','96%']],
  [['Metoda','Czas wpłaty'],['BLIK','5 sekund']]]]
 assert showcase_brands(project(tables))['brands']==['Lemon Casino','NV Casino']


def test_nested_partials_raw_cards_and_html_ranking():
 p=project([shortcode('showcase'),{'type':'raw','data':{'html':'<table><tr><th>Casino</th><th>Bonus</th></tr><tr><td>Ritzo</td><td>100%</td></tr></table>'}}],[
  definition('showcase','{{> cards}}'),definition('cards','<div class="casino-card"><img alt="BetAlice Casino logo"></div>{{> showcase}}')])
 assert showcase_brands(p)['brands']==['BetAlice Casino','Ritzo']


def test_endpoint_showcase_only_for_general_sites(setup):
 client,db,site,state=setup
 site.brand='Общие ключи';db.commit()
 state['project']=project([shortcode('casinos')],[definition('casinos','<div class="casino"><img alt="Ritzo logo"></div>')])
 result=client.get(f'/sites/{site.id}/pages/interlinking').json()
 assert result['showcase']=={'count':1,'brands':['Ritzo'],'message':''}
 site.brand='BetOnRed';site.site_type='monobrand';db.commit()
 assert 'showcase' not in client.get(f'/sites/{site.id}/pages/interlinking').json()
