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
        section_content_mode="nested",
        section_source_slug="/test/",
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
        "content_mode": "nested",
    }
    assert payload["pages"][0]["sectionId"] == "casino-menu"
    assert payload["pages"][0]["sectionPath"] == "/online-casinos/"
    assert payload["pages"][0]["sectionContentMode"] == "nested"
    assert payload["pages"][0]["slug"] == "/online-casinos/test/"


def test_publication_payload_can_update_the_menu_page_itself() -> None:
    section = SimpleNamespace(external_id="casino-menu", name="Casinos", path="/online-casinos/", menu_type="header")
    item = SimpleNamespace(
        section_id="section-id",
        section_content_mode="menu_page",
        section_source_slug="/generated-article/",
        generated_json={"pages": [{"slug": "/generated-article/", "title": "Casinos", "content": {"blocks": []}}]},
    )

    payload = build_publication_payload(FakeDb(section), item)

    assert payload["publication_target"]["content_mode"] == "menu_page"
    assert payload["pages"][0]["slug"] == "/online-casinos/"
    assert payload["pages"][0]["sectionContentMode"] == "menu_page"


def test_publication_payload_converts_legacy_markdown_bold_to_html() -> None:
    section = SimpleNamespace(external_id="guides", name="Guides", path="/guides/", menu_type="header")
    item = SimpleNamespace(
        section_id="section-id",
        section_content_mode="menu_page",
        section_source_slug="/guides/",
        generated_json={"pages": [{
            "slug": "/guides/",
            "content": {"blocks": [{"type": "paragraph", "data": {"text": "Lire **les conditions** avant de jouer."}}]},
        }]},
    )

    payload = build_publication_payload(FakeDb(section), item)

    assert payload["pages"][0]["content"]["blocks"][0]["data"]["text"] == "Lire <strong>les conditions</strong> avant de jouer."
