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
DEFAULT_CONTENT_PROMPT_TEMPLATE = """Рабочий промпт для конкретной задачи.

Базовые требования качества, юридической осторожности и формата ответа применяются отдельно через "Базовый промпт".
Здесь описывай только нишу, интент, структуру и специальные требования к странице.

Роль:
Ты — senior SEO-редактор и content strategist для gambling/betting тем.

Задача:
Сгенерировать готовую SEO-страницу для сайта {{SITE_NAME}}.

Переменные:
- Тема страницы: {{TOPIC}}
- Slug страницы: {{SLUG}}
- Гео/страна: {{GEO}}
- Язык страницы: {{LANGUAGE}}
- Желаемый объем: около {{TARGET_WORDS}} слов
- Текущий год: {{CURRENT_YEAR}}
- Shortcode context: {{SHORTCODE}}

Контекст ниши:
Онлайн-казино, ставки, casino providers, легальные Anbieter, лицензии, Spielerschutz, Zahlungen, Auszahlungen, KYC, Datenschutz, Limits, sichere Online Casinos.

Главная цель:
Создать полезную, структурированную, юридически аккуратную страницу, которая полно отвечает на поисковый интент пользователя и пригодна для редакторской проверки перед публикацией.

Внутренняя SEO-логика, НЕ выводить в текст:
1. Главный интент.
2. 8-12 подинтентов.
3. Главный ключ.
4. Вторичные ключи.
5. FAQ-запросы.
6. Legal/Safety/Payment кластеры.
7. Гипотетические content gaps.
8. Риски фактов, которые нужно проверить редактору.

Для страниц по Германии обязательно раскрыть:
- Was bedeutet GGL-Lizenz?
- Warum ist Lizenzprüfung wichtig?
- Wie erkennt man sichere Anbieter?
- Welche Rolle spielen KYC und Identitätsprüfung?
- Was muss man vor Einzahlung prüfen?
- Unterschied zwischen Einzahlung und Auszahlung.
- Spielerschutz, Limits und Selbstausschluss.
- Für wen sind Online Casinos nicht geeignet?
- Welche Warnsignale sollte man beachten?

Если тема рейтинговая:
- Если нет проверенного списка брендов, делай таблицу критериев выбора.
- Для мест под реальные бренды используй только placeholder:
  [Anbieter 1 - muss geprüft werden]
  [Anbieter 2 - muss geprüft werden]
  [Anbieter 3 - muss geprüft werden]

Шаблон ответа:
Title:
Meta Description:
H1:

H2: Intro
1-2 коротких абзаца. Сразу отвечай на основной запрос, без длинного вступления.

H2: Quick Answer
3-5 предложений с практическим ответом.

H2: Überblick / schneller Vergleich
2-4 абзаца. Если уместно, добавь таблицу:
| Kriterium | Worauf achten | Warum wichtig |
|---|---|---|

H2: Methodik: Wie wir Anbieter bewerten
Объясни критерии оценки без фейковых баллов и без неподтвержденного рейтинга.

H2: Lizenz und rechtlicher Rahmen
Объясни лицензии, локальные ограничения, что должен проверить пользователь и что должен проверить редактор.

H2: Sicherheit: Lizenz, Zahlungen, Datenschutz und KYC
Раскрой безопасность без обещаний абсолютной защиты.

H2: Zahlungen und Auszahlungen
Объясни различие между Einzahlung и Auszahlung, KYC, возможные задержки и что проверить до депозита.

H2: Spielerschutz und Limits
Раскрой лимиты, самоисключение, признаки проблемной игры.

H2: Für wen geeignet / nicht geeignet
Дай честное разделение аудиторий, без рекламного давления.

H2: Häufige Fehler vor der Registrierung
Дай практический список ошибок.

H2: FAQ
Сгенерируй 8-10 вопросов. Каждый вопрос и ответ пиши отдельными строками:
Q: ...
A: ...

H2: Responsible Gambling Hinweis
Добавь аккуратный блок на языке {{LANGUAGE}}:
- Glücksspiel ist mit Risiken verbunden.
- Nur mit Geld spielen, dessen Verlust verkraftbar ist.
- Limits nutzen.
- Bei Kontrollverlust Hilfe suchen.
- [Muss geprüft werden: lokale Hilfsangebote in {{GEO}}].

Editor Check:
- Suchintention: OK / Risiko
- Fakten: OK / Muss geprüft werden
- Legal-Risiko: OK / Risiko
- Keyword-Stuffing: OK / Risiko
- E-E-A-T: OK / Muss gestärkt werden
- Thin Content: OK / Risiko
- Struktur: OK / Risiko
- Nächste Prüfung vor Veröffentlichung: ...
"""

PROMPT_FORMAT_CONTRACT_MARKER = "SYSTEM FORMAT CONTRACT FOR PARSER"
PROMPT_FORMAT_CONTRACT = f"""{PROMPT_FORMAT_CONTRACT_MARKER}
Этот блок обязателен для любого промпта генерации в сервисе.

Формат ответа должен быть пригоден для автоматического парсинга в Editor.js:
- Не используй Markdown code fences.
- Начинай ответ строго с Title.
- В начале ответа должны быть ровно эти поля отдельными строками:
  Title:
  Meta Description:
  H1:
- Не повторяй Title, Meta Description и H1 в теле статьи.
- Каждый публичный раздел начинай отдельной строкой формата H2: Название раздела.
- Не используй отдельные строки Intro:, Quick Answer:, FAQ: или Responsible Gambling: без префикса H2.
- Не пиши короткие standalone-строки как подзаголовки. Если это заголовок, он обязан начинаться с H2:.
- Таблицы можно давать в markdown-формате.
- Списки делай через дефис.
- FAQ пиши внутри раздела H2: FAQ, вопросы через Q:, ответы через A:.
- Editor Check выводи в конце отдельным блоком; система сохранит его как служебные метаданные.
"""

BASE_PROMPT_TEMPLATE_NAME = "Базовый промпт"
DEFAULT_BASE_PROMPT_TEMPLATE = f"""Базовые требования для всех генераций контента.

Эти правила применяются к любому рабочему промпту в сервисе.

Переменные, которые подставляет система:
- Тема страницы: {{{{TOPIC}}}}
- Slug страницы: {{{{SLUG}}}}
- Гео/страна: {{{{GEO}}}}
- Язык страницы: {{{{LANGUAGE}}}}
- Желаемый объем: {{{{TARGET_WORDS}}}}
- Текущий год: {{{{CURRENT_YEAR}}}}
- Сайт/проект: {{{{SITE_NAME}}}}
- Shortcode context: {{{{SHORTCODE}}}}

Общие правила качества:
- Пиши строго на языке {{{{LANGUAGE}}}}.
- Не смешивай языки, кроме устоявшихся терминов вроде KYC, RTP, FAQ, GGL, OASIS, LUGAS.
- Тон: экспертный, спокойный, редакционный, не рекламный.
- Не утверждай, что ты изучил Google, TOP-10, конкурентов или реальные сайты, если браузинг недоступен.
- Не выдумывай факты, бренды, лицензии, бонусы, суммы, RTP, сроки выплат, комиссии, рейтинги, отзывы, даты обновления или ссылки.
- Если факт требует проверки, используй пометку: [Muss geprüft werden: ...].
- Не обещай выигрыш и не создавай ощущение гарантированной безопасности.
- Не используй формулировки: garantiert, ohne Risiko, 100% legal, sicherer Gewinn, absolut sicher, einzig rechtssicher, immer legal, strafbar.
- Не делай рекламный текст и keyword stuffing.
- Не повторяй главный ключ слишком часто.
- Не повторяй одинаковые вводки и FAQ.
- Не создавай фейковый опыт автора.
- Не создавай фейковый TOP-10, рейтинг, оценку или список брендов без проверенных данных.
- Если рабочий промпт требует рейтинг, но проверенных брендов нет, используй placeholders вида [Anbieter 1 - muss geprüft werden].
- Внутренний SEO-анализ, intent mapping и content gaps не выводи в публичный текст.

{PROMPT_FORMAT_CONTRACT}
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


def clean_multiline_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    compact_lines: list[str] = []
    previous_blank = False
    for line in lines:
        if not line:
            if not previous_blank:
                compact_lines.append("")
            previous_blank = True
            continue
        compact_lines.append(line)
        previous_blank = False
    return "\n".join(compact_lines).strip()


def extract_ai_article_parts(generated_text: str, fallback_topic: str) -> dict:
    title = ""
    meta_description = ""
    h1 = ""
    body_lines: list[str] = []
    editor_check_lines: list[str] = []
    in_editor_check = False

    for raw_line in generated_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        label_match = re.match(r"^(Title|Meta Description|H1)\s*:\s*(.*)$", line, flags=re.IGNORECASE)
        if label_match:
            label = label_match.group(1).lower()
            value = label_match.group(2).strip()
            if label == "title":
                title = value
            elif label == "meta description":
                meta_description = value
            elif label == "h1":
                h1 = value
            continue

        editor_match = re.match(r"^Editor Check\s*:?\s*(.*)$", line, flags=re.IGNORECASE)
        if editor_match:
            in_editor_check = True
            if editor_match.group(1):
                editor_check_lines.append(editor_match.group(1).strip())
            continue

        if in_editor_check:
            editor_check_lines.append(line)
        else:
            body_lines.append(line)

    return {
        "title": title or fallback_topic.strip(),
        "meta_description": meta_description,
        "h1": h1 or title or fallback_topic.strip(),
        "body": "\n".join(body_lines).strip(),
        "editor_check": "\n".join(editor_check_lines).strip(),
    }


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


RISKY_CONTENT_PHRASES = (
    "garantiert",
    "ohne Risiko",
    "100% legal",
    "sicherer Gewinn",
    "einzig rechtssicher",
    "strafbar",
)


def analyze_content_quality(payload: dict) -> dict:
    issues: list[dict] = []
    warnings: list[dict] = []
    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        return {
            "status": "failed",
            "issues": [{"code": "missing_pages", "message": "Payload has no pages."}],
            "warnings": [],
        }

    for page_index, page in enumerate(pages):
        if not isinstance(page, dict):
            issues.append({"code": "invalid_page", "page": page_index, "message": "Page must be an object."})
            continue
        blocks = page.get("content", {}).get("blocks", [])
        if not isinstance(blocks, list) or not blocks:
            issues.append({"code": "missing_blocks", "page": page_index, "message": "Page has no Editor.js blocks."})
            continue

        heading_levels = [
            block.get("data", {}).get("level")
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "header" and isinstance(block.get("data"), dict)
        ]
        if heading_levels.count(1) != 1:
            issues.append({"code": "invalid_h1_count", "page": page_index, "message": "Page must have exactly one H1 block."})
        if not any(level == 2 for level in heading_levels):
            warnings.append({"code": "missing_h2", "page": page_index, "message": "Page has no H2 sections."})

        page_text_parts: list[str] = []
        for block_index, block in enumerate(blocks):
            if not isinstance(block, dict):
                issues.append({"code": "invalid_block", "page": page_index, "block": block_index, "message": "Block must be an object."})
                continue
            block_type = block.get("type")
            data = block.get("data")
            block_text = clean_text(" ".join(extract_block_text(block)))
            page_text_parts.append(block_text)

            if block_type == "paragraph" and len(block_text) > 1800:
                issues.append(
                    {
                        "code": "oversized_paragraph",
                        "page": page_index,
                        "block": block_index,
                        "message": "Paragraph is too long for review and publication.",
                    }
                )
            if block_type == "paragraph" and re.search(r"\b(Title|Meta Description|H1):", block_text):
                issues.append(
                    {
                        "code": "metadata_inside_body",
                        "page": page_index,
                        "block": block_index,
                        "message": "Title, meta description or H1 labels leaked into page body.",
                    }
                )
            if block_type == "faq" and (not isinstance(data, list) or len(data) < 3):
                warnings.append({"code": "thin_faq", "page": page_index, "block": block_index, "message": "FAQ block has too few items."})

        page_text = clean_text(" ".join(page_text_parts))
        lowered = page_text.lower()
        for phrase in RISKY_CONTENT_PHRASES:
            if phrase.lower() in lowered:
                issues.append({"code": "risky_phrase", "page": page_index, "phrase": phrase, "message": "Risky legal or promotional phrase found."})
        if "[muss geprüft werden" in lowered:
            warnings.append({"code": "unverified_marker", "page": page_index, "message": "Text contains facts that must be checked before publication."})

    return {
        "status": "failed" if issues else ("warning" if warnings else "ok"),
        "issues": issues,
        "warnings": warnings,
    }


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

    article_parts = extract_ai_article_parts(generated_text, topic)
    page["title"] = article_parts["title"]
    page["breadcrumb"] = article_parts["h1"]
    page["description"] = article_parts["meta_description"] or clean_text(article_parts["body"])[:155] or page["description"]
    page["content"]["blocks"] = build_blocks_from_ai_text(
        generated_text=article_parts["body"] or generated_text,
        topic=article_parts["h1"],
        shortcode=shortcode,
        include_toc=include_toc,
        include_faq=include_faq,
    )
    base_payload["generation_meta"]["generator"] = "gemini"
    base_payload["generation_meta"]["model"] = provider.model
    base_payload["generation_meta"]["usage"] = usage
    if article_parts["editor_check"]:
        base_payload["generation_meta"]["editor_check"] = article_parts["editor_check"]
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
    if PROMPT_FORMAT_CONTRACT_MARKER not in prompt:
        prompt = f"{prompt.rstrip()}\n\n{PROMPT_FORMAT_CONTRACT}"
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
    return clean_multiline_text("\n\n".join(chunks))


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
        .where(models.PromptTemplate.name != BASE_PROMPT_TEMPLATE_NAME)
        .order_by(models.PromptTemplate.is_default.desc(), models.PromptTemplate.created_at.asc())
        .limit(1)
    )
    if existing:
        if not site.default_prompt_template_id:
            site.default_prompt_template_id = existing.id
        return existing

    prompt = models.PromptTemplate(
        site_id=site.id,
        name="Промпт тест 1",
        content=DEFAULT_CONTENT_PROMPT_TEMPLATE,
        is_default=True,
    )
    db.add(prompt)
    db.flush()
    site.default_prompt_template_id = prompt.id
    return prompt


def ensure_base_prompt_template(db: Session) -> models.PromptTemplate:
    existing = db.scalar(
        select(models.PromptTemplate)
        .where(models.PromptTemplate.name == BASE_PROMPT_TEMPLATE_NAME)
        .limit(1)
    )
    if existing:
        return existing

    prompt = models.PromptTemplate(
        site_id=None,
        name=BASE_PROMPT_TEMPLATE_NAME,
        content=DEFAULT_BASE_PROMPT_TEMPLATE,
        is_default=False,
    )
    db.add(prompt)
    db.flush()
    return prompt


def compose_prompt_with_base(db: Session, prompt_template: str | None) -> str:
    base_prompt = ensure_base_prompt_template(db)
    specific_prompt = prompt_template.strip() if prompt_template and prompt_template.strip() else DEFAULT_CONTENT_PROMPT_TEMPLATE
    if BASE_PROMPT_TEMPLATE_NAME in specific_prompt and PROMPT_FORMAT_CONTRACT_MARKER in specific_prompt:
        return specific_prompt
    return (
        f"{base_prompt.content.strip()}\n\n"
        "РАБОЧИЙ ПРОМПТ ДЛЯ КОНКРЕТНОЙ ЗАДАЧИ:\n"
        f"{specific_prompt}"
    )


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
    title = topic.strip()
    lines = [line.strip(" #*\t") for line in generated_text.splitlines() if line.strip()]
    blocks: list[dict] = [header_block(title, 1)]
    headings: list[str] = [title]
    pending_paragraphs: list[str] = []

    def flush_paragraphs() -> None:
        if pending_paragraphs:
            blocks.append(paragraph_block(" ".join(pending_paragraphs)))
            pending_paragraphs.clear()

    index = 0
    while index < len(lines):
        line = lines[index]

        if line.startswith("|") and line.endswith("|"):
            flush_paragraphs()
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].startswith("|") and lines[index].endswith("|"):
                cells = [cell.strip() for cell in lines[index].strip("|").split("|")]
                is_separator = all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)
                if not is_separator and any(cells):
                    rows.append(cells)
                index += 1
            if rows:
                blocks.append(table_block(rows))
            continue

        if re.match(r"^[-*]\s+", line):
            flush_paragraphs()
            items: list[str] = []
            while index < len(lines) and re.match(r"^[-*]\s+", lines[index]):
                items.append(re.sub(r"^[-*]\s+", "", lines[index]).strip())
                index += 1
            if items:
                blocks.append(list_block("unordered", items))
            continue

        explicit_heading = re.match(r"^(H[2-4]|#{2,4})\s*:?\s*(.+)$", line, flags=re.IGNORECASE)
        section_label = re.match(r"^([A-ZÄÖÜ][^:]{2,80})\s*:\s*$", line)

        if explicit_heading or section_label:
            flush_paragraphs()
            heading = explicit_heading.group(2).strip() if explicit_heading else line.rstrip(":").strip()
            if heading and heading.lower() != title.lower():
                headings.append(heading)
                blocks.append(header_block(heading, 2))
            index += 1
            continue

        pending_paragraphs.append(line)
        if len(" ".join(pending_paragraphs)) > 700:
            flush_paragraphs()
        index += 1
    flush_paragraphs()

    if include_toc and len(headings) > 1:
        blocks.insert(1, toc_block(headings[:8]))
    has_inline_faq = bool(re.search(r"\bFAQ\b|Häufig gestellte Fragen|häufige Fragen", generated_text, flags=re.IGNORECASE))
    if include_faq and not any(block.get("type") == "faq" for block in blocks) and not has_inline_faq:
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
    prompt_template = compose_prompt_with_base(db, payload.prompt_template)
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
        prompt_template_name=payload.prompt_template_name,
        prompt_template=prompt_template,
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
            generation_prompt_name=payload.prompt_template_name,
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
            item.generation_prompt_name = task.prompt_template_name
            item.generated_at = datetime.now(timezone.utc)
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
