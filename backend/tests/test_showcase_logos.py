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


def test_svg_is_rejected_before_calling_webdev():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0z"/></svg>'
    with pytest.raises(HTTPException):
        logos.prepare(logos.LogoUpload(name='brand.svg', data=base64.b64encode(svg.encode()).decode()))


def project_logo(src, canon='current.test'):
    return {'settings':{'canon':canon},'data':{'casinos':{'basic':[{'key':'logo','type':'gallery','data':[{'id':7,'src':src}]}]}}}


def test_legacy_project_folder_logo_resolves_to_current_main():
    record=[{'key':'logo','type':'logo','id':7}]
    assert logos.url(project_logo('/casinos/hitnspin.webp'),record)=='https://current.test/casinos/hitnspin.webp'
    assert logos.url(project_logo('/images/brand.png','https://current.test/'),record)=='https://current.test/images/brand.png'


def test_uploaded_logo_still_resolves_without_changing_gallery():
    from copy import deepcopy
    project=project_logo('/uploads/brand.webp');before=deepcopy(project)
    assert logos.url(project,[{'key':'logo','id':7}])=='https://current.test/uploads/brand.webp'
    assert project==before


def test_root_logo_paths_cannot_switch_host_or_traverse_directories():
    record=[{'key':'logo','id':7}]
    assert logos.url(project_logo('//other.test/logo.png'),record) is None
    assert logos.url(project_logo('/%2fother.test/logo.png'),record) is None
    assert logos.url(project_logo('/casinos/../secret'),record) is None
    assert logos.url(project_logo('/\\other.test/logo.png'),record) is None
    assert logos.url(project_logo('/logo.png','https://user@other.test'),record) is None


def test_unavailable_or_invalid_main_keeps_logo_unresolved_without_breaking_editor():
    record=[{'key':'logo','id':7}]
    assert logos.url(project_logo('/logo.png',None),record) is None
    assert logos.url(project_logo('/logo.png','https://['),record) is None
