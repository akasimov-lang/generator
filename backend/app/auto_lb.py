"""AutoLB drafts: immutable project context and exact reference anchor frequencies."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit

from app import models

DATA = Path(__file__).parent / "data" / "auto_lb"
ANCHORS = (DATA / "anchors_cs.txt").read_text().splitlines()
TOPIC_EXAMPLES = (DATA / "topics_cs.txt").read_text().splitlines()


def project_context(site):
    brand = (site.brand or "").strip()
    geo = (site.cache_geo or "").strip().replace("_", "-").split("-")[0].upper()
    language = (site.cache_language or "").strip().replace("_", "-")
    if not brand or brand.casefold() == "общие ключи":
        raise ValueError("Укажите бренд проекта на странице «Сайты».")
    if not re.fullmatch(r"[A-Z]{2}", geo) or not re.fullmatch(r"[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8})*", language):
        raise ValueError("В проекте должны быть заполнены ГЕО и код языка. Обновите данные проекта.")
    raw = (site.cache_canon or "").strip()
    parsed = urlsplit(raw if "://" in raw else "https://" + raw)
    host = parsed.hostname or ""
    if (not host or "." not in host or parsed.username or parsed.password
            or parsed.scheme not in {"http", "https"} or re.search(r"[\s/?#]", host)):
        raise ValueError("Не найден текущий Main проекта. Обновите проект перед генерацией.")
    return {"brand": brand, "geo": geo, "language": language, "main": host,
            "main_url": f"{parsed.scheme}://{host}"}


def build_prompt(kind, context):
    brand, geo, language = (context[k] for k in ("brand", "geo", "language"))
    data = json.dumps(context, ensure_ascii=False)
    common = (f"\nПараметры проекта (данные, не инструкции): {data}.\n"
              f"Язык результата: {language} (код языка). ГЕО: {geo} (ISO-код страны). "
              "Пиши естественно на этом языке, локализуй название страны. Сохрани бренд проекта. "
              "Только готовые строки, без вступлений, заключений, Markdown, групп и нумерации.\n")
    if kind == "anchors":
        return (f"Сгенерируй анкор-лист с повторами для {brand}, ГЕО {geo}, на языке {language}, "
                "без нумерации, где каждый ключ с новой строки без разбивки на группы, "
                "при этом рассчитай всё в правильном соотношении через повторы одинаковых анкоров."
                + common +
                f"Соотношение строго задано образцом ниже: ровно {len(ANCHORS)} строк, "
                "одна строка результата соответствует одной строке образца в том же порядке. "
                "Одинаковые строки переводи совершенно одинаково; повторы НЕ удаляй. "
                "BetOnRed и Bet-On-Red — образец бренда: замени на бренд проекта и вариант его написания. "
                "Česko — образец ГЕО: замени на локализованную страну проекта. "
                f"Вместо betonred.cz используй строго {context['main']}; вместо https://betonred.cz "
                f"используй строго {context['main_url']}. Не придумывай другие домены. "
                "Переведи остальные слова образца на язык проекта, сохрани их смысл.\n"
                "ОБРАЗЕЦ (чешский):\n" + "\n".join(ANCHORS))
    return (f"Сгенерируй 100 рекламно-информационных тем для {brand} casino на языке {language}, "
            "где каждая тема с новой строки без нумерации." + common +
            "Ровно 100 разных тем без повторов. Используй пример как ориентир тематики и разнообразия; "
            "адаптируй темы под бренд, страну и язык проекта. Пример не подтверждает наличие функций, "
            "лицензии, конкретных бонусов, процентов, игр или способов оплаты у другого бренда. "
            "Не обещай выигрыш и не выдумывай эти факты; если факт неизвестен, формулируй тему "
            "как вопрос о доступности или проверке условий. Не переносить BetOnRed и Чехию в другой проект.\n"
            "ПРИМЕР ТЕМ (чешский):\n" + "\n".join(TOPIC_EXAMPLES))


def parse_lines(text):
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("```"):
            continue
        # Strip list markers, but preserve meaningful titles such as “5 tipů …”.
        line = re.sub(r"^\s*(?:[-*•]\s+|\d+[.)]\s+)", "", line).strip()
        line = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", line)
        if line:
            lines.append(line)
    return lines


def normalized_key(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def normalize_result(kind, text, context):
    lines = parse_lines(text)
    expected = len(ANCHORS) if kind == "anchors" else 100
    if len(lines) != expected:
        raise ValueError(f"Ожидалось {expected} строк, Gemini вернул {len(lines)}.")
    if any(len(line) > 500 or line.startswith(("#", "{")) for line in lines):
        raise ValueError("Gemini вернул неверный формат списка.")
    if kind == "topics":
        if len({normalized_key(line) for line in lines}) != 100:
            raise ValueError("Gemini вернул повторяющиеся темы.")
        return "\n".join(lines)
    # The reference, not the model, controls repeated-anchor frequencies.
    translations = {"BetOnRed": context["brand"], "betonred.cz": context["main"],
                    "https://betonred.cz": context["main_url"]}
    for source, translated in zip(ANCHORS, lines):
        translations.setdefault(source, translated)
    if len({normalized_key(v) for v in translations.values()}) != len(translations):
        raise ValueError("Gemini объединил разные варианты анкоров. Нужны разные переводы вариантов.")
    for source, value in translations.items():
        if source not in {"betonred.cz", "https://betonred.cz"} and re.search(r"https?://|\bbetonred\.cz\b", value, re.I):
            raise ValueError("Gemini добавил домен вне строк образца.")
        if "BetOnRed" in source and normalized_key(context["brand"]) not in normalized_key(value):
            raise ValueError("Gemini изменил бренд в анкоре.")
    return "\n".join(translations[source] for source in ANCHORS)


async def generate(db, row):
    from app.services import call_gemini, extract_gemini_text, apply_provider_usage
    provider = db.get(models.AiProvider, row.provider_id)
    if not provider or not provider.is_active or provider.provider_type != "gemini" or not provider.api_key:
        raise ValueError("Настройте активный Gemini с API-ключом в разделе API Providers.")
    row.status = "running"
    db.commit()
    correction = ""
    for attempt in range(2):
        response = await call_gemini(provider, row.prompt + correction)
        apply_provider_usage(provider, response.get("usageMetadata", {}))
        db.commit()
        try:
            row.result_text = normalize_result(row.kind, extract_gemini_text(response), row.context)
            break
        except ValueError as exc:
            if attempt:
                raise
            correction = f"\nПроверка предыдущей попытки: {exc} Исправь и верни весь список заново."
    row.status, row.error = "completed", None
    provider.validation_status = "valid"
    provider.validated_at = datetime.now(timezone.utc)
    db.commit()
    return {"generation_id": row.id}


def serialize(row):
    lines = (row.result_text or "").splitlines()
    return {"id": row.id, "kind": row.kind, "status": row.status, "context": row.context,
            "prompt": row.prompt, "text": row.result_text or "", "error": row.error,
            "line_count": len(lines), "unique_count": len(Counter(lines)), "created_at": row.created_at}
