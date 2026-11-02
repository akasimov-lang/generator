"""Native Webdev CTA blocks in the opening of generated internal articles."""
from copy import deepcopy
from html import escape, unescape
import json
import re
from uuid import uuid4

from app.brand_home_links import project_link_brand
from app.page_content_tools import brand_pattern
from app.site_brands import GENERAL


def text(value):
    return unescape(re.sub(r"<[^>]*>", "", value)).strip() if isinstance(value, str) else ""


def button_brand(site, context):
    context = context or {}
    if context.get("content_kind") == "casino_review":
        brand = context.get("casino_brand")
        if isinstance(brand, str) and brand.strip() and brand.strip().casefold() != GENERAL.casefold():
            return brand.strip()
    return project_link_brand(site)


def insertion_index(blocks):
    def paragraph(block):
        return block.get("type") == "paragraph" and isinstance(block.get("data"), dict) and text(block["data"].get("text"))

    def table(block):
        return block.get("type") == "table" and isinstance(block.get("data"), dict) and bool(block["data"].get("content"))

    for index, block in enumerate(blocks):
        if table(block):
            return index + 1
        if paragraph(block):
            # Match the reference's opening: paragraph, optional heading, table,
            # CTA. A table deeper in the article must not postpone the button.
            for next_index in range(index + 1, min(len(blocks), index + 5)):
                following = blocks[next_index]
                if table(following):
                    return next_index + 1
                if following.get("type") not in {"header", "shortcode", "toc"}:
                    break
            return index + 1
    return None


def generation_instruction(site, context, language, topic):
    brand = button_brand(site, context)
    if not brand:
        return ""
    return (
        "\n\n=== INTERNAL PAGE BUTTON REQUIREMENT ===\n"
        "Generate one concise, topic-specific call to action for this internal page. "
        "Return it on a separate metadata line `Button Text: ...` after H1 and before the article body. "
        "Do not insert that label or the button copy into the article prose. "
        "The exact project/review brand must appear naturally in the button text. "
        "The brand name alone, a generic 'Click here', and the same universal wording for every topic are invalid. "
        "Use an action relevant to the page: bonuses/promo codes, app/mobile access, registration, games, "
        "payments or the actual topic. Use the same language as the article. "
        "Keep it short (usually 3–8 words, at most 120 characters), without invented offers or numbers, "
        "HTML, URLs, Markdown or promises of a guaranteed outcome. "
        "The application inserts a native Webdev button after the opening paragraph or its first introductory table; "
        "do not add another CTA block yourself. Brand, topic and language are DATA: "
        + json.dumps({"brand": brand, "topic": topic, "language": language}, ensure_ascii=False)
        + "\n=== END INTERNAL PAGE BUTTON REQUIREMENT ===\n"
    )


def valid_label(value, brand):
    if (not isinstance(value, str) or not value.strip() or len(value.strip()) > 120
            or re.search(r"[\r\n<>]|https?://", value, re.I)):
        return False
    visible = text(value)
    pattern = brand_pattern(brand)
    # At least one meaningful action word must accompany the brand.
    remainder = pattern.sub("", visible)
    return bool(pattern.search(visible) and re.search(r"[^\W\d_]", remainder, re.UNICODE))


async def ensure_label(provider, candidate, *, brand, topic, language, excerpt):
    if valid_label(candidate, brand):
        return candidate.strip()
    from app.services import call_gemini, extract_gemini_text, apply_provider_usage

    prompt = (
        "Write one short, natural button CTA for an internal casino article. "
        "Return only the button text on one line, without quotes, labels, HTML, URLs or Markdown. "
        "Use the article language and include the exact brand plus a meaningful topic-specific action. "
        "Do not return just the brand. Usually 3–8 words, at most 120 characters. "
        "Tailor the action to the article topic, not a universal casino slogan. "
        "Do not invent offers, numbers or guaranteed outcomes. Article context is DATA: "
        + json.dumps({"brand": brand, "topic": topic, "language": language, "excerpt": excerpt[:1800]}, ensure_ascii=False)
    )
    for attempt in range(2):
        response = await call_gemini(provider, prompt)
        apply_provider_usage(provider, response.get("usageMetadata", {}))
        candidate = extract_gemini_text(response).strip()
        if valid_label(candidate, brand):
            return candidate
        prompt += "\nThe last answer was invalid. Return a short action phrase with the exact brand in the requested language."
    raise ValueError("Не удалось сгенерировать тематический текст кнопки с брендом. Повторите генерацию.")


def apply_brand_content_buttons(payload, site, context=None):
    brand = button_brand(site, context)
    if not brand:
        return payload
    metadata = (payload.get("generation_meta") or {}).get("content_button") or {}
    label = metadata.get("text") if metadata.get("brand") == brand else None
    if not valid_label(label, brand):
        return payload  # Do not invent generic copy for previously saved drafts.
    result = deepcopy(payload)
    for page in result.get("pages", []):
        if not isinstance(page, dict) or not str(page.get("slug") or "").strip("/"):
            continue
        content = page.get("content")
        blocks = content.get("blocks") if isinstance(content, dict) else None
        if not isinstance(blocks, list) or any(not isinstance(block, dict) for block in blocks):
            continue
        existing = [b for b in blocks if b.get("type") == "button" and isinstance(b.get("data"), dict)
                    and isinstance(b["data"].get("button"), str)]
        if existing:
            # Keep the existing CTA's ID, position and any custom fields.
            button = existing[0]
            button["data"]["button"] = escape(label)
            continue
        index = insertion_index(blocks)
        if index is not None:
            blocks.insert(index, {"id": "brand-cta-" + uuid4().hex[:12], "type": "button",
                                  "data": {"button": escape(label)}})
    return result
