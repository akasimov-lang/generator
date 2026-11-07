import base64
import hashlib
from io import BytesIO

import pytest
from PIL import Image

from app import showcase_logo_library as library
from app.template_asset_library import image_snapshot, normalized


def test_alias_resolves_exact_brand_without_substring_confusion():
    assert library.find(" casinoDAYS ")["name"] == "Casino Days"
    assert library.find("7bit")["name"] == "7Bit Casino"
    with pytest.raises(ValueError):
        library.find("casino")


def test_reviewed_catalog_has_unique_identities_and_readable_verified_files():
    identities = {}
    assert library.entries()
    for entry in library.entries():
        for name in [entry["name"], *entry.get("aliases", [])]:
            identity = normalized(name)
            assert identities.get(identity, entry["id"]) == entry["id"]
            identities[identity] = entry["id"]
        assert entry["source"].startswith("https://")
        assert entry["source_page"].startswith("https://")
        assert entry["surface"] in {"dark", "light"}
        raw = base64.b64decode(image_snapshot(entry)["data"], validate=True)
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
        with Image.open(BytesIO(raw)) as image:
            image.load()
            assert image.format == "PNG"
            assert image.size == (entry["width"], entry["height"])
            assert image.getbbox() is not None


def test_prepared_library_logo_uses_native_png_contract():
    (extension, data), entry = library.prepare_upload("Zoccer")
    assert extension == ".png" and entry["surface"] == "light"
    with Image.open(BytesIO(base64.b64decode(data))) as image:
        assert image.format == "PNG" and image.mode == "RGBA"


def test_changed_asset_is_not_silently_uploaded(monkeypatch):
    original = library.image_snapshot
    monkeypatch.setattr(library, "image_snapshot", lambda entry: {
        **original(entry), "data": base64.b64encode(b"different image").decode()})
    with pytest.raises(ValueError, match="проверенной версией"):
        library.prepare_upload("Zoccer")


def test_legacy_favicon_is_not_advertised_as_reviewed_showcase_wordmark():
    assert not library.entries("Casumo")
    with pytest.raises(ValueError):
        library.prepare_upload("Casumo")
