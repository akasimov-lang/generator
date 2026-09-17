import json
import os
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get("CHROME"), headless=True)
    for admin in [False, True]:
        page = browser.new_page(viewport={"width": 540, "height": 850})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        def route(r):
            path = r.request.url.split("/api")[-1].split("?")[0]
            data = {"id": "user", "username": "user", "is_admin": admin, "is_active": True} if path == "/auth/me" else []
            r.fulfill(status=200, content_type="application/json", body=json.dumps(data))
        page.route("**/api/**", route)
        base = os.environ.get("VITE_TEST_URL", "http://127.0.0.1:5174")
        page.goto(base)
        page.evaluate('localStorage.setItem("admin_token","mock"); sessionStorage.setItem("popup_permission_prompt_closed","true")')
        page.goto(base + "/guide")
        nav = page.get_by_role("navigation", name="Основное меню")
        toggle = page.locator(".mobileMenuToggle")
        expect(toggle).to_be_visible()
        expect(nav).to_be_hidden()
        expect(page.locator(".topbar .topbarActions")).to_have_count(0)
        expect(page.get_by_title("Выйти", exact=True)).to_be_hidden()
        expect(toggle).to_have_attribute("aria-expanded", "false")
        toggle.click()
        expect(nav).to_be_visible()
        expect(page.locator(".mobileAccountActions .userPill")).to_contain_text("user")
        expect(page.get_by_title("Выйти", exact=True)).to_be_visible()
        old_theme = page.locator("html").get_attribute("data-theme")
        page.locator(".mobileAccountActions button[title^='Включить']").click()
        assert page.locator("html").get_attribute("data-theme") != old_theme
        page.keyboard.press("Escape")
        expect(nav).to_be_hidden()
        expect(toggle).to_be_focused()
        toggle.press("Enter")
        nav.get_by_role("link", name="Настройки", exact=True).click()
        expect(nav).to_be_hidden()
        expect(page).to_have_url(base + "/settings")
        page.reload()
        expect(nav).to_be_hidden()
        page.set_viewport_size({"width": 1440, "height": 1000})
        expect(nav).to_be_visible()
        expect(toggle).to_be_hidden()
        expect(page.locator(".topbar .topbarActions")).to_be_visible()
        expect(page.locator(".mobileAccountActions")).to_have_count(0)
        for width in [900, 540, 390, 320]:
            page.set_viewport_size({"width": width, "height": 850})
            expect(nav).to_be_hidden()
            assert page.locator('.sidebar').bounding_box()['height'] <= 60
            expect(page.locator('.sidebarDigitalRain')).to_be_hidden()
            toggle.click()
            expect(nav).to_be_visible()
            assert toggle.bounding_box()["x"] + toggle.bounding_box()["width"] <= width
            toggle.click()
        toggle.click()
        if admin:
            page.get_by_role("button", name="Посмотреть как пользователь", exact=True).click()
            expect(nav).to_be_hidden()
            toggle.click()
            page.get_by_role("button", name="Режим администратора", exact=True).click()
            expect(nav).to_be_hidden()
            toggle.click()
        page.locator(".mobileAccountActions").get_by_role("button", name="Обновить", exact=True).click()
        expect(nav).to_be_hidden()
        toggle.click()
        page.get_by_title("Выйти", exact=True).click()
        expect(page.locator(".loginBrandRow")).to_be_visible()
        assert page.evaluate('localStorage.getItem("admin_token")') is None
        assert not errors, errors
        page.close()
    browser.close()
print("PASS mobile/desktop, both roles, keyboard/Escape, navigation closes menu, reload and resizing")
