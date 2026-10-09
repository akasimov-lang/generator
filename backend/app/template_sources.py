"""Public-page snapshots. Browser HTML never masquerades as Google's rendering."""
import asyncio
from datetime import datetime, timezone
from html.parser import HTMLParser
import os
import re
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

MAX_HTML = 2_000_000


class BrowserProfile(BaseModel):
    user_agent: str = Field(default="", max_length=500)
    locale: str = Field(default="ru-RU", pattern=r"^[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8})*$")
    timezone: str = Field(default="UTC", max_length=80)
    width: int = Field(default=1440, ge=320, le=3840)
    height: int = Field(default=1000, ge=320, le=2160)
    device_scale_factor: float = Field(default=1, ge=1, le=4)
    color_scheme: str = Field(default="light", pattern=r"^(light|dark)$")

    @field_validator("user_agent")
    @classmethod
    def no_control_chars(cls, value):
        if any(ord(c) < 32 for c in value):
            raise ValueError("Некорректный User-Agent")
        return value


def host(url):
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


async def capture_google(url, profile):
    """Use the public Rich Results UI, with bounded waits and no CAPTCHA bypass."""
    from playwright.async_api import async_playwright
    from app.factual_research import require_public_url
    await require_public_url(url)
    meta = {"status": "needs_google_html", "source": "google_rich_results",
            "requested_url": url, "captured_at": datetime.now(timezone.utc).isoformat()}
    async with async_playwright() as p:
        options = {"headless": True}
        chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(chrome): options["executable_path"] = chrome
        browser = await p.chromium.launch(**options)
        try:
            context = await browser.new_context(user_agent=profile.user_agent or None,
                locale=profile.locale, timezone_id=profile.timezone,
                viewport={"width": profile.width, "height": profile.height},
                device_scale_factor=profile.device_scale_factor, color_scheme=profile.color_scheme,
                service_workers="block", accept_downloads=False)
            # Only Google serves the testing UI. Competitor code is never executed here.
            async def google_only(route):
                domain = host(route.request.url)
                if any(domain == allowed or domain.endswith("." + allowed) for allowed in
                       ("google.com", "gstatic.com", "googleusercontent.com", "googleapis.com", "recaptcha.net")):
                    await route.continue_()
                else:
                    await route.abort()
            await context.route("**/*", google_only)
            await context.add_init_script("""window.__pagepilotCopied = '';
                try { Object.defineProperty(navigator, 'clipboard', {value: {writeText: async t => {window.__pagepilotCopied = t;}}}); } catch(e) {}
                document.addEventListener('copy', e => {setTimeout(() => {const t=e.clipboardData?.getData('text/plain'); if(t)window.__pagepilotCopied=t;},0);}, true);""")
            page = await context.new_page()
            await page.goto("https://search.google.com/test/rich-results?hl=ru", wait_until="domcontentloaded", timeout=30000)
            await page.get_by_label("Введите URL", exact=True).fill(url, timeout=10000)
            await page.get_by_role("button", name="Проверить страницу", exact=True).click()
            for _ in range(60):
                body = await page.locator("body").inner_text()
                if re.search(r"Войдите в аккаунт|Sign in.*try again", body, re.I):
                    meta.update(status="auth_required", error="Google требует вход в аккаунт. Используйте ручной импорт HTML.")
                    return {"google_html": "", "capture": meta}
                challenge = page.locator('iframe[src*="recaptcha"][title*="challenge"], iframe[title*="проверка reCAPTCHA"]')
                if "/sorry/" in page.url or await challenge.count() and await challenge.first.is_visible() or re.search(r"не робот|unusual traffic|подозрительный трафик", body, re.I):
                    meta.update(status="blocked", error="Google запросил CAPTCHA. Скопируйте HTML из Rich Results Test вручную.")
                    return {"google_html": "", "capture": meta}
                tested = page.get_by_text(re.compile(r"Просмотреть проверенную страницу|View tested page", re.I))
                if await tested.count() and await tested.first.is_visible():
                    await tested.first.click(); break
                if re.search(r"URL недоступен|Не удалось проверить URL|URL is not available|Невозможно получить", body, re.I):
                    raise ValueError("Google не смог проверить страницу конкурента")
                await page.wait_for_timeout(1500)
            else:
                raise ValueError("Google не завершил проверку за отведённое время")
            await page.wait_for_timeout(700)
            # CodeMirror stores the complete document even when the visible code is virtualized.
            values = await page.evaluate("""() => {
                const out=[];
                for (const el of document.querySelectorAll('.CodeMirror')) if(el.CodeMirror)out.push(el.CodeMirror.getValue());
                for (const el of document.querySelectorAll('.cm-editor')) {const v=el.cmView?.view; if(v)out.push(v.state.doc.toString());}
                if(window.monaco?.editor)for(const m of window.monaco.editor.getModels())out.push(m.getValue());
                for(const el of document.querySelectorAll('textarea,pre'))out.push(el.value||el.textContent||'');
                return out;
            }""")
            copies = page.get_by_role("button", name=re.compile(r"копировать|copy", re.I))
            for index in range(min(await copies.count(), 6)):
                if await copies.nth(index).is_visible():
                    await copies.nth(index).click(); await page.wait_for_timeout(100)
                    values.append(await page.evaluate("window.__pagepilotCopied"))
            candidates = [v for v in values if isinstance(v, str) and re.search(r"<(?:!doctype|html|head|body)\b", v, re.I)]
            if not candidates:
                raise ValueError("Не удалось извлечь полный HTML из интерфейса Google. Доступен ручной импорт.")
            html = max(candidates, key=len)
            excerpt(html)
            meta.update(status="google_ready", result_url=page.url)
            return {"google_html": html, "capture": meta}
        finally:
            await browser.close()


def excerpt(html):
    from app.services import CompetitorHTMLExtractor
    if not html or len(html.encode("utf-8")) > MAX_HTML:
        raise ValueError("HTML пуст или превышает 2 МБ. Сохраните полный HTML страницы меньшего размера.")
    if not re.search(r"<(?:html|body|head)\b", html, re.I):
        raise ValueError("Нужен HTML страницы, а не ссылка или текст отчёта Google.")
    class ReadableHTML(CompetitorHTMLExtractor):
        def __init__(self):
            super().__init__()
            self.visible = []
        def handle_data(self, data):
            if not self._ignore_depth:
                self.visible.append(data)
            super().handle_data(data)
    parser = ReadableHTML(); parser.feed(html)
    result = parser.payload()
    text = result.get("text_content", "")
    if not text:
        text = " ".join(" ".join(parser.visible).split())
    if len(text.strip()) < 150:
        raise ValueError("В HTML недостаточно текста сайта. Проверьте, что скопирована вкладка HTML проверенной страницы.")
    title = result.get("title", "")
    if re.search(r"just a moment|attention required|verify you are human|проверка расширенных результатов|rich results test|access denied", title, re.I):
        raise ValueError("Получена заглушка или страница проверки, а не сайт конкурента.")
    return {"title": title, "excerpt": text[:12000], "excerpt_truncated": len(text) > 12000}


async def capture_page(url, profile):
    """Observe the original origin; never follow an affiliate/other-domain navigation."""
    from playwright.async_api import async_playwright
    from app.factual_research import require_public_url
    await require_public_url(url)
    meta = {"status": "browser_only", "captured_at": datetime.now(timezone.utc).isoformat(),
            "requested_url": url, "redirects": [], "note": "Вспомогательный снимок Chromium, не HTML Google."}
    raw, rendered = "", ""
    async with async_playwright() as p:
        options = {"headless": True}
        chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(chrome): options["executable_path"] = chrome
        browser = await p.chromium.launch(**options)
        tasks = []
        try:
            context = await browser.new_context(
                user_agent=profile.user_agent or None, locale=profile.locale,
                timezone_id=profile.timezone, viewport={"width": profile.width, "height": profile.height},
                device_scale_factor=profile.device_scale_factor, color_scheme=profile.color_scheme,
                service_workers="block", accept_downloads=False)
            await context.route_web_socket("**/*", lambda ws: ws.close())
            async def public_only(route):
                request = route.request
                try:
                    if request.is_navigation_request() and host(request.url) != host(url):
                        meta["redirects"].append(request.url)
                        meta["status"] = "redirected"
                        await route.abort(); return
                    if request.method not in {"GET", "HEAD"} or request.resource_type in {"media", "websocket"}:
                        await route.abort(); return
                    await require_public_url(request.url)
                    await route.continue_()
                except Exception:
                    await route.abort()
            await context.route("**/*", public_only)
            page = await context.new_page()
            async def response_html(response):
                nonlocal raw
                if response.request.resource_type == "document" and host(response.url) == host(url):
                    if response.request.redirected_from:
                        meta["redirects"].append(response.url)
                    if 200 <= response.status < 300 and "html" in response.headers.get("content-type", "") and not raw:
                        body = await response.body()
                        if len(body) <= MAX_HTML:
                            raw = body.decode("utf-8", errors="replace")
                        else:
                            meta["error"] = "Исходный HTML превышает 2 МБ"
            page.on("response", lambda response: tasks.append(asyncio.create_task(response_html(response))))
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                await page.wait_for_timeout(1800)
            except Exception:
                meta.setdefault("error", "Страница недоступна, перенаправлена или истекло время ожидания")
            if host(page.url) == host(url):
                rendered = await page.content()
                if len(rendered.encode("utf-8")) > MAX_HTML:
                    rendered = ""; meta["error"] = "Отрисованный HTML превышает 2 МБ"
            meta["final_url"] = page.url
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            try:
                excerpt(rendered or raw)
            except ValueError as exc:
                meta["status"], meta["error"] = "needs_google_html", str(exc)
            return {"raw_html": raw, "rendered_html": rendered, "capture": meta}
        finally:
            for task in tasks:
                if not task.done(): task.cancel()
            await browser.close()
