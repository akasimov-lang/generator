"""Guide index, shareable routes, browser history and read-only access."""
import json
import os
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get("CHROME"), headless=True)
    for admin in [True, False]:
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        errors, calls = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        def route(r):
            path = r.request.url.split("/api")[-1].split("?")[0]
            calls.append((r.request.method, path))
            data = {"id": "reader", "username": "reader", "is_admin": admin, "is_active": True} if path == "/auth/me" else []
            r.fulfill(status=200, content_type="application/json", body=json.dumps(data))
        context.route("**/api/**", route)
        base = os.environ.get("VITE_TEST_URL", "http://127.0.0.1:5174")
        page.goto(base)
        page.evaluate('localStorage.setItem("admin_token","mock"); sessionStorage.setItem("popup_permission_prompt_closed","true")')
        page.goto(base + "/guide")
        expect(page.get_by_role("heading", name="Как работать с PagePilot")).to_be_visible()
        expect(page.locator(".sidebar .nav a").last).to_have_text("Инструкции")
        links = page.locator(".guideTopicList a")
        assert links.count() == 11
        targets = links.evaluate_all("(links) => links.map(a => a.getAttribute('href'))")
        for target in targets:
            page.locator(f'.guideTopicList a[href="{target}"]').click()
            expect(page).to_have_url(base + target)
            if target == "/auto-reglue/guide":
                expect(page.get_by_role("heading", name="1. Подготовьте проект")).to_be_visible()
            else:
                expect(page.locator(".guideArticle")).to_be_visible()
            page.reload()
            expect(page).to_have_url(base + target)
            page.get_by_role("link", name="Все инструкции", exact=True).click()
            expect(page.get_by_role("heading", name="Как работать с PagePilot")).to_be_visible()
        page.get_by_role("link", name="Открыть базовую инструкцию").click()
        page.go_back()
        expect(page).to_have_url(base + "/guide")
        page.go_forward()
        expect(page).to_have_url(base + "/guide/start")
        page.set_viewport_size({"width": 390, "height": 844})
        expect(page.locator(".guideArticle")).to_be_visible()
        bounds = page.locator(".guideHub").bounding_box()
        assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= 391
        assert all(method == "GET" and path == "/auth/me" for method, path in calls), calls
        assert not errors, errors
        context.close()
    browser.close()
print("PASS: 11 guide links, direct URLs/reload/history, both roles, mobile, no project reads or mutations")
