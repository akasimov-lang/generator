from xml.etree import ElementTree
import httpx
from app.pelican_missing_favicons import icon, is_image, public_state


def test_seven_distinct_favicons_are_self_contained_svg():
    icons = [icon(i) for i in range(7)]
    assert len(set(icons)) == 7
    for value in icons:
        root = ElementTree.fromstring(value)
        assert root.attrib['viewBox'] == '0 0 64 64'
        assert not any(x.tag.split('}')[-1] in {'script','image','foreignObject'} for x in root.iter())


def test_existing_public_favicon_is_preserved_even_if_native_setting_is_empty():
    def handler(request):
        if request.url.path == '/': return httpx.Response(200, text='<link rel="icon" href="/brand.svg">')
        assert request.url.path == '/brand.svg'
        return httpx.Response(200, text=icon(0), headers={'content-type': 'image/svg+xml'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = public_state(client, 'https://site.test')
    assert result['state'] == 'present' and result['linked'] and result['url'].endswith('/brand.svg')


def test_missing_images_are_distinguished_from_html_fallbacks_and_unavailable_sites():
    def handler(request):
        if request.url.path == '/': return httpx.Response(200, text='<link rel="icon" href="/favicon.png">')
        return httpx.Response(200, text='<html>not found</html>', headers={'content-type':'image/png'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert public_state(client, 'https://site.test')['state'] == 'missing'
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(403))) as client:
        assert public_state(client, 'https://site.test')['state'] == 'unavailable'


def test_a_configured_file_is_not_mistaken_for_a_publicly_linked_icon():
    def handler(request):
        if request.url.path == '/brand.svg':
            return httpx.Response(200, text=icon(1), headers={'content-type':'image/svg+xml'})
        return httpx.Response(200, text='<html>No favicon link</html>')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=public_state(client,'https://site.test','<link rel="icon" href="/brand.svg">')
    assert result['state']=='present' and not result['linked']
