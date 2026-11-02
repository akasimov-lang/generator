"""Required generic casino queries, localized for each AutoLB project snapshot."""
import json
import re
import unicodedata

from sqlalchemy import select

from app import models

PROFILE = "general-casino-v1"
POLISH = (
    "polskie kasyno online",
    "najlepsze kasyna online",
    "kasyna internetowe",
    "kasyno na prawdziwe pieniadze",
    "wypłacalne kasyna internetowe",
    "wypłacalne kasyna",
    "najbardziej wypłacalne kasyno online",
    "kasyno online blik",
    "blik kasyno",
    "kasyno z blikiem",
)


def key(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def is_polish(context):
    return context["geo"] == "PL" and context["language"].split("-")[0].casefold() == "pl"


def snapshot(context):
    if context.get("unlimited_anchors"):
        context["required_keyword_profile"] = PROFILE
        if is_polish(context):
            context["required_keywords"] = list(POLISH)
    return context


def validate(values):
    if (not isinstance(values, list) or len(values) != len(POLISH)
            or any(not isinstance(v, str) or not v.strip() or len(v) > 200
                   or re.search(r"[\r\n<>]", v) for v in values)):
        raise ValueError("Перевод обязательных ключей должен содержать 10 непустых фраз.")
    result = [v.strip() for v in values]
    if len({key(v) for v in result}) != len(result):
        raise ValueError("Перевод обязательных ключей содержит одинаковые фразы. Нужны 10 разных вариантов.")
    if any("blik" not in key(v) for v in result[-3:]):
        raise ValueError("В трёх последних обязательных ключах должно сохраняться название BLIK.")
    return result


def required(context):
    if not context.get("unlimited_anchors") or context.get("required_keyword_profile") != PROFILE:
        return []  # Previously queued jobs retain their original contract.
    return validate(context.get("required_keywords"))


def prompt(context, kind):
    if not context.get("unlimited_anchors") or context.get("required_keyword_profile") != PROFILE:
        return ""
    values = context.get("required_keywords")
    if values:
        instruction = ("Включи каждую из следующих 10 обязательных фраз отдельной строкой в точном написании. "
                       "Дополнительные анкоры и повторы допустимы."
                       if kind == "anchors" else
                       "Используй каждую из следующих 10 обязательных фраз хотя бы в одной теме, "
                       "сохранив её точное написание внутри темы. Темы должны оставаться разными.")
        return "\n" + instruction + "\n" + "\n".join(validate(values)) + "\n"
    return ("\nОбязательное семантическое ядро для сайтов с общими ключами: "
            + json.dumps(POLISH, ensure_ascii=False)
            + ". Локализуй все 10 фраз на язык проекта; вместо Польши используй страну GEO проекта. "
            "Сохрани BLIK как название платёжной системы и различия между всеми вариантами. "
            "Все 10 локализованных фраз обязательны в результате.\n")


async def prepare(db, row, provider):
    """Save the localized vocabulary before generating any final list."""
    from app.services import call_gemini, extract_gemini_text, apply_provider_usage

    context = row.context
    if not context.get("unlimited_anchors") or context.get("required_keyword_profile") != PROFILE:
        return
    if context.get("required_keywords"):
        required(context)
        return
    # Reuse the saved translation for this project's GEO/language, including
    # subsequent topic batches and a changed Main. Do not rewrite old results.
    previous = db.scalars(select(models.AutoLbGeneration).where(
        models.AutoLbGeneration.site_id == row.site_id,
        models.AutoLbGeneration.status == "completed",
    ).order_by(models.AutoLbGeneration.created_at.desc(), models.AutoLbGeneration.id.desc()))
    values = None
    for saved in previous:
        old = saved.context or {}
        if (old.get("required_keyword_profile") == PROFILE
                and old.get("unlimited_anchors")
                and old.get("geo") == context["geo"]
                and key(old.get("language", "")) == key(context["language"])):
            try:
                values = required(old)
            except ValueError:
                continue
            break
    if values is None:
        request = (
            "Переведи и локализуй 10 польских поисковых фраз для сайта об онлайн-казино. "
            "Верни только JSON-массив из 10 разных строк в исходном порядке, без Markdown. "
            "Параметры локализации: "
            + json.dumps({k: context[k] for k in ("geo", "language")}, ensure_ascii=False)
            + ". Все фразы на указанном языке проекта. В первой фразе вместо Польши используй "
            "естественное название или прилагательное страны указанного GEO. "
            "Выплатные/выплачивающие казино — смысл трёх фраз с wypłacalne; "
            "не превращай их в обещание выигрыша. Сохрани BLIK как имя платёжной системы "
            "в трёх последних фразах. Сохрани различия между всеми 10 вариантами, "
            "включая перестановки слов. Исходные фразы: " + json.dumps(POLISH, ensure_ascii=False)
        )
        correction = ""
        for attempt in range(2):
            response = await call_gemini(provider, request + correction)
            apply_provider_usage(provider, response.get("usageMetadata", {}))
            db.commit()
            try:
                text = extract_gemini_text(response).strip()
                if text.startswith("```"):
                    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
                values = validate(json.loads(text))
                break
            except (ValueError, TypeError) as exc:
                if attempt:
                    raise ValueError("Не удалось получить 10 разных переводов обязательных ключей. Повторите генерацию.") from exc
                correction = ("\nПредыдущий ответ не прошёл проверку: " + str(exc)
                              + " Верни JSON-массив из 10 разных непустых фраз; в последних трёх сохрани BLIK.")
    row.context = {**context, "required_keywords": values}
    db.commit()


def include_anchors(lines, context):
    values = required(context)
    canonical = {key(v): v for v in values}
    lines = [canonical.get(key(line), line) for line in lines]
    seen = {key(line) for line in lines}
    return lines + [v for v in values if key(v) not in seen]


def check_topics(lines, context):
    values = required(context)
    normalized = [key(line) for line in lines]
    missing = [v for v in values if not any(key(v) in line for line in normalized)]
    if missing:
        raise ValueError("В темах отсутствуют обязательные ключи: " + "; ".join(missing))
