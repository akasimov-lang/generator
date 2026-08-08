from types import SimpleNamespace

from app import models
from app.services import build_publication_payload


class FakeDb:
    def __init__(self, section: object) -> None:
        self.section = section

    def get(self, model: object, item_id: str) -> object | None:
        if model is models.Section and item_id == "section-id":
            return self.section
        return None


def test_publication_payload_adds_section_target() -> None:
    section = SimpleNamespace(external_id="casino-menu", name="Casinos", path="/online-casinos/", menu_type="footer")
    item = SimpleNamespace(
        section_id="section-id",
        generated_json={
            "menu": {"header": [], "footer": []},
            "pages": [{"slug": "/test/", "title": "Test", "content": {"blocks": []}}],
        },
    )

    payload = build_publication_payload(FakeDb(section), item)

    assert payload["publication_target"] == {
        "section_id": "casino-menu",
        "section_name": "Casinos",
        "section_path": "/online-casinos/",
        "menu_type": "footer",
    }
    assert payload["pages"][0]["sectionId"] == "casino-menu"
    assert payload["pages"][0]["sectionPath"] == "/online-casinos/"
