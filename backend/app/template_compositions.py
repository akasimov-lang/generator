"""Additional page compositions: real markup and responsive layout, no scripts."""
from html import escape

CONCEPTS = {
    'twin_portal': ('Двойная витрина', 'Two large linked topic panels before a centered introduction; compact content tiles.'),
    'promo_catalog': ('Промоблок и категории', 'Introduction beside a highlighted topic panel; a row of linked categories below.'),
    'review_dashboard': ('Обзор со сводкой', 'Brand overview with a factual checklist beside it, then a full-width contents band.'),
    'editorial_index': ('Редакционный гид', 'Narrow reading area with a contents column and ruled article sections.'),
    'feature_billboard': ('Визуальный баннер', 'Large geometric illustration beside a compact text panel; alternating feature rows.'),
    'journey_map': ('Пошаговый гид', 'Intro followed by a visual route through topics; a vertical timeline through sections.'),
    'card_directory': ('Каталог разделов', 'Compact title followed by an asymmetric grid of linked topic cards; boxed content sections.'),
}


def hero_markup(kind, content, artwork):
    e = escape
    heading = f'<h1>{e(content.heading)}</h1>'
    intro = f'<p>{e(content.intro)}</p>'
    cta = f'<a class="cta" href="#{content.sections[0].id}">{e(content.cta_label)}</a>'
    art = f'<div class="composition-art" aria-hidden="true">{artwork}</div>'
    def card(section, i, detail=True):
        return (f'<a class="topic-card" href="#{section.id}">'
                f'<strong>{e(section.title)}</strong>'
                + (f'<span>{e(section.bullets[0])}</span>' if detail else '') + '</a>')
    cards = ''.join(card(s, i) for i, s in enumerate(content.sections[:4]))
    index = f'<nav class="topic-index" aria-label="{e(content.menu_label)}">' + ''.join(card(s, i, False) for i, s in enumerate(content.sections)) + '</nav>'
    copy = f'<div class="hero-copy">{heading}{intro}{cta}</div>'
    if kind == 'twin_portal':
        return f'<div class="hero-tiles">{cards if len(content.sections) < 2 else "".join(card(s,i) for i,s in enumerate(content.sections[:2]))}</div>{copy}'
    if kind == 'promo_catalog':
        return copy + f'<div class="hero-promo">{art}{card(content.sections[0],0)}</div><nav class="category-strip" aria-label="{e(content.menu_label)}">{cards}</nav>'
    if kind == 'review_dashboard':
        points = ''.join(f'<li>{e(p)}</li>' for p in content.sections[0].bullets[:4])
        return copy + f'<aside class="hero-summary"><h2>{e(content.sections[0].title)}</h2><ul>{points}</ul></aside>' + index
    if kind == 'editorial_index':
        return copy + index
    if kind == 'feature_billboard':
        return f'<div class="hero-visual">{art}</div>' + copy
    if kind == 'journey_map':
        return copy + f'<nav class="journey-steps" aria-label="{e(content.menu_label)}">{cards}</nav>'
    if kind == 'card_directory':
        return copy + f'<nav class="directory-grid" aria-label="{e(content.menu_label)}">{cards}</nav>'
    raise ValueError('Unknown composition')


COMMON = '''
.hero-copy{position:relative;z-index:1}.hero-copy h1{font-size:clamp(2.3rem,4.5vw,4.5rem)}
.hero-copy .cta{margin-top:18px}.topic-card{display:flex;flex-direction:column;gap:16px;padding:26px;background:var(--surface);border:1px solid var(--muted);text-decoration:none;position:relative;overflow:hidden}
.topic-card strong{font:700 clamp(1.15rem,2vw,1.8rem)/1.2 var(--display)}.topic-card>span:last-child{font-size:.95rem;max-width:46ch}.topic-number{color:var(--accent);font:700 1rem var(--body)}
.topic-card:hover{outline:2px solid var(--accent);outline-offset:-2px}.composition-art{color:var(--accent)}.composition-art svg{display:block;width:100%;height:auto}
.topic-index{display:grid;gap:0}.topic-index .topic-card{border-width:0 0 1px;padding:16px}.topic-index .topic-card strong{font-size:1.05rem}
'''
CSS = {
    'twin_portal': '''.hero{gap:44px}.hero-tiles{display:grid;grid-template-columns:1fr 1fr;gap:24px}.hero-tiles .topic-card{min-height:290px;justify-content:end;padding:34px;border-radius:18px;background:linear-gradient(135deg,var(--surface) 55%,var(--accent));border:0}.hero-tiles .topic-card:nth-child(2){background:linear-gradient(25deg,var(--surface) 55%,var(--accent))}.hero-tiles strong{font-size:clamp(1.6rem,3vw,2.7rem)}.hero-copy{text-align:center}.hero-copy h1,.hero-copy p{margin-left:auto;margin-right:auto}.section:not(#hero){border-top:1px solid var(--muted)}''',
    'promo_catalog': '''.hero{grid-template-columns:1.1fr 1fr;gap:32px}.hero-promo{position:relative;border-radius:20px;overflow:hidden;background:var(--surface);display:grid;align-items:center;min-height:340px}.hero-promo .composition-art{position:absolute;inset:0;opacity:.18}.hero-promo .topic-card{background:transparent;border:0;z-index:1}.hero-promo strong{font-size:2.2rem}.category-strip{grid-column:1/-1;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.category-strip .topic-card{padding:18px;border-radius:12px}.category-strip .topic-card>span:last-child{display:none}.section:not(#hero):not(#faq) .content-body{grid-template-columns:1fr 1fr}''',
    'review_dashboard': '''.hero{grid-template-columns:1.4fr 1fr;align-items:center;gap:36px}.hero-summary{padding:30px;border:2px solid var(--accent);background:var(--surface);border-radius:18px}.hero-summary h2{font-size:1.5rem}.hero-summary ul{padding-left:20px}.hero-summary li{padding:10px 0}.hero>.topic-index{grid-column:1/-1;grid-template-columns:repeat(3,minmax(0,1fr));background:var(--surface);padding:18px}.hero>.topic-index .topic-card{background:transparent}.section:not(#hero){border-top:1px solid var(--muted)}''',
    'editorial_index': '''.hero{grid-template-columns:2fr 1fr;gap:64px;align-items:start;min-height:0}.hero-copy h1{font-size:clamp(2.4rem,5vw,4.8rem);max-width:16ch}.hero>.topic-index{border-top:5px solid var(--accent)}.hero>.topic-index .topic-card{background:transparent;flex-direction:row;align-items:baseline}.section:not(#hero):not(#faq){display:grid;grid-template-columns:minmax(140px,1fr) 3fr;column-gap:40px;border-top:1px solid var(--muted)}.section:not(#hero):not(#faq)>h2{font-size:1.6rem}.section:not(#hero):not(#faq)>.table-wrap{grid-column:2}.section:not(#hero):not(#faq) .content-body{grid-template-columns:1fr}''',
    'feature_billboard': '''.hero{grid-template-columns:1.15fr 1fr;gap:0;background:var(--surface);border:1px solid var(--muted)}.hero-visual{min-height:460px;display:grid;place-items:center;background:var(--accent);padding:24px}.hero-visual .composition-art{color:var(--on-accent);width:100%;transform:rotate(-12deg)}.hero-copy{padding:40px}.hero-copy h1{font-size:clamp(2.2rem,3.8vw,4rem)}.section:not(#hero):not(#faq) .content-body{grid-template-columns:1.2fr 1fr;gap:50px}.section:nth-of-type(odd):not(#hero):not(#faq) .copy{order:2}''',
    'journey_map': '''.hero{min-height:0;gap:44px}.hero-copy{max-width:850px}.journey-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0}.journey-steps .topic-card{border:0;border-top:4px solid var(--accent);background:transparent;padding:24px 24px 24px 0}.journey-steps .topic-number{font-size:2.4rem}.section:not(#hero):not(#faq){position:relative;border-left:4px solid var(--accent);margin-left:max(24px,calc((100vw - 1160px)/2));padding-left:40px}''',
    'card_directory': '''.hero{min-height:0;gap:32px}.hero-copy{display:grid;grid-template-columns:1.2fr 1fr;gap:20px 40px;align-items:start}.hero-copy h1{grid-row:1/3}.hero-copy .cta{justify-self:start;margin-top:0}.directory-grid{display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:18px}.directory-grid .topic-card:first-child{grid-row:span 2;background:var(--accent);color:var(--on-accent);justify-content:end;min-height:280px}.directory-grid .topic-card:first-child .topic-number{color:inherit}.directory-grid .topic-card:last-child{grid-column:2/-1}.section:not(#hero){border:1px solid var(--muted);border-radius:20px;margin-top:20px;margin-bottom:20px;background:var(--surface)}''',
}
MOBILE = '''
@media(max-width:760px){.hero,.hero-copy{grid-template-columns:1fr;gap:24px;text-align:left}.hero-copy h1{grid-row:auto;font-size:clamp(2.1rem,9vw,3rem);max-width:100%}.hero-copy p{font-size:1rem}.hero-tiles,.category-strip,.journey-steps,.directory-grid,.hero>.topic-index{grid-template-columns:1fr;gap:14px}.hero-tiles .topic-card{min-height:210px;padding:24px}.topic-card{padding:22px}.hero-summary{padding:22px}.hero-promo{min-height:230px}.hero-visual{min-height:220px;padding:16px}.hero-visual .composition-art{max-width:300px}.hero:has(.hero-visual) .hero-copy{padding:24px}.directory-grid .topic-card:first-child{grid-row:auto;min-height:210px}.directory-grid .topic-card:last-child{grid-column:auto}.hero>.topic-index,.category-strip{grid-column:auto}.section:not(#hero):not(#faq){display:block;margin-left:0;padding:30px 20px}.section:not(#hero):not(#faq) .content-body{grid-template-columns:1fr;gap:18px}.section:nth-of-type(odd):not(#hero):not(#faq) .copy{order:initial}.journey-steps .topic-card{border-top:0;border-left:3px solid var(--accent);padding:12px 20px}.hero-copy .cta{max-width:100%}}
'''


def composition_css(kind):
    return COMMON + CSS[kind] + MOBILE
