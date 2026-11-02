"""Validate and package original vector artwork generated for each template."""
import base64
import hashlib
import re
from xml.etree import ElementTree as ET

SVG = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG)
TAGS = {'svg','g','defs','linearGradient','radialGradient','stop','path','rect','circle','ellipse','line','polyline','polygon','text','tspan','title','desc'}
ATTRS = {'viewBox','width','height','x','y','x1','y1','x2','y2','cx','cy','r','rx','ry','d','points','fill','stroke','stroke-width','stroke-linecap','stroke-linejoin','stroke-dasharray','fill-rule','opacity','fill-opacity','stroke-opacity','transform','id','gradientUnits','gradientTransform','offset','stop-color','stop-opacity','font-family','font-size','font-weight','text-anchor','dominant-baseline','dx','dy','preserveAspectRatio'}


def general_brand(brand):
    return re.sub(r'[^\w]', '', brand.casefold()) in {'общиеключи','онлайнказино','onlinecasino'}


def safe_svg(value):
    if not isinstance(value,str) or not 80 <= len(value) <= 60000 or re.search(r'<!|<\?',value):
        raise ValueError('Нужен оригинальный SVG без внешних ресурсов')
    try: root=ET.fromstring(value)
    except ET.ParseError as e: raise ValueError('Некорректный SVG') from e
    if root.tag not in {'svg','{'+SVG+'}svg'}: raise ValueError('Ожидался SVG')
    for node in root.iter():
        tag=node.tag.removeprefix('{'+SVG+'}')
        if tag not in TAGS: raise ValueError('Недопустимый элемент SVG: '+tag)
        node.tag='{'+SVG+'}'+tag
        for key,text in node.attrib.items():
            if key not in ATTRS or re.search(r'[<>]|(?:https?:|data:|javascript:|@import)',text,re.I):
                raise ValueError('Недопустимый атрибут SVG')
            if 'url(' in text and not re.fullmatch(r'url\(#[a-zA-Z][\w-]*\)',text):
                raise ValueError('Внешние ресурсы SVG запрещены')
    try: box=[float(v) for v in re.split(r'[ ,]+',root.attrib['viewBox'].strip())]
    except (KeyError,ValueError): raise ValueError('SVG должен иметь viewBox')
    if len(box)!=4 or not all(-10000 < v < 10000 for v in box) or box[2]<=0 or box[3]<=0:
        raise ValueError('Некорректный размер SVG')
    if not any(n.tag.rsplit('}',1)[-1] in {'path','rect','circle','ellipse','polygon','polyline','line'} for n in root.iter()):
        raise ValueError('SVG должен содержать графику')
    return ET.tostring(root,encoding='unicode')


def fingerprint(svg):
    root=ET.fromstring(svg)
    # Ignore paint and metadata: recoloring the same geometry is not a new illustration.
    for parent in root.iter():
        for child in list(parent):
            if child.tag.rsplit("}", 1)[-1] in {"title", "desc"}:
                parent.remove(child)
    for node in root.iter():
        for key in list(node.attrib):
            if key in {'fill','stroke','opacity','fill-opacity','stroke-opacity','stop-color','id'}:
                del node.attrib[key]
        node.attrib=dict(sorted(node.attrib.items()));node.tail=None
        if node.text is not None:node.text=node.text.strip() or None
    return hashlib.sha256(ET.tostring(root)).hexdigest()


def validate_assets(raw, content, brand, previous):
    if not isinstance(raw,dict):raise ValueError('Gemini должен создать visual_assets: hero, icons, logo и favicon для общих ключей')
    required={'hero':raw.get('hero')}
    icons=raw.get('icons') or {}
    if not isinstance(icons,dict):raise ValueError('Нужны иконки секций')
    for section in content.sections:required['icon-'+section.id]=icons.get(section.id)
    if general_brand(brand):required.update(logo=raw.get('logo'),favicon=raw.get('favicon'))
    values={key:safe_svg(value) for key,value in required.items()}
    digests={key:fingerprint(value) for key,value in values.items()}
    icon_hashes=[digest for key,digest in digests.items() if key.startswith('icon-')]
    if len(set(icon_hashes))!=len(icon_hashes):raise ValueError('Для каждой секции нужна своя иконка')
    old={digest for row in previous for digest in ((row.document or {}).get('visual_assets') or {}).get('fingerprints',{}).values()}
    if old.intersection(digests.values()):raise ValueError('Графика повторяет ранее созданный шаблон; создайте новые формы и композицию')
    return {'svg':values,'fingerprints':digests,'origin':'gemini_generated'}


def image_uri(svg):
    return 'data:image/svg+xml;base64,'+base64.b64encode(svg.encode()).decode()


def visual_files(document):
    return {'assets/generated-'+key+'.svg':svg for key,svg in (document.get('visual_assets') or {}).get('svg',{}).items()}


def externalize(html,document):
    for path,svg in visual_files(document).items():html=html.replace(image_uri(svg),path)
    return html


COMPACT_HEADER_CSS = '''
body>header{display:flex!important;flex-direction:row!important;align-items:center!important;justify-content:space-between!important;flex-wrap:nowrap!important;gap:16px!important;min-height:0!important;height:auto!important;padding-top:12px!important;padding-bottom:12px!important;position:relative!important}
body>header .logo{width:clamp(120px,18vw,200px)!important;min-width:100px!important;flex-shrink:0!important;height:44px!important;min-height:0!important;padding:0!important;margin:0!important;border:0!important;background-color:transparent!important;font-size:18px!important}
body>header .desktop-nav{display:flex!important;flex-direction:row!important;flex-wrap:wrap!important;align-items:center!important;justify-content:flex-end!important;gap:6px 16px!important;width:auto!important;max-width:none!important;min-width:0!important;margin:0!important;padding:0!important;border:0!important;background:transparent!important}
body>header nav a{display:inline-block!important;width:auto!important;min-width:0!important;min-height:0!important;margin:0!important;padding:4px 0!important;font-size:14px!important;line-height:1.3!important;white-space:nowrap!important;text-decoration:none}
body>header .mobile-nav{display:none!important}
.section-icon{display:inline-block;width:36px;height:36px;vertical-align:middle;margin-right:12px;object-fit:contain}.art img{display:block;width:100%;height:100%;object-fit:contain}
@media(max-width:1100px){body>header .desktop-nav{display:none!important}body>header .mobile-nav{display:block!important;position:relative!important}body>header .mobile-nav summary{cursor:pointer;padding:8px 10px!important;font-size:14px!important}body>header .mobile-nav nav{position:absolute!important;right:0!important;top:100%!important;z-index:100!important;min-width:180px!important;max-width:calc(100vw - 32px)!important;display:flex!important;flex-direction:column!important;align-items:stretch!important;gap:8px!important;padding:16px!important;background:var(--surface,#fff);color:var(--text,#172433);border:1px solid currentColor;border-radius:12px}body>header .mobile-nav nav a{white-space:normal!important}body>header{padding:10px 16px!important}}
'''
