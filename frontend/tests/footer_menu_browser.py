"""A footer is missing only when actual menu items exist and do not render."""
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

DIST = Path(os.environ.get("PAGEPILOT_DIST", Path(__file__).resolve().parents[1] / "dist"))
site = dict(id="footer", name="footer.test", brand="Vox", base_url="https://footer.test", publication_endpoint="",
    payload_mode="simple_page", editor_version="2", default_menu={"header": [], "footer": []}, menu_library=[],
    default_banners=[], cache_canon="footer.test", cache_geo="DE", cache_language="de", cache_domains=["footer.test"],
    project_status="working", is_test_project=False, has_menu=True, domains_count=1, internal_pages_count=0)
caps = dict(check_status="completed", header_menu_rendered=True, header_menu_template_rendered=True,
    header_menu_nested=False, footer_menu_rendered=False, footer_menu_template_rendered=False, footer_menu_nested=False)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"), headless=True)
    page = browser.new_page(viewport={"width": 1700, "height": 1100})
    errors = []
    network_reads = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.add_init_script('localStorage.setItem("admin_token","mock");sessionStorage.setItem("popup_permission_prompt_closed","true")')
    def route(r):
        path = urlparse(r.request.url).path
        if not path.startswith("/api/"):
            asset = DIST / path.lstrip("/")
            if not asset.is_file(): asset = DIST / "index.html"
            r.fulfill(content_type=mimetypes.guess_type(str(asset))[0] or "application/octet-stream", body=asset.read_bytes()); return
        path = path[4:]; data = []
        if path == "/auth/me": data = dict(id="test", username="test", is_admin=True, is_active=True)
        elif path in ["/sites", "/sites/cache/projects"]: data = [site]
        elif path == "/sites/lookup": data = site
        elif path.endswith("/sections"):
            data = [dict(id=status, site_id="footer", external_id=status, name=status, path=f"/{status}/", menu_type="header", parent_id=None, sync_status=status, updated_at="2026-10-21T10:00:00Z") for status in ["synced", "pending", "external_deleted"]]
        elif path == "/me/favorite-sites": data = {"site_ids": []}
        elif "/menu-capabilities" in path: data = caps
        elif path.endswith("/network"):
            network_reads.append(path)
            data = {"canon": "footer.test", "domains": ["footer.test"], "operations": [], "revision": "mock", "main_history": [], "alternate_history": [], "x_default_history": [], "alternates": [], "reserve": ""}
        r.fulfill(content_type="application/json", body=json.dumps(data))
    page.route("**/*", route)
    page.goto("http://localhost/project-network/footer.test/")
    footer = page.locator(".projectMenuCapability").filter(has=page.locator("small", has_text="Footer"))
    expect(footer).to_contain_text("Нет пунктов меню")
    expect(footer.locator(".menuReadyMedal.isGray")).to_have_count(1)
    assert "isEmpty" in footer.get_attribute("class") and "isMissing" not in footer.get_attribute("class")
    assert "не отображается" not in footer.get_attribute("title")
    page.clock.install()
    before = len(network_reads)
    page.clock.fast_forward(61000)
    page.evaluate('window.dispatchEvent(new Event("focus"))')
    page.wait_for_timeout(150)
    assert len(network_reads) == before, network_reads
    page.get_by_role('button', name='Обновить данные', exact=True).click()
    expect(page.get_by_role('button', name='Обновить данные', exact=True)).to_be_enabled()
    assert len(network_reads) == before + 1
    site["default_menu"]["footer"] = [{"id": "terms", "title": "Terms", "slug": "/terms/"}]
    page.reload()
    expect(footer).to_contain_text("Меню не реализовано")
    expect(footer.locator(".menuReadyMedal.isRed")).to_have_count(1)
    assert "isMissing" in footer.get_attribute("class")
    caps["footer_menu_rendered"] = caps["footer_menu_template_rendered"] = True
    page.reload()
    expect(footer).to_contain_text("Меню реализовано")
    assert "isReady" in footer.get_attribute("class")
    expect(footer.locator(".menuReadyMedal.isRed")).to_have_count(0)
    page.locator('.workspaceTabs').get_by_role('link', name='Меню', exact=False).click()
    table = page.locator('.pendingMenuChangesTable')
    synced = table.locator('tr').filter(has=page.get_by_text('synced', exact=True))
    pending = table.locator('tr').filter(has=page.get_by_text('pending', exact=True))
    expect(synced.get_by_role('button', name='Отправить', exact=True)).to_have_count(0)
    expect(synced.get_by_role('button', name='Изменить', exact=True)).to_be_visible()
    expect(pending.get_by_role('button', name='Отправить', exact=True)).to_be_visible()
    expect(page.get_by_text('Библиотека пунктов меню', exact=False)).to_have_count(0)
    page.get_by_role('button', name='Загрузить HTML', exact=True).click()
    expect(page.get_by_role('heading', name='Сохранить HTML конкурентов', exact=True)).to_be_visible()
    expect(page.get_by_role('combobox', name='Бренд', exact=True)).to_have_value('Vox')
    expect(page.get_by_role('combobox', name='ГЕО', exact=True)).to_have_value('🇩🇪 DE — Германия')
    page.get_by_role('button', name='Назад', exact=True).click()
    expect(table).to_be_visible()
    assert not errors, errors
    browser.close()
print("PASS: footer states; no idle refresh; manual refresh; no send for synced menu; no menu library; upload with project context and back")
