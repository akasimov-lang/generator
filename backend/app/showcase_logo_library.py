"""Reusable, reviewed wordmarks for showcases; never fetches or publishes assets."""
import base64
import hashlib
from copy import deepcopy

from app.template_asset_library import catalog, image_snapshot, normalized
from app.showcase_logos import LogoUpload, prepare


def entries(query=""):
    needle = normalized(query)
    return [deepcopy(entry) for entry in catalog().get("brands", [])
            if entry.get("showcase_ready") and (not needle or any(
                needle in normalized(name)
                for name in [entry["name"], *entry.get("aliases", [])]))]


def find(brand):
    identity = normalized(brand)
    matches = [entry for entry in entries() if identity in {
        normalized(name) for name in [entry["name"], *entry.get("aliases", [])]}]
    if len(matches) != 1:
        raise ValueError("В библиотеке нет однозначно подтверждённого логотипа этого бренда.")
    return matches[0]


def prepare_upload(brand):
    """Return native upload bytes and provenance; caller owns durable write receipts."""
    entry = find(brand)
    image = image_snapshot(entry)
    digest = hashlib.sha256(base64.b64decode(image["data"], validate=True)).hexdigest()
    if digest != entry.get("sha256"):
        raise ValueError("Файл логотипа не совпадает с проверенной версией библиотеки.")
    prepared = prepare(LogoUpload(name=entry["name"], data=image["data"]))
    return prepared, entry
