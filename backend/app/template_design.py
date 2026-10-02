"""Versioned design families; identifiers describe rendered behavior, never aliases."""
from app.template_compositions import CONCEPTS, composition_css

import random
import unicodedata

PROTOCOL_VERSION = "2"
CONCEPT_COUNT = 10
AXES = {
    "shell": ("full_width", "reading_column", "offset_column", "framed", "islands"),
    "header": ("inline", "centered", "stacked", "brand_band"),
    "navigation": ("underline", "tabs", "index", "divided", "capsule"),
    "hero": ("poster", "split_title", "left_manifesto", "inset_cover", "bottom_caption", *CONCEPTS),
    "section_rhythm": ("alternating", "ruled", "spaced", "staggered"),
    "content_patterns": ("flow", "two_columns", "lead_aside", "fact_tiles"),
    "typography": ("editorial_serif", "humanist", "geometric", "technical", "classical"),
    "palette": ("ink_copper", "milk_bordeaux", "navy_amber", "forest_sand", "plum_lavender", "white_blue", "charcoal_mint", "warm_terracotta"),
    "shape_language": ("square", "rounded", "offset_shadow", "double_border", "soft_depth"),
    "visual_style": ("circles", "diagonal", "grid", "arches", "waves"),
    "icon_system": ("none",),
    "density": ("compact", "balanced", "airy", "dense_editorial"),
    "table_pattern": ("rules", "striped", "cells", "accent_header"),
    "faq_pattern": ("open_rows", "open_grid", "open_aside", "open_numbered"),
    "footer_pattern": ("columns", "centered", "split", "stacked"),
}
CORE_AXES = ("hero", "navigation", "shell", "typography", "palette", "visual_style")


def normalize(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def compare(candidate, previous):
    matches = [key for key in AXES if candidate[key] == previous[key]]
    rejected = (len(matches) >= 4 or {"hero", "navigation"}.issubset(matches)
                or {"shell", "typography", "shape_language"}.issubset(matches))
    return {"matching_axes": matches, "similarity": round(len(matches) / 15, 3), "passed": not rejected}


def validate_design(design):
    if set(design) != set(AXES) or any(design[key] not in values for key, values in AXES.items()):
        raise ValueError("Неполный или неизвестный дизайн-паспорт")


def choose_concepts(history, seed):
    """Offer ten different compositions, varying at least four core axes per pair."""
    rng = random.Random(seed)
    concepts = []
    for _ in range(30000):
        design = {axis: rng.choice(values) for axis, values in AXES.items()}
        if any(design["hero"] == c["hero"] or sum(design[a] != c[a] for a in CORE_AXES) < 4 for c in concepts):
            continue
        if any(not compare(design, entry["design"])["passed"] for entry in history):
            continue
        concepts.append(design)
        if len(concepts) == CONCEPT_COUNT:
            break
    if len(concepts) != CONCEPT_COUNT:
        raise ValueError("Не удалось найти десять уникальных концепций в доступных семействах. История сохранена; расширьте библиотеку дизайна.")
    concepts.sort(key=lambda candidate: max((compare(candidate, p["design"])["similarity"] for p in history), default=0))
    return concepts


PALETTES = {
    "ink_copper": ("#151b23", "#202a36", "#f4eee7", "#bcc8d4", "#efad7d", "#17202a"),
    "milk_bordeaux": ("#faf6ef", "#ffffff", "#302326", "#69545c", "#8c254b", "#ffffff"),
    "navy_amber": ("#101c35", "#1e304f", "#fff5df", "#c1cadd", "#ffc86b", "#18203a"),
    "forest_sand": ("#112b24", "#1f3d33", "#fff5de", "#c0d1c0", "#e6bd7c", "#172e25"),
    "plum_lavender": ("#282033", "#382c47", "#faf3ff", "#d1bfdc", "#d2b3ff", "#292034"),
    "white_blue": ("#f0f4fa", "#ffffff", "#172943", "#52657b", "#214fb6", "#ffffff"),
    "charcoal_mint": ("#202525", "#2c3534", "#f1fbf7", "#bed2ca", "#95e0bf", "#1c2924"),
    "warm_terracotta": ("#f4ece2", "#fffaf4", "#372c26", "#70574a", "#a23c20", "#ffffff"),
}


def design_css(d):
    validate_design(d)
    page, surface, text, muted, accent, on_accent = PALETTES[d["palette"]]
    fonts = {
        "editorial_serif": ('Georgia,serif', 'Arial,sans-serif', '1.08', '700'),
        "humanist": ('"Trebuchet MS",sans-serif', 'Verdana,sans-serif', '1.12', '600'),
        "geometric": ('Futura,"Century Gothic",sans-serif', 'Arial,sans-serif', '1.02', '800'),
        "technical": ('"Courier New",monospace', 'Arial,sans-serif', '1.13', '700'),
        "classical": ('"Palatino Linotype",Palatino,serif', 'Georgia,serif', '1.16', '500'),
    }
    display, body, line, weight = fonts[d["typography"]]
    spacing = {"compact": ("38px", "16px", "1.5"), "balanced": ("60px", "17px", "1.65"),
               "airy": ("90px", "18px", "1.75"), "dense_editorial": ("48px", "16px", "1.6")}[d["density"]]
    css = f""":root{{--page:{page};--surface:{surface};--text:{text};--muted:{muted};--accent:{accent};--on-accent:{on_accent};--gap:{spacing[0]};--display:{display};--body:{body}}}
*{{box-sizing:border-box;min-width:0}}html{{scroll-behavior:smooth;scroll-padding-top:30px}}body{{margin:0;background:var(--page);color:var(--text);font: {spacing[1]}/{spacing[2]} var(--body)}}
a{{color:inherit;text-underline-offset:5px;overflow-wrap:anywhere}}a:focus-visible,summary:focus-visible{{outline:3px solid var(--accent);outline-offset:5px}}h1,h2,h3{{font-family:var(--display);line-height:{line};font-weight:{weight};overflow-wrap:anywhere}}h1{{font-size:clamp(2.5rem,6vw,5.8rem);margin:0 0 24px;max-width:20ch}}h2{{font-size:clamp(1.65rem,3vw,2.8rem);margin:0 0 24px}}h3{{font-size:1.2rem}}p{{max-width:75ch;overflow-wrap:anywhere}}header,footer,.section{{padding:var(--gap) max(24px,calc((100vw - 1160px)/2))}}header{{padding-top:24px;padding-bottom:24px;display:flex;align-items:center;gap:28px;background:var(--surface)}}
.logo{{width:clamp(140px,20vw,240px);min-height:48px;display:flex;align-items:center;font:700 1.5rem var(--display);overflow-wrap:anywhere}}.logo::before{{content:attr(data-brand)}}.logo img{{max-width:100%;height:auto;display:block}}nav{{display:flex;flex-wrap:wrap;gap:14px}}nav a{{text-decoration:none;font-size:.9rem}}.desktop-nav{{margin-left:auto}}.mobile-nav{{display:none}}.section{{scroll-margin-top:24px}}.hero{{position:relative;isolation:isolate;overflow:hidden;min-height:420px;display:grid;align-content:center;gap:20px}}.hero> :not(.art){{position:relative;z-index:1}}.hero p{{font-size:1.2rem;max-width:58ch}}.hero .cta{{justify-self:start}}.cta{{display:inline-block;background:var(--accent);color:var(--on-accent);padding:13px 24px;text-decoration:none;font-weight:700}}.art{{position:absolute;right:2%;bottom:4%;width:36%;height:75%;color:var(--accent);opacity:.12;pointer-events:none}}.art svg{{width:100%;height:100%}}.content-body{{display:grid;gap:18px}}.copy p:first-child{{margin-top:0}}.points{{margin:0;padding-left:24px}}.points li{{padding:7px 0}}.mark{{display:inline-block;width:18px;height:18px;margin-right:12px;vertical-align:middle;color:var(--accent)}}.table-wrap{{overflow-x:auto;max-width:100%;margin:22px 0}}table{{border-collapse:collapse;width:100%;font-size:.94rem}}td,th{{padding:14px;text-align:left;overflow-wrap:anywhere;border-bottom:1px solid var(--muted)}}th{{color:var(--text)}}.faq-list{{display:grid;gap:22px}}.faq-item h3{{margin:0 0 10px}}.faq-item p{{margin:0}}footer{{background:var(--surface);display:grid;gap:28px;color:var(--muted)}}footer strong{{color:var(--text);font:700 1.8rem var(--display)}}footer nav{{color:var(--text)}}.footer-note{{font-size:.9rem}}
"""
    rules = {
        "shell": {
            "full_width": "",
            "reading_column": ".section{padding-left:max(24px,calc((100vw - 800px)/2));padding-right:max(24px,calc((100vw - 800px)/2))}",
            "offset_column": ".section{margin-left:17%;padding-left:5%;padding-right:8%;border-left:1px solid var(--muted)}",
            "framed": "body{margin:18px;border:2px solid var(--muted)}.section,header,footer{padding-left:5%;padding-right:5%}",
            "islands": ".section{max-width:1120px;margin:26px auto;padding:48px;background:var(--surface)}",
        },
        "header": {
            "inline": "",
            "centered": "header{flex-direction:column;text-align:center}.logo{justify-content:center}.desktop-nav{margin:0;justify-content:center}",
            "stacked": "header{align-items:flex-start;flex-direction:column;border-bottom:4px solid var(--accent)}.desktop-nav{margin:0}",
            "brand_band": "header{background:var(--accent);color:var(--on-accent);justify-content:space-between}.logo{font-size:2rem}.desktop-nav{max-width:65%}",
        },
        "navigation": {
            "underline": "nav a{border-bottom:2px solid currentColor;padding:8px 0}",
            "tabs": "nav{gap:4px}nav a{padding:10px 15px;background:var(--page);color:var(--text)}",
            "index": "nav{counter-reset:nav}nav a::before{counter-increment:nav;content:counter(nav,decimal-leading-zero) ' ';font-family:monospace;opacity:.65}",
            "divided": "nav a{padding:6px 12px;border-left:1px solid currentColor}",
            "capsule": "nav a{border:1px solid currentColor;border-radius:30px;padding:7px 14px}",
        },
        "hero": {
            "poster": ".hero{text-align:center;justify-items:center;min-height:550px}.hero h1{max-width:17ch}.hero .cta{justify-self:center}.art{inset:10% 10%;width:80%;height:80%}",
            "split_title": ".hero{grid-template-columns:1.15fr 1fr;gap:30px}.hero h1{grid-row:1 / 4}.hero .art{right:5%;width:40%}",
            "left_manifesto": ".hero{min-height:560px}.hero h1{max-width:13ch}.hero p{max-width:44ch}.art{right:0;width:45%}",
            "inset_cover": ".hero{margin-top:28px;margin-bottom:28px;border:3px solid var(--accent);min-height:450px}.hero h1{font-size:clamp(2.5rem,5vw,4.6rem)}.art{width:50%;right:0}",
            "bottom_caption": ".hero{min-height:600px;align-content:end;padding-top:180px}.hero h1{max-width:24ch}.art{top:0;height:50%;width:90%;right:5%}",
        },
        "section_rhythm": {
            "alternating": ".section:nth-of-type(even){background:var(--surface)}",
            "ruled": ".section+.section{border-top:1px solid var(--muted)}",
            "spaced": ".section+.section{margin-top:35px}.section:not(:first-of-type) h2{max-width:18ch}",
            "staggered": ".section:nth-of-type(even){padding-right:18%}.section:nth-of-type(odd):not(:first-of-type){padding-left:18%}",
        },
        "content_patterns": {
            "flow": "",
            "two_columns": ".content-body{grid-template-columns:1fr 1fr;gap:40px}",
            "lead_aside": ".content-body{grid-template-columns:2fr 1fr}.points{border-left:2px solid var(--accent);padding:0 0 0 30px;list-style:none}",
            "fact_tiles": ".points{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;list-style:none;padding:0}.points li{background:var(--surface);padding:22px;border:1px solid var(--muted)}",
        },
        "shape_language": {
            "square": ".cta,.points li,.faq-item{border-radius:0}",
            "rounded": ".cta,.table-wrap{border-radius:24px}.faq-item{border-radius:20px;padding:20px;border:1px solid var(--muted)}",
            "offset_shadow": ".cta{box-shadow:5px 5px 0 var(--muted)}.faq-item{border:1px solid var(--muted);padding:20px;box-shadow:4px 4px 0 var(--muted)}",
            "double_border": ".cta,.faq-item{border:4px double currentColor}.faq-item{padding:20px}",
            "soft_depth": ".cta{border-radius:10px;box-shadow:0 8px 22px #0003}.faq-item{padding:20px;background:var(--surface);border-radius:10px;box-shadow:0 6px 18px #0002}",
        },
        "table_pattern": {
            "rules": "th{border-bottom:3px solid var(--accent)}",
            "striped": "tbody tr:nth-child(odd){background:var(--surface)}",
            "cells": "td,th{border:1px solid var(--muted)}",
            "accent_header": "thead th{background:var(--accent);color:var(--on-accent)}",
        },
        "faq_pattern": {
            "open_rows": ".faq-item{border-bottom:1px solid var(--muted);padding-bottom:22px}",
            "open_grid": ".faq-list{grid-template-columns:1fr 1fr}",
            "open_aside": ".faq-item{display:grid;grid-template-columns:1fr 2fr;gap:24px}",
            "open_numbered": ".faq-list{counter-reset:faq}.faq-item h3::before{counter-increment:faq;content:counter(faq) '. ';color:var(--accent)}",
        },
        "footer_pattern": {
            "columns": "footer{grid-template-columns:1fr 2fr}footer nav{display:grid;grid-template-columns:1fr 1fr}.footer-note{grid-column:1/-1}",
            "centered": "footer{text-align:center;justify-items:center}footer nav{justify-content:center}",
            "split": "footer{grid-template-columns:1fr 1fr}footer nav{flex-direction:column;align-items:flex-end}.footer-note{grid-column:1/-1}",
            "stacked": "footer nav{border-top:1px solid var(--muted);padding-top:22px}footer strong{font-size:2.6rem}",
        },
    }
    for axis, options in rules.items():
        css += options.get(d[axis], "") + "\n"
    css += """@media(max-width:760px){body{margin:0;border:0;font-size:16px;line-height:1.5}header{padding:18px;flex-direction:row;align-items:center;justify-content:space-between;text-align:left;flex-wrap:wrap}.logo{justify-content:flex-start;max-width:68%}.desktop-nav{display:none}.mobile-nav{display:block}.mobile-nav summary{cursor:pointer;padding:10px}.mobile-nav nav{padding:18px 0;max-width:85vw}.section{margin:0;padding:30px 20px;border-left:0;max-width:none}.section:nth-of-type(even),.section:nth-of-type(odd):not(:first-of-type){padding-left:20px;padding-right:20px}.section+.section{margin-top:0}.hero{min-height:360px;grid-template-columns:1fr;text-align:left;justify-items:start;gap:14px}.hero h1{grid-row:auto;font-size:clamp(2.2rem,10vw,3.4rem);max-width:100%;margin-bottom:8px}.hero p{font-size:1.05rem}.hero .cta{justify-self:start}.hero .art{right:0;width:65%;opacity:.08}.content-body,.faq-list,.faq-item{grid-template-columns:1fr;gap:18px}.points{border-left:0}.points li{padding:8px}.table-wrap{margin:18px 0}td,th{padding:10px;min-width:110px}footer{padding:30px 20px;grid-template-columns:1fr;text-align:left;justify-items:start}footer nav{align-items:flex-start;justify-content:flex-start}h2{margin-bottom:18px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}"""
    mobile_hero = {
        "poster": ".hero{text-align:center;justify-items:center;min-height:430px}.hero h1{font-size:3.2rem}.hero .cta{justify-self:center}",
        "split_title": ".hero{min-height:380px}.hero h1{border-bottom:2px solid var(--accent);padding-bottom:20px}.hero p{font-size:1rem}",
        "left_manifesto": ".hero{min-height:320px}.hero h1{max-width:12ch}.hero .art{width:45%;height:45%;bottom:0}",
        "inset_cover": ".hero{margin:0;padding:26px 18px;border:2px solid var(--accent);min-height:360px}.hero h1{font-size:2.3rem}",
        "bottom_caption": ".hero{min-height:500px;padding-top:100px;align-content:end}.hero .art{top:0;width:100%;height:32%}",
    }
    css += "@media(max-width:760px){" + mobile_hero.get(d["hero"], "") + "}"
    if d["navigation"] == "tabs":
        css += "@media(max-width:760px){header .desktop-nav{display:flex;max-width:100%;width:100%;overflow-x:auto;flex-wrap:nowrap;margin:0}header .desktop-nav a{flex:none}header .mobile-nav{display:none}}"
    elif d["navigation"] == "index":
        css += "@media(max-width:760px){header .desktop-nav{display:grid;grid-template-columns:1fr 1fr;gap:8px;max-width:100%;width:100%;margin:0}header .desktop-nav a{font-size:.8rem}header .mobile-nav{display:none}}"
    if d["hero"] in CONCEPTS:
        css += composition_css(d["hero"])
    return css


def art_svg(style):
    shapes = {
        "circles": '<circle cx="180" cy="180" r="140"/><circle cx="420" cy="270" r="130" fill="none" stroke="currentColor" stroke-width="24"/>',
        "diagonal": '<path d="M20 360 220 20h100L120 360zM260 360 460 20h100L360 360z"/>',
        "grid": ''.join(f'<rect x="{x}" y="{y}" width="70" height="70" rx="6"/>' for x in range(20,550,110) for y in range(20,350,110)),
        "arches": '<path d="M80 380V180a140 140 0 0 1 280 0v200M200 380V180a140 140 0 0 1 280 0v200" fill="none" stroke="currentColor" stroke-width="40"/>',
        "waves": '<path d="M0 80Q150 220 300 80T600 80M0 190Q150 330 300 190T600 190M0 300Q150 440 300 300T600 300" fill="none" stroke="currentColor" stroke-width="26"/>',
    }
    return '<svg viewBox="0 0 600 400" xmlns="http://www.w3.org/2000/svg" fill="currentColor">' + shapes[style] + '</svg>'

