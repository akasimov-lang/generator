import json
import os

from playwright.sync_api import expect, sync_playwright


site = dict(
    id="preview",
    name="example.cz",
    base_url="https://example.cz",
    publication_endpoint="",
    payload_mode="simple_page",
    editor_version="2",
    default_menu={"header": [], "footer": []},
    menu_library=[],
    default_banners=[],
    cache_canon="example.cz",
    cache_geo="CZ",
    cache_language="cs",
    homepage_title="Example",
    internal_pages_count=1,
    domains_count=1,
    cache_domains=["example.cz"],
    main_domain_history=[],
    x_default_history=[],
    alternate_domain_history=[],
    cache_server_host="test.example",
    project_status="working",
    is_test_project=False,
    has_menu=True,
    cache_synced_at="2026-09-24T10:00:00Z",
    menu_capabilities_checked_at=None,
    header_menu_template_rendered=True,
    footer_menu_template_rendered=True,
    header_menu_rendered=True,
    footer_menu_rendered=True,
    header_menu_nested=True,
    footer_menu_nested=False,
)
caps = dict(
    checked_at=None,
    header_menu_template_rendered=True,
    footer_menu_template_rendered=True,
    header_menu_rendered=True,
    footer_menu_rendered=True,
    header_menu_nested=True,
    footer_menu_nested=False,
    check_status="completed",
)


def payload(title, text):
    return {"pages": [{"title": title, "description": text, "content": {"blocks": [{"type": "paragraph", "data": {"text": text}}]}}]}


item = dict(
    id="content1",
    task_id="task1",
    site_id="preview",
    section_id=None,
    topic="Casino guide",
    slug="/casino-guide/",
    status="generated",
    word_count=900,
    include_casino_rating=False,
    generated_json=payload("Latest", "Latest version"),
    generation_prompt_name="Default",
    generated_at="2026-09-24T10:00:00Z",
    generation_progress=100,
    generation_error=None,
    competitor_research_status="pending",
    competitor_research_progress=0,
    competitor_research_error=None,
    competitor_brief=None,
    published_at=None,
    published_url=None,
    indexing_task_id=None,
    indexing_status=None,
    indexing_error=None,
    deletion_requested_at=None,
    deletion_confirmed_at=None,
    deletion_error=None,
    last_publication_status_code=None,
    created_at="2026-09-24T09:00:00Z",
    updated_at="2026-09-24T10:00:00Z",
)
revisions = [
    dict(id="revision1", content_item_id="content1", requested_by_user_id="user", remarks="First", generate_title=True,
         status="completed", source_json=payload("Original", "Original"), revised_json=payload("First", "First result"),
         source_generated_at="2026-09-24T08:00:00Z", revised_generated_at="2026-09-24T08:30:00Z",
         error_message=None, created_at="2026-09-24T08:00:00Z", updated_at="2026-09-24T08:30:00Z"),
    dict(id="revision2", content_item_id="content1", requested_by_user_id="user", remarks="Second", generate_title=True,
         status="completed", source_json=payload("Before second", "Before second"), revised_json=payload("Preferred", "Preferred result"),
         source_generated_at="2026-09-24T09:00:00Z", revised_generated_at="2026-09-24T09:30:00Z",
         error_message=None, created_at="2026-09-24T09:00:00Z", updated_at="2026-09-24T09:30:00Z"),
]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ.get("CHROME"), headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    sent = []
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def route(request_route):
        path = request_route.request.url.split("/api")[-1].split("?")[0]
        method = request_route.request.method
        data = []
        if path == "/auth/me":
            data = dict(id="user", username="user", is_admin=False, is_active=True)
        elif path == "/sites/lookup":
            data = site
        elif path == "/sites":
            data = [site]
        elif path == "/sites/preview/content":
            data = [item]
        elif path == "/content/content1/revisions":
            data = revisions
        elif path == "/content/content1" and method == "GET":
            data = item
        elif path == "/content/content1/revise":
            sent.append(request_route.request.post_data_json)
            data = {**item, "status": "generation_queued", "generation_progress": 1}
        elif path.endswith("/menu-capabilities"):
            data = caps
        elif path.endswith("/overview"):
            data = dict(site=site, stats={}, recent_content=[])
        elif "favorite-sites" in path:
            data = {"site_ids": []}
        request_route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

    page.route("**/api/**", route)
    base = os.environ.get("VITE_TEST_URL", "http://127.0.0.1:5174")
    page.goto(base)
    page.evaluate('localStorage.setItem("admin_token", "mock"); sessionStorage.setItem("popup_permission_prompt_closed", "true")')
    page.goto(base + "/project-content/example.cz/")
    page.get_by_role("navigation", name="Разделы публикации").get_by_role("button").filter(has_text="Контент").click()
    page.get_by_role("button", name="Предпросмотр", exact=True).click()
    groups = page.locator(".revisionVersionGroup")
    groups.nth(1).get_by_role("button", name="После", exact=True).click()
    expect(page.get_by_text("Основа новой доработки:", exact=False)).to_contain_text("После доработки №2")
    page.get_by_label("Замечания к доработке").fill("Keep this version and improve its introduction")
    page.get_by_role("button", name="Отправить на доработку", exact=True).click()
    page.wait_for_timeout(200)

    assert sent == [{
        "remarks": "Keep this version and improve its introduction",
        "generate_title": True,
        "source_revision_id": "revision2",
        "source_revision_side": "revised",
    }], sent
    assert not errors, errors
    browser.close()

print("PASS: selected historical version is sent as the source of the next revision")
