import base64
from io import BytesIO

import pytest
from fastapi import HTTPException
from PIL import Image
from app import showcase_logos as logos


def test_raster_is_decoded_and_reencoded_as_png():
    source = BytesIO()
    Image.new('RGB', (16, 8), 'red').save(source, 'JPEG')
    ext, buffer = logos.prepare(logos.LogoUpload(name='brand.jpg', data=base64.b64encode(source.getvalue()).decode()))
    assert ext == '.png'
    with Image.open(BytesIO(base64.b64decode(buffer))) as result:
        assert result.format == 'PNG' and result.size == (16, 8)


@pytest.mark.parametrize('svg', [
    '<svg><script>alert(1)</script></svg>',
    '<svg onload="alert(1)"/>',
    '<svg><use href="https://evil.example/logo.svg"/></svg>',
    '<svg><style>@import "https://evil.example/a.css";</style></svg>',
    '<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg>&x;</svg>',
    '<svg><path fill="url(https://evil.example)"/></svg>',
])
def test_active_and_external_svg_is_rejected(svg):
    with pytest.raises(HTTPException):
        logos.prepare(logos.LogoUpload(name='brand.svg', data=base64.b64encode(svg.encode()).decode()))


def test_svg_fragment_gradient_is_accepted():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="a"><stop offset="0" stop-color="red"/></linearGradient></defs><path fill="url(#a)" d="M0 0z"/></svg>'
    assert logos.prepare(logos.LogoUpload(name='brand.svg', data=base64.b64encode(svg.encode()).decode())) == ('.svg', svg)
