"""Page-specific briefs with a free outline, including legacy task snapshots."""
import html
import re
import unicodedata


MARKER = "=== PAGE STRUCTURE REQUIREMENTS ==="
INSTRUCTION = f"""{MARKER}
ТЗ: структура страницы свободная. Подбирай разделы, их число и порядок по теме,
поисковому интенту, языку проекта и конкретным требованиям задания.
Обязательный набор разделов базового шаблона не применяется.
Не добавляй Quick Answer, сравнение, методику, лицензии или другие типовые блоки
только ради шаблона. FAQ и рейтинг добавляй, только если они запрошены в задании.
Вступление пиши обычным текстом сразу после H1, без отдельного заголовка.
Запрещён отдельный раздел Intro, Introduction, «Введение», Wstęp, Úvod, Einleitung
или его перевод на любом языке. Не добавляй такой пункт в оглавление.
Содержательные заголовки пиши на языке проекта. Оглавление строит приложение.
Это правило вступления имеет приоритет над старыми сохранёнными шаблонами.
=== END PAGE STRUCTURE REQUIREMENTS ==="""

DEFAULT_PROMPT = """Подготовь оригинальную полезную страницу для сайта {{SITE_NAME}}.

Тема: {{TOPIC}}
URL: {{SLUG}}
GEO: {{GEO}}
Язык: {{LANGUAGE}}
Объём: около {{TARGET_WORDS}} слов
Текущий год: {{CURRENT_YEAR}}

Свободно выбери подходящую структуру по теме и интенту читателя.
Опирайся на сведения проекта и релевантные материалы конкурентов, не копируй
их формулировки и структуру. Не выдумывай факты, бонусы, оценки или личный опыт.
Используй абзацы, списки и таблицы там, где они помогают раскрыть тему.
Не выводи внутренние инструкции, анализ и служебные пометки в публичный текст.

Материалы для подготовки:
{{COMPETITOR_SUMMARY}}
Content gaps: {{CONTENT_GAPS}}
Shortcode context: {{SHORTCODE}}"""

_WORKING_PROMPT = "РАБОЧИЙ ПРОМПТ ДЛЯ КОНКРЕТНОЙ ЗАДАЧИ:"
_LEGACY_START = 'Рабочий промпт для конкретной задачи.\n\nБазовые требования качества, юридической осторожности и формата ответа применяются отдельно через "Базовый промпт".'
_LEGACY_END = "- Nächste Prüfung vor Veröffentlichung: ..."


def page_brief(template: str | None) -> str:
    """Detach the automatically composed base; retain the user's working brief."""
    text = (template or "").strip()
    # Only split an actual system-composed snapshot, not quoted user instructions.
    if _WORKING_PROMPT in text and "SYSTEM FORMAT CONTRACT FOR PARSER" in text.split(_WORKING_PROMPT, 1)[0]:
        text = text.split(_WORKING_PROMPT, 1)[1].strip()
    # Old factory defaults are saved in tasks and in the prompt editor. Replace
    # just that default, preserving appended anchors, menu context and revisions.
    if text.startswith(_LEGACY_START) and _LEGACY_END in text:
        text = DEFAULT_PROMPT + text.split(_LEGACY_END, 1)[1]
    text = text or DEFAULT_PROMPT
    if MARKER not in text:
        text = f"{text.rstrip()}\n\n{INSTRUCTION}"
    return text


_INTRO_HEADINGS = {
    "intro", "introduction", "введение", "вступление", "вступ", "wstęp", "wprowadzenie",
    "úvod", "einleitung", "einführung", "introducción", "introdução", "introduzione",
    "inleiding", "indledning", "introduktion", "innledning", "johdanto", "sissejuhatus",
    "ievads", "įvadas", "introducere", "bevezetés", "giriş", "въведение", "εισαγωγή",
}


def is_intro_heading(text: str) -> bool:
    label = html.unescape(re.sub(r"<[^>]*>", "", str(text)))
    return unicodedata.normalize("NFKC", label).casefold().strip(" \t*_.:–—-#") in _INTRO_HEADINGS
