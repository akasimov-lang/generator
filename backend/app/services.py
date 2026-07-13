import asyncio
import copy
import html
import json
import re
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from slugify import slugify
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.schemas import GenerationTaskCreate, PublicationCampaignCreate

SIMPLE_PAGE = "simple_page"
FULL_SITE = "full_site"
SITE_DEFAULT = "site_default"
DEFAULT_EDITOR_VERSION = "2.31.0"
GEMINI_DEFAULT_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_CONTENT_PROMPT_TEMPLATE = """Ты — senior SEO-редактор и content strategist для gambling/betting тем.

Задача: сгенерировать SEO-страницу на немецком языке для сайта-обзорника онлайн-казино, ставок и casino providers.

Важно:
У тебя нет доступа к Google, браузингу и актуальной выдаче.
Не утверждай, что ты изучил TOP-10, конкурентов или реальные сайты.
Content gaps формируй как гипотезу на основе темы, поискового интента и типичных слабых мест страниц в нише gambling/betting.
Не выдумывай факты.

Гео: Германия.
Язык страницы: немецкий.
Текущий год: {{CURRENT_YEAR}}.
Тематика: онлайн-казино, легальные Anbieter, GGL-Lizenz, Spielerschutz, Zahlungen, Auszahlungen, KYC, sichere Online Casinos.
Аудитория: пользователи из Германии, которые хотят выбрать легальное и безопасное онлайн-казино или Spielothek.

Тема страницы:
{{TOPIC}}

Slug страницы:
{{SLUG}}

Примеры тем:
1. Beste Online Casinos in Deutschland 2026: Legale Anbieter im Vergleich
2. Legale Online Casinos in Deutschland: Anbieter mit GGL-Lizenz
3. Beste Online Spielotheken in Deutschland: Sichere Slots mit Lizenz
4. Sichere Online Casinos erkennen: Lizenz, Zahlungen und Spielerschutz
5. Neue Online Casinos in Deutschland: Neue Anbieter mit Lizenz

Цель страницы:
Создать полезный, структурированный и юридически аккуратный контент, который максимально полно отвечает на запрос пользователя без копирования конкурентов и без неподтвержденных утверждений.

Работай как редактор, который отвечает за публикацию.

Основные правила:
- Пиши на немецком языке.
- Не используй русский или английский в тексте страницы, кроме терминов вроде KYC, RTP, FAQ, GGL.
- Не выдумывай названия казино, операторов, лицензий, бонусов, сумм, RTP, сроков выплат, комиссий, рейтингов или отзывов.
- Если данных нет, используй безопасную формулировку или пометку: [Muss geprüft werden: ...].
- Не обещай выигрыш.
- Не называй казино “абсолютно безопасными”.
- Не используй формулировки “garantiert”, “ohne Risiko”, “100% legal”, “sicherer Gewinn”.
- Не делай рекламный текст.
- Не делай keyword stuffing.
- Не повторяй главный ключ слишком часто.
- Не создавай фейковый опыт автора.
- Не создавай фейковый рейтинг без данных.
- Не делай одинаковые FAQ и одинаковые вводки.

SEO-логика:
Сначала определи:
1. Главный интент пользователя.
2. 8–12 подинтентов.
3. Главный ключ.
4. Вторичные ключи.
5. FAQ-запросы.
6. Legal/Safety/Payment кластеры.
7. Гипотетические content gaps, которые часто бывают у конкурентов.

Для тем про Германию обязательно раскрыть:
- Was bedeutet GGL-Lizenz?
- Warum ist Lizenzprüfung wichtig?
- Wie erkennt man sichere Anbieter?
- Welche Rolle spielen KYC und Identitätsprüfung?
- Was muss man vor Einzahlung prüfen?
- Unterschied zwischen Einzahlung und Auszahlung.
- Spielerschutz, Limits und Selbstausschluss.
- Für wen sind Online Casinos nicht geeignet?
- Welche Warnsignale sollte man beachten?

Структура страницы:
Верни готовую страницу в таком формате:

Title:
Meta Description:
H1:

Intro:
1–2 коротких абзаца. Сразу отвечай на основной запрос, без длинного вступления.

Quick Answer:
Короткий практический ответ пользователю в 3–5 предложениях.

H2: ...
Текст 2–4 абзаца.

Если нужна таблица, добавь ее в markdown-формате:
| Kriterium | Worauf achten | Warum wichtig |
|---|---|---|

После таблицы обязательно добавь 1 короткий поясняющий абзац.

Обязательные блоки для страниц про онлайн-казино в Германии:
1. Überblick / schneller Vergleich.
2. Methodik: Wie wir Anbieter bewerten.
3. GGL-Lizenz und rechtlicher Rahmen.
4. Sicherheit: Lizenz, Zahlungen, Datenschutz, KYC.
5. Zahlungen und Auszahlungen.
6. Spielerschutz und Limits.
7. Für wen geeignet / nicht geeignet.
8. Häufige Fehler vor der Registrierung.
9. FAQ.
10. Responsible Gambling Hinweis.

Для рейтинговых страниц:
Если нет проверенного списка брендов, не создавай фейковый TOP-10.
Вместо этого создай таблицу критериев выбора и пометь места, где нужны реальные Anbieter:
[Anbieter 1 – muss geprüft werden]
[Anbieter 2 – muss geprüft werden]
[Anbieter 3 – muss geprüft werden]

FAQ:
Сгенерируй 8–10 вопросов.
Ответы должны быть короткими, конкретными и не рекламными.

Responsible Gambling:
Добавь аккуратный блок на немецком:
- Glücksspiel ist mit Risiken verbunden.
- Nur mit Geld spielen, dessen Verlust verkraftbar ist.
- Limits nutzen.
- Bei Kontrollverlust Hilfe suchen.
- Для организаций помощи используй пометку: [Muss geprüft werden: lokale Hilfsangebote in Deutschland].

Финальная редакторская проверка:
В конце добавь короткий блок:

Editor Check:
- Suchintention: OK / Risiko
- Fakten: OK / Muss geprüft werden
- Legal-Risiko: OK / Risiko
- Keyword-Stuffing: OK / Risiko
- E-E-A-T: OK / Muss gestärkt werden
- Thin Content: OK / Risiko
- Nächste Prüfung vor Veröffentlichung: ...

Не добавляй вымышленные ссылки.
Не добавляй вымышленные даты обновления.
Не утверждай, что страница лучше конкурентов, если конкуренты не проверены.
"""


def now_payload_time() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def make_block_id() -> str:
    return uuid.uuid4().hex[:10]


def normalize_slug(topic: str) -> str:
    slug = slugify(topic) or uuid.uuid4().hex[:8]
    return f"/{slug}/"


def clean_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def count_words(payload: dict) -> int:
    if "pages" in payload:
        chunks: list[str] = []
        for page in payload.get("pages", []):
            page_content = page.get("content", {}) if isinstance(page, dict) else {}
            for block in page_content.get("blocks", []):
                chunks.extend(extract_block_text(block))
        return len(re.findall(r"\b[\w'-]+\b", clean_text(" ".join(chunks)), flags=re.UNICODE))

    content = payload.get("content", {})
    chunks: list[str] = []
    chunks.append(str(content.get("intro", "")))
    for section in content.get("sections", []):
        chunks.append(str(section.get("body", "")))
    for faq in content.get("faq", []):
        chunks.append(str(faq.get("answer", "")))
    return len(re.findall(r"\b[\w'-]+\b", clean_text(" ".join(chunks)), flags=re.UNICODE))


def extract_block_text(block: dict) -> list[str]:
    data = block.get("data")
    block_type = block.get("type")
    if block_type in {"header", "paragraph"} and isinstance(data, dict):
        return [data.get("text", "")]
    if block_type == "list" and isinstance(data, dict):
        return [str(item) for item in data.get("items", [])]
    if block_type == "table" and isinstance(data, dict):
        return [str(cell) for row in data.get("content", []) for cell in row]
    if block_type == "faq" and isinstance(data, list):
        return [str(item.get("answer", "")) for item in data if isinstance(item, dict)]
    if block_type == "quote" and isinstance(data, dict):
        return [data.get("quote", "")]
    if block_type == "plusMinus" and isinstance(data, dict):
        values = []
        for item in data.get("values", []):
            values.extend([item.get("plus", ""), item.get("minus", "")])
        return values
    return []


def build_stub_content(
    topic: str,
    geo: str,
    language: str,
    target_words: int | None = None,
    site: models.Site | None = None,
    payload_mode: str = SITE_DEFAULT,
    shortcode: str | None = None,
    include_toc: bool = True,
    include_faq: bool = True,
) -> dict:
    resolved_mode = resolve_payload_mode(site, payload_mode)
    page = build_editor_page(
        topic=topic,
        geo=geo,
        language=language,
        target_words=target_words,
        site=site,
        shortcode=shortcode,
        include_toc=include_toc,
        include_faq=include_faq,
    )
    menu = copy.deepcopy(site.default_menu) if site and site.default_menu else {"header": [], "footer": []}
    payload = {
        "menu": menu,
        "pages": [page],
        "generation_meta": {
            "geo": geo,
            "language": language,
            "target_words": target_words,
            "payload_mode": resolved_mode,
            "generator": "stub_editorjs",
        },
    }
    if resolved_mode == FULL_SITE and site and site.showcase_payload:
        payload["casinos"] = site.showcase_payload.get("casinos", site.showcase_payload)
    return payload


async def build_ai_content(
    provider: models.AiProvider,
    topic: str,
    geo: str,
    language: str,
    target_words: int | None = None,
    site: models.Site | None = None,
    payload_mode: str = SITE_DEFAULT,
    prompt_template: str | None = None,
    shortcode: str | None = None,
    include_toc: bool = True,
    include_faq: bool = True,
) -> dict:
    if provider.provider_type == "gemini":
        return await build_gemini_content(
            provider=provider,
            topic=topic,
            geo=geo,
            language=language,
            target_words=target_words,
            site=site,
            payload_mode=payload_mode,
            prompt_template=prompt_template,
            shortcode=shortcode,
            include_toc=include_toc,
            include_faq=include_faq,
        )
    return build_stub_content(
        topic=topic,
        geo=geo,
        language=language,
        target_words=target_words,
        site=site,
        payload_mode=payload_mode,
        shortcode=shortcode,
        include_toc=include_toc,
        include_faq=include_faq,
    )


async def build_gemini_content(
    provider: models.AiProvider,
    topic: str,
    geo: str,
    language: str,
    target_words: int | None,
    site: models.Site | None,
    payload_mode: str,
    prompt_template: str | None,
    shortcode: str | None,
    include_toc: bool,
    include_faq: bool,
) -> dict:
    if not provider.api_key:
        raise ValueError("Gemini API key is not configured")

    base_payload = build_stub_content(
        topic=topic,
        geo=geo,
        language=language,
        target_words=target_words,
        site=site,
        payload_mode=payload_mode,
        shortcode=shortcode,
        include_toc=include_toc,
        include_faq=include_faq,
    )
    page = base_payload["pages"][0]
    prompt = build_gemini_prompt(
        topic=topic,
        geo=geo,
        language=language,
        target_words=target_words,
        site=site,
        prompt_template=prompt_template,
        shortcode=shortcode,
        include_toc=include_toc,
        include_faq=include_faq,
    )
    try:
        response = await call_gemini(provider, prompt)
    except Exception as exc:
        provider.validation_status = "invalid"
        provider.validation_message = describe_ai_provider_error(exc)
        provider.validated_at = datetime.now(timezone.utc)
        raise

    usage = response.get("usageMetadata", {}) if isinstance(response, dict) else {}
    apply_provider_usage(provider, usage)
    provider.validation_status = "valid"
    provider.validation_message = "Gemini API key is valid"
    provider.validated_at = datetime.now(timezone.utc)
    generated_text = extract_gemini_text(response)
    if not generated_text:
        raise ValueError("Gemini returned an empty response")

    page["content"]["blocks"] = build_blocks_from_ai_text(
        generated_text=generated_text,
        topic=topic,
        shortcode=shortcode,
        include_toc=include_toc,
        include_faq=include_faq,
    )
    page["description"] = clean_text(generated_text)[:155] or page["description"]
    base_payload["generation_meta"]["generator"] = "gemini"
    base_payload["generation_meta"]["model"] = provider.model
    base_payload["generation_meta"]["usage"] = usage
    return base_payload


def build_gemini_prompt(
    topic: str,
    geo: str,
    language: str,
    target_words: int | None,
    site: models.Site | None,
    prompt_template: str | None,
    shortcode: str | None,
    include_toc: bool,
    include_faq: bool,
) -> str:
    template = prompt_template.strip() if prompt_template and prompt_template.strip() else DEFAULT_CONTENT_PROMPT_TEMPLATE
    slug = normalize_slug(topic)
    values = {
        "topic": topic,
        "geo": geo,
        "country": geo,
        "language": language,
        "target_words": str(target_words or "not specified"),
        "site_name": site.name if site else "not specified",
        "site_base_url": site.base_url if site else "",
        "slug": slug,
        "current_year": str(datetime.now(timezone.utc).year),
        "shortcode": shortcode or "none",
        "include_toc": "yes" if include_toc else "no",
        "include_faq": "yes" if include_faq else "no",
    }
    prompt = template
    for key, value in values.items():
        prompt = prompt.replace("{{" + key + "}}", value)
        prompt = prompt.replace("{{" + key.upper() + "}}", value)
    prompt += (
        "\n\nGeneration constraints:\n"
        f"- Topic: {topic}\n"
        f"- Country/geo: {geo}\n"
        f"- Language: {language}\n"
        f"- Target words: {target_words or 'not specified'}\n"
        f"- Include TOC-related headings: {'yes' if include_toc else 'no'}\n"
        f"- Include FAQ: {'yes' if include_faq else 'no'}\n"
        f"- Shortcode block context: {shortcode or 'none'}\n"
        "- Return plain article text only. Do not return JSON or Markdown fences.\n"
    )
    return prompt

async def call_gemini(provider: models.AiProvider, prompt: str) -> dict:
    model = provider.model or GEMINI_DEFAULT_MODEL
    endpoint_template = provider.endpoint_url or GEMINI_DEFAULT_ENDPOINT
    endpoint = endpoint_template.format(model=model)
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": provider.api_key,
    }
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(endpoint, json=body, headers=headers)
    response.raise_for_status()
    return response.json()


def extract_gemini_text(response: dict) -> str:
    chunks: list[str] = []
    for candidate in response.get("candidates", []):
        content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
        for part in content.get("parts", []):
            if isinstance(part, dict) and part.get("text"):
                chunks.append(str(part["text"]))
    return clean_text("\n\n".join(chunks))


def apply_provider_usage(provider: models.AiProvider, usage: dict) -> None:
    prompt_tokens = int(usage.get("promptTokenCount") or 0)
    completion_tokens = int(usage.get("candidatesTokenCount") or 0)
    total_tokens = int(usage.get("totalTokenCount") or (prompt_tokens + completion_tokens))
    provider.prompt_tokens_used = (provider.prompt_tokens_used or 0) + prompt_tokens
    provider.completion_tokens_used = (provider.completion_tokens_used or 0) + completion_tokens
    provider.total_tokens_used = (provider.total_tokens_used or 0) + total_tokens
    provider.last_used_at = datetime.now(timezone.utc)


def ensure_default_prompt_template(db: Session, site: models.Site) -> models.PromptTemplate:
    existing = db.scalar(
        select(models.PromptTemplate)
        .where(models.PromptTemplate.site_id == site.id)
        .order_by(models.PromptTemplate.is_default.desc(), models.PromptTemplate.created_at.asc())
        .limit(1)
    )
    if existing:
        return existing

    prompt = models.PromptTemplate(
        site_id=site.id,
        name="Default DE gambling SEO prompt",
        content=DEFAULT_CONTENT_PROMPT_TEMPLATE,
        is_default=True,
    )
    db.add(prompt)
    db.flush()
    return prompt


async def validate_ai_provider_key(provider: models.AiProvider) -> models.AiProvider:
    provider.validated_at = datetime.now(timezone.utc)

    if provider.provider_type != "gemini":
        provider.validation_status = "unchecked"
        provider.validation_message = "Автопроверка сейчас доступна только для Gemini-провайдеров."
        return provider

    if not provider.api_key:
        provider.validation_status = "invalid"
        provider.validation_message = "API key is not configured"
        return provider

    try:
        response = await call_gemini(provider, "Reply with exactly: ok")
        usage = response.get("usageMetadata", {}) if isinstance(response, dict) else {}
        apply_provider_usage(provider, usage)
    except Exception as exc:
        provider.validation_status = "invalid"
        provider.validation_message = describe_ai_provider_error(exc)
        return provider

    provider.validation_status = "valid"
    provider.validation_message = "Gemini API key is valid"
    return provider


def describe_ai_provider_error(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        status_label = ""
        reason = ""
        message = ""
        try:
            payload = error.response.json()
        except ValueError:
            payload = {}

        if isinstance(payload, dict):
            error_payload = payload.get("error", payload)
            if isinstance(error_payload, dict):
                status_label = str(error_payload.get("status") or "")
                message = str(error_payload.get("message") or "")
                details = error_payload.get("details") or []
                if isinstance(details, list):
                    for detail in details:
                        if isinstance(detail, dict) and detail.get("reason"):
                            reason = str(detail["reason"])
                            break

        if not message:
            message = error.response.text[:300]

        parts = [f"HTTP {status_code}", status_label, reason, message]
        return ": ".join(part for part in parts if part)[:500]

    return str(error)[:500] or error.__class__.__name__


def build_blocks_from_ai_text(
    generated_text: str,
    topic: str,
    shortcode: str | None,
    include_toc: bool,
    include_faq: bool,
) -> list[dict]:
    title = topic.strip().title()
    lines = [line.strip(" #*\t") for line in generated_text.splitlines() if line.strip()]
    blocks: list[dict] = [header_block(title, 1)]
    headings: list[str] = [title]
    pending_paragraphs: list[str] = []

    def flush_paragraphs() -> None:
        if pending_paragraphs:
            blocks.append(paragraph_block(" ".join(pending_paragraphs)))
            pending_paragraphs.clear()

    for line in lines:
        if looks_like_heading(line):
            flush_paragraphs()
            headings.append(line)
            blocks.append(header_block(line, 2))
        else:
            pending_paragraphs.append(line)
            if len(" ".join(pending_paragraphs)) > 700:
                flush_paragraphs()
    flush_paragraphs()

    if include_toc and len(headings) > 1:
        blocks.insert(1, toc_block(headings[:8]))
    if include_faq and not any(block.get("type") == "faq" for block in blocks):
        blocks.append(
            faq_block(
                [
                    {
                        "question": f"What is {title} about?",
                        "answer": f"This page explains {topic} and gives practical context for readers.",
                    }
                ]
            )
        )
    if shortcode:
        blocks.append(shortcode_block(shortcode))
    return blocks


def looks_like_heading(line: str) -> bool:
    if len(line) > 90:
        return False
    if line.endswith("."):
        return False
    words = line.split()
    return 2 <= len(words) <= 10


def resolve_payload_mode(site: models.Site | None, requested_mode: str) -> str:
    if requested_mode in {SIMPLE_PAGE, FULL_SITE}:
        return requested_mode
    if site and site.payload_mode in {SIMPLE_PAGE, FULL_SITE}:
        return site.payload_mode
    return SIMPLE_PAGE


def build_editor_page(
    topic: str,
    geo: str,
    language: str,
    target_words: int | None,
    site: models.Site | None,
    shortcode: str | None,
    include_toc: bool,
    include_faq: bool,
) -> dict:
    title = topic.strip().title()
    slug = normalize_slug(topic)
    description = f"Useful guide about {topic} for {geo} readers in {language}."
    headings = [
        title,
        f"What to know about {title}",
        f"How to choose the right option in {geo}",
        "Key comparison points",
        "FAQ",
    ]
    blocks: list[dict] = [header_block(headings[0], 1)]
    if include_toc:
        blocks.append(toc_block(headings))
    blocks.extend(
        [
            paragraph_block(
                f"This page is a generated editorial draft for <strong>{html.escape(topic)}</strong>. "
                f"It is prepared for geo {html.escape(geo)} and language {html.escape(language)} and should be reviewed before publication."
            ),
            header_block(headings[1], 2),
            paragraph_block(
                f"The content explains the topic, gives practical context and keeps the structure compatible with the site's Editor.js renderer."
            ),
            header_block(headings[2], 2),
            list_block(
                "unordered",
                [
                    "Check the offer, limits and conditions before publishing.",
                    "Keep local geo and language details consistent across title, H1 and body.",
                    "Use shortcode blocks only when the target site already supports them.",
                ],
            ),
            header_block(headings[3], 2),
            table_block(
                [
                    ["Page topic", title],
                    ["Geo", geo],
                    ["Language", language],
                    ["Target words", str(target_words or "Not specified")],
                ]
            ),
        ]
    )
    if include_faq:
        blocks.extend(
            [
                header_block(headings[4], 2),
                faq_block(
                    [
                        {
                            "question": f"What is this page about?",
                            "answer": f"It is an editorial page about {topic}, prepared for {geo} and {language}.",
                        },
                        {
                            "question": "Can this content be published automatically?",
                            "answer": "It should be validated and approved in the admin panel before the publication worker sends it to the endpoint.",
                        },
                    ]
                ),
            ]
        )
    if shortcode:
        blocks.append(shortcode_block(shortcode))

    published = now_payload_time()
    editor_version = site.editor_version if site and site.editor_version else DEFAULT_EDITOR_VERSION
    banners = site.default_banners if site and site.default_banners is not None else []
    return {
        "id": uuid.uuid4().hex[:8],
        "slug": slug,
        "title": title,
        "publishedTime": published,
        "description": description,
        "updatedTime": published,
        "breadcrumb": title,
        "content": {
            "time": int(datetime.now(timezone.utc).timestamp() * 1000),
            "blocks": blocks,
            "version": editor_version,
        },
        "head": [breadcrumb_schema_block(slug, title)],
        "banners": banners,
    }


def header_block(text: str, level: int) -> dict:
    return {"id": make_block_id(), "type": "header", "data": {"text": text, "level": level}}


def paragraph_block(text: str) -> dict:
    return {"id": make_block_id(), "type": "paragraph", "data": {"text": text}}


def list_block(style: str, items: list[str]) -> dict:
    return {"id": make_block_id(), "type": "list", "data": {"style": style, "items": items}}


def table_block(rows: list[list[str]]) -> dict:
    return {"id": make_block_id(), "type": "table", "data": {"withHeadings": False, "stretched": False, "content": rows}}


def faq_block(items: list[dict]) -> dict:
    return {"id": make_block_id(), "type": "faq", "data": items}


def toc_block(headings: list[str]) -> dict:
    return {"id": make_block_id(), "type": "toc", "data": [{"heading": heading, "checked": True} for heading in headings]}


def shortcode_block(shortcode: str) -> dict:
    return {"id": make_block_id(), "type": "shortcode", "data": {"shortcode": shortcode}}


def breadcrumb_schema_block(slug: str, title: str) -> dict:
    data = {
        "@context": "http://www.schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "item": {"@type": "WebPage", "@id": "/", "name": "Startseite"}},
            {"@type": "ListItem", "position": 2, "item": {"@type": "WebPage", "@id": slug, "name": title}},
        ],
    }
    return {"type": "universal", "data": json.dumps(data, ensure_ascii=False, indent=2)}


def create_generation_task(db: Session, payload: GenerationTaskCreate) -> models.GenerationTask:
    clean_topics = [topic.strip() for topic in payload.topics if topic.strip()]
    task = models.GenerationTask(
        title=payload.title,
        site_id=payload.site_id,
        section_id=payload.section_id,
        ai_provider_id=payload.ai_provider_id,
        geo=payload.geo,
        language=payload.language,
        payload_mode=payload.payload_mode,
        topics_count=len(clean_topics),
        target_words=payload.target_words,
        prompt_template=payload.prompt_template,
        status="created",
    )
    db.add(task)
    db.flush()

    for index, topic in enumerate(clean_topics, start=1):
        site = db.get(models.Site, payload.site_id) if payload.site_id else None
        generated_json = build_stub_content(
            topic,
            payload.geo,
            payload.language,
            payload.target_words,
            site=site,
            payload_mode=payload.payload_mode,
            shortcode=payload.shortcode,
            include_toc=payload.include_toc,
            include_faq=payload.include_faq,
        )
        page = generated_json["pages"][0]
        item = models.ContentItem(
            task_id=task.id,
            site_id=task.site_id,
            topic=topic,
            slug=page["slug"],
            generated_json=generated_json,
            status="draft",
            word_count=count_words(generated_json),
            section_id=payload.section_id,
            idempotency_key=f"{payload.geo.lower()}-{payload.language.lower()}-{slugify(topic)}-{index}-{uuid.uuid4().hex[:8]}",
        )
        db.add(item)

    db.commit()
    db.refresh(task)
    return task


def generate_task_items(db: Session, task: models.GenerationTask) -> models.GenerationTask:
    task.status = "generating"
    db.flush()
    provider = db.get(models.AiProvider, task.ai_provider_id) if task.ai_provider_id else None
    site = db.get(models.Site, task.site_id) if task.site_id else None
    try:
        for item in task.items:
            if provider and provider.is_active:
                item.generated_json = asyncio.run(
                    build_ai_content(
                        provider=provider,
                        topic=item.topic,
                        geo=task.geo,
                        language=task.language,
                        target_words=task.target_words,
                        site=site,
                        payload_mode=task.payload_mode,
                        prompt_template=task.prompt_template,
                        shortcode=None,
                        include_toc=True,
                        include_faq=True,
                    )
                )
                item.slug = item.generated_json["pages"][0]["slug"]
                item.word_count = count_words(item.generated_json)
            item.status = "generated"
        task.status = "generated"
    except Exception:
        for item in task.items:
            if item.status not in {"generated", "approved", "scheduled", "published"}:
                item.status = "generation_failed"
        task.status = "generation_failed"
        db.commit()
        raise
    db.commit()
    db.refresh(task)
    return task


def schedule_campaign(db: Session, payload: PublicationCampaignCreate) -> models.PublicationCampaign:
    campaign = models.PublicationCampaign(
        name=payload.name,
        site_id=payload.site_id,
        start_at=payload.start_at,
        interval_minutes=payload.interval_minutes,
        items_per_run=payload.items_per_run,
        status="active",
    )
    db.add(campaign)
    for index, item_id in enumerate(payload.content_item_ids):
        item = db.get(models.ContentItem, item_id)
        if item and item.status == "approved" and item.site_id == payload.site_id:
            item.status = "scheduled"
            item.scheduled_at = payload.start_at + timedelta(minutes=payload.interval_minutes * index)
    db.commit()
    db.refresh(campaign)
    return campaign


def get_dashboard(db: Session) -> dict:
    total_tasks = db.scalar(select(func.count(models.GenerationTask.id))) or 0
    generated = db.scalar(select(func.count(models.ContentItem.id)).where(models.ContentItem.status.in_(["generated", "approved", "scheduled", "published"]))) or 0
    awaiting_approve = db.scalar(select(func.count(models.ContentItem.id)).where(models.ContentItem.status == "generated")) or 0
    scheduled = db.scalar(select(func.count(models.ContentItem.id)).where(models.ContentItem.status == "scheduled")) or 0
    published = db.scalar(select(func.count(models.ContentItem.id)).where(models.ContentItem.status == "published")) or 0
    errors = db.scalar(select(func.count(models.ContentItem.id)).where(models.ContentItem.status.in_(["publication_failed", "generation_failed"]))) or 0

    next_item = db.scalars(
        select(models.ContentItem)
        .where(models.ContentItem.status == "scheduled")
        .order_by(models.ContentItem.scheduled_at.asc())
        .limit(1)
    ).first()

    active_tasks = db.scalars(select(models.GenerationTask).order_by(models.GenerationTask.created_at.desc()).limit(6)).all()
    queue = db.scalars(
        select(models.ContentItem)
        .where(models.ContentItem.status.in_(["scheduled", "publishing"]))
        .order_by(models.ContentItem.scheduled_at.asc())
        .limit(8)
    ).all()
    recent_errors = db.scalars(select(models.PublicationLog).where(models.PublicationLog.error_message.is_not(None)).order_by(models.PublicationLog.created_at.desc()).limit(5)).all()

    return {
        "stats": {
            "total_tasks": total_tasks,
            "generated": generated,
            "awaiting_approve": awaiting_approve,
            "scheduled": scheduled,
            "published": published,
            "errors": errors,
            "next_publication_at": next_item.scheduled_at if next_item else None,
        },
        "active_tasks": [
            {
                "id": task.id,
                "title": task.title,
                "geo": task.geo,
                "language": task.language,
                "topics_count": task.topics_count,
                "status": task.status,
                "created_at": task.created_at,
            }
            for task in active_tasks
        ],
        "publication_queue": [
            {
                "id": item.id,
                "topic": item.topic,
                "status": item.status,
                "scheduled_at": item.scheduled_at,
                "slug": item.slug,
            }
            for item in queue
        ],
        "recent_errors": [
            {
                "id": log.id,
                "error_message": log.error_message,
                "endpoint_url": log.endpoint_url,
                "created_at": log.created_at,
            }
            for log in recent_errors
        ],
    }


async def publish_item(db: Session, item: models.ContentItem, site: models.Site) -> None:
    item.status = "publishing"
    db.commit()
    headers = {"Content-Type": "application/json", "Idempotency-Key": item.idempotency_key}
    if site.api_token:
        headers["Authorization"] = f"Bearer {site.api_token}"

    try:
        request_payload = build_publication_payload(db, item)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(site.publication_endpoint, json=request_payload, headers=headers)
        response_body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"raw": response.text}
        log = models.PublicationLog(
            content_item_id=item.id,
            endpoint_url=site.publication_endpoint,
            request_payload=request_payload,
            response_status=response.status_code,
            response_body=response_body,
        )
        db.add(log)
        if response.status_code in (200, 201):
            item.status = "published"
            item.published_at = datetime.now(timezone.utc)
            item.published_url = response_body.get("url")
        elif response.status_code in (429, 500, 502, 503):
            item.status = "retry_scheduled"
            item.scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        else:
            item.status = "publication_failed"
        db.commit()
    except Exception as exc:
        db.add(
            models.PublicationLog(
                content_item_id=item.id,
                endpoint_url=site.publication_endpoint,
                request_payload=build_publication_payload(db, item),
                error_message=str(exc),
            )
        )
        item.status = "retry_scheduled"
        item.scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        db.commit()


def build_publication_payload(db: Session, item: models.ContentItem) -> dict:
    payload = copy.deepcopy(item.generated_json)
    if not item.section_id:
        return payload

    section = db.get(models.Section, item.section_id)
    if not section:
        return payload

    publication_target = {
        "section_id": section.external_id,
        "section_name": section.name,
        "section_path": section.path,
    }
    payload["publication_target"] = publication_target
    for page in payload.get("pages", []):
        if isinstance(page, dict):
            page["sectionId"] = section.external_id
            page["sectionPath"] = section.path
    return payload
