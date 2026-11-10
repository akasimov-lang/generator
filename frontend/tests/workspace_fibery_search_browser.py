"""Run on the server against built assets, with all application API calls mocked."""
import json
import os
import sys
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

if sys.platform == "darwin":
    raise SystemExit("Run this browser check on the server, not on the user's Mac.")

base = os.environ["PAGEPILOT_BROWSER_URL"].rstrip("/")
site = dict(
    id="search-698", name="casino-portugalonline.com", fibery_name="#698_Общие ключи_PT",
    base_url="https://casino-portugalonline.com", cache_canon="casino-portugalonline.com",
    cache_domains=["old-portugal.test"], cache_geo="pt-PT", cache_language="pt",
    publication_endpoint="", payload_mode="simple_page", editor_version="2",
    default_menu={"header": [], "footer": []}, menu_library=[], default_banners=[],
    internal_pages_count=0, domains_count=2, project_status="mass_actions",
    is_test_project=False, has_menu=False,
)
sites = [site, dict(site, id="other", name="other.test", base_url="https://other.test",
                   cache_canon="other.test", cache_domains=[], fibery_name=None)]

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    errors, writes = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')

    def api(route):
        path = urlparse(route.request.url).path[4:]
        if route.request.method != "GET":
            writes.append(path)
        data = []
        if path == "/auth/me":
            data = dict(id="test", username="test", is_admin=True, is_active=True)
        elif path in ("/sites", "/sites/cache/projects"):
            data = sites
        elif path == "/sites/lookup":
            data = site
        elif "favorite-sites" in path:
            data = {"site_ids": []}
        elif path.endswith("/overview"):
            data = {"site": site, "stats": {}, "recent_content": []}
        elif path.endswith("/menu-capabilities"):
            data = {"check_status": "completed"}
        route.fulfill(content_type="application/json", body=json.dumps(data))

    page.route("**/api/**", api)
    page.goto(base + "/project-overview/")
    search = page.get_by_role("searchbox", name="Поиск по всем сайтам", exact=True)
    results = page.locator("#workspace-domain-results")
    search.fill("698")
    expect(results.locator("tbody tr")).to_have_count(1)
    expect(results).to_contain_text(site["name"])
    expect(results.locator("a.fiberyProjectLink")).to_have_attribute(
        "href", "https://hzhz.fibery.io/favorites/Alfasearch_Config/SEO_Projects/698")
    search.fill("#698")
    expect(results.locator("tbody tr")).to_have_count(1)
    search.fill("ОБЩИЕ КЛЮЧИ")
    expect(results.locator("tbody tr")).to_have_count(1)
    search.fill("https://old-portugal.test/path/")
    expect(results).to_contain_text(site["name"])
    search.fill("missing-project")
    expect(results).to_contain_text("Проекты не найдены")
    search.fill("698")
    results.get_by_role("button", name=site["name"], exact=True).click()
    expect(search).to_have_value("")
    expect(page.locator(".projectPicker .searchableSelectControl")).to_contain_text(site["name"])

    picker = page.locator(".projectPicker .searchableSelectControl")
    picker.click()
    expect(page.get_by_role("option")).to_have_count(2)
    dropdown = page.get_by_role("textbox", name="Найти проект", exact=True)
    dropdown.fill("698")
    expect(page.get_by_role("option")).to_have_count(1)
    dropdown.press("Enter")
    expect(picker).to_contain_text(site["name"])
    picker.click()
    expect(page.get_by_role("option")).to_have_count(2)
    dropdown.fill("ОБЩИЕ КЛЮЧИ")
    expect(page.get_by_role("option")).to_have_count(1)
    dropdown.press("Escape")
    expect(picker).to_contain_text(site["name"])

    page.set_viewport_size({"width": 390, "height": 844})
    search.fill("698")
    expect(search).to_be_visible()
    expect(results).to_contain_text(site["fibery_name"])
    page.get_by_role("button", name="Очистить поиск по всем сайтам", exact=True).click()
    expect(search).to_have_value("")
    search.fill("698")
    search.press("Escape")
    expect(search).to_have_value("")
    assert not errors, errors
    assert not writes, writes
    browser.close()

print("PASS: workspace Fibery number/name, domain aliases, result navigation, project selector, keyboard, clearing and mobile search; no API writes")
