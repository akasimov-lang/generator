"""Reusable vector phone frames and real, public-site screen capture."""
import base64
import os
from html import escape
from urllib.parse import urlsplit

# Original schematic front views inspired by these device families, not OEM renders.
FRAMES = [
    ('iphone_16', 'iPhone 16', 46, 'island', '#7d8592', 850),
    ('iphone_16_pro', 'iPhone 16 Pro', 44, 'island', '#b6aca0', 864),
    ('iphone_16_pro_max', 'iPhone 16 Pro Max', 48, 'island', '#42464c', 880),
    ('iphone_13', 'iPhone 13', 44, 'notch', '#8dabc0', 850),
    ('iphone_se', 'iPhone SE', 36, 'home', '#b9bdc2', 810),
    ('galaxy_s25', 'Samsung Galaxy S25', 34, 'punch', '#8999a6', 864),
    ('galaxy_s25_ultra', 'Samsung Galaxy S25 Ultra', 22, 'punch', '#a09b90', 874),
    ('galaxy_a55', 'Samsung Galaxy A55', 30, 'punch', '#8093ab', 860),
    ('galaxy_z_flip', 'Samsung Galaxy Z Flip', 35, 'punch', '#b1a6c1', 916),
    ('oppo_find_x8', 'OPPO Find X8', 40, 'punch', '#a9adb1', 860),
    ('oppo_reno12', 'OPPO Reno12', 39, 'punch', '#b5afc8', 884),
    ('pixel_9', 'Google Pixel 9', 49, 'punch', '#8b998e', 855),
    ('xiaomi_14', 'Xiaomi 14', 35, 'punch', '#7e9f98', 858),
    ('oneplus_12', 'OnePlus 12', 33, 'punch', '#5a776c', 894),
    ('nothing_phone_2', 'Nothing Phone (2)', 42, 'punch', '#686b70', 864),
]


def frame_svg(frame_id, screen=None):
    _, _, radius, camera, metal, height = next(f for f in FRAMES if f[0] == frame_id)
    top = 65 if camera == 'home' else 18
    bottom = 68 if camera == 'home' else 18
    sh = height - top - bottom
    inset = 18 if camera == 'home' else 14
    camera_shape = {
        'island': '<rect x="143" y="28" width="114" height="31" rx="16" fill="#08090b"/><circle cx="232" cy="43" r="5" fill="#182535"/>',
        'notch': '<path d="M112 18h176v20q0 22-22 22H134q-22 0-22-22z" fill="#08090b"/><rect x="167" y="30" width="52" height="5" rx="3" fill="#36393e"/>',
        'punch': '<circle cx="200" cy="34" r="8" fill="#08090b"/><circle cx="200" cy="34" r="3" fill="#1a2c3c"/>',
        'home': f'<rect x="170" y="31" width="60" height="5" rx="3" fill="#34373c"/><circle cx="200" cy="{height-35}" r="20" fill="#13151a" stroke="{metal}" stroke-width="2"/>',
    }[camera]
    picture = f'<image href="{escape(screen, quote=True)}" x="{inset}" y="{top+48 if camera != "home" else top}" width="{400-2*inset}" height="{sh-48 if camera != "home" else sh}" preserveAspectRatio="xMidYMin slice"/>' if screen else ''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 {height}" fill="none">
<defs><linearGradient id="metal" x2="1" y2="1"><stop stop-color="#eef0f1"/><stop offset=".18" stop-color="{metal}"/><stop offset=".5" stop-color="#202327"/><stop offset=".8" stop-color="{metal}"/><stop offset="1" stop-color="#090a0c"/></linearGradient><mask id="body-mask"><rect width="400" height="{height}" fill="white"/><rect x="{inset}" y="{top+48 if camera != 'home' else top}" width="{400-2*inset}" height="{sh-48 if camera != 'home' else sh}" rx="{max(4,radius-12) if camera!='home' else 4}" fill="black"/></mask><clipPath id="screen"><rect x="{inset}" y="{top}" width="{400-2*inset}" height="{sh}" rx="{max(4,radius-12) if camera!='home' else 4}"/></clipPath></defs>
<rect x="0" y="138" width="7" height="55" rx="3" fill="{metal}"/><rect x="0" y="215" width="7" height="84" rx="3" fill="{metal}"/><rect x="393" y="186" width="7" height="102" rx="3" fill="{metal}"/>
<g mask="url(#body-mask)"><rect x="4" y="2" width="392" height="{height-4}" rx="{radius}" fill="url(#metal)" stroke="#707379"/>
<rect x="9" y="7" width="382" height="{height-14}" rx="{radius-4}" fill="#192028" stroke="#32363b"/></g>
<g clip-path="url(#screen)">{picture}</g>{camera_shape}
</svg>'''


def data_uri(mime, content):
    return f'data:{mime};base64,' + base64.b64encode(content).decode()


async def capture_brand(url, brand):
    """Capture provided public URL only; no login, clicks, or model-generated logos."""
    from playwright.async_api import async_playwright
    from app.factual_research import require_public_url
    await require_public_url(url)
    async with async_playwright() as p:
        options = {'headless': True}
        if os.path.exists('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'):
            options['executable_path'] = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        browser = await p.chromium.launch(**options)
        try:
            context = await browser.new_context(viewport={'width': 390, 'height': 1000}, device_scale_factor=1,
                is_mobile=True, has_touch=True, service_workers='block', accept_downloads=False)
            await context.route_web_socket('**/*', lambda ws: ws.close())
            async def public_only(route):
                try:
                    if route.request.method not in {'GET', 'HEAD'} or route.request.resource_type in {'media', 'websocket'}:
                        await route.abort(); return
                    await require_public_url(route.request.url)
                    await route.continue_()
                except Exception:
                    await route.abort()
            await context.route('**/*', public_only)
            page = await context.new_page()
            response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            if not response or response.status >= 400:
                raise ValueError('Сайт бренда недоступен для скриншотов')
            await require_public_url(page.url)
            await page.wait_for_timeout(1800)
            body = await page.locator('body').inner_text(timeout=5000)
            title = (await page.title()).lower()
            if any(term in title for term in ['just a moment', 'access denied', 'captcha']):
                raise ValueError('Сайт бренда закрыт проверкой доступа')
            normalized = lambda text: ''.join(c for c in text.casefold() if c.isalnum())
            if normalized(brand) not in normalized(body + ' ' + title + ' ' + urlsplit(page.url).hostname):
                raise ValueError('На указанной странице не найден выбранный бренд')
            logo = None
            candidates = page.locator('header img, img[alt*="logo" i], [class*="logo"] img, [class*="logo"] svg')
            for i in range(min(await candidates.count(), 12)):
                node = candidates.nth(i)
                box = await node.bounding_box()
                if box and 25 <= box['width'] <= 600 and 10 <= box['height'] <= 200 and await node.is_visible():
                    logo = data_uri('image/png', await node.screenshot(type='png', timeout=5000))
                    break
            height = await page.evaluate('document.documentElement.scrollHeight')
            offsets = list(dict.fromkeys([0, min(900,max(0,height-1000)), min(1800,max(0,height-1000))]))
            screens = []
            for offset in offsets:
                await page.evaluate('(y) => scrollTo(0,y)', offset)
                await page.wait_for_timeout(250)
                screens.append(data_uri('image/jpeg', await page.screenshot(type='jpeg', quality=82)))
            return {'source_url': page.url, 'screens': screens, 'logo': logo}
        finally:
            await browser.close()


def gallery(document, brand):
    media = document.get('brand_media') or {}
    if not media.get('screens'):
        return ''
    heading = document['content'].get('mobile_gallery_heading') or brand
    frames = media.get('frames') or [FRAMES[0][0]] * len(media['screens'])
    images = []
    for i, (screen, frame) in enumerate(zip(media['screens'], frames)):
        svg = frame_svg(frame, screen)
        images.append(f'<figure><img src="{data_uri("image/svg+xml", svg.encode())}" alt="{escape(brand)} · {i+1}" width="400" height="900" loading="lazy"></figure>')
    return f'<section class="section" id="mobile-screens"><h2>{escape(heading)}</h2><div class="phone-gallery">{"".join(images)}</div></section>'


PHONE_CSS = '.phone-gallery{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:clamp(20px,4vw,70px);align-items:start}.phone-gallery figure{margin:0}.phone-gallery img{display:block;width:100%;height:auto;filter:drop-shadow(0 14px 12px #0004)}@media(max-width:760px){.phone-gallery{grid-template-columns:1fr;justify-items:center}.phone-gallery figure{width:min(100%,340px)}}'
