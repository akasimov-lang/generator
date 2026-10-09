"""Final public copy gates; research URLs and editorial notes stay private."""
import re

NUMBERED = re.compile(r"^\s*(?:\d{1,3}|[IVX]{1,5})\s*[.)\-:–—]\s+", re.I)
ASSISTANT = re.compile(r"\b(?:as an ai|as a language model|here is (?:the|your) (?:html|template|content)|"
                       r"вот (?:готовый|ваш) (?:шаблон|html|текст)|как языковая модель|комментарий gemini)\b", re.I)
SOURCE_HEADING = re.compile(r"^(?:sources?|references?|источники|список источников|zdroje|quellen|fuentes)\s*:?$", re.I)


def check_public_copy(content):
    data = content.model_dump() if hasattr(content, "model_dump") else content
    headings = [data.get(k, "") for k in ("heading", "faq_title", "mobile_gallery_heading", "payments_heading", "providers_heading")]
    headings += [section["title"] for section in data["sections"]]
    headings += [item["question"] for item in data["faq"]]
    if any(NUMBERED.search(value) or re.match(r"^\s*0\d\s+", value) for value in headings):
        raise ValueError("Нельзя нумеровать информационные блоки и заголовки страницы")
    if any(SOURCE_HEADING.fullmatch(value.strip()) for value in headings):
        raise ValueError("Список источников не должен публиковаться на странице")
    def strings(value):
        if isinstance(value, str): yield value
        elif isinstance(value, list):
            for item in value: yield from strings(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key not in {"editorial_notes", "payment_systems", "game_providers"}: yield from strings(item)
    for value in strings(data):
        if ASSISTANT.search(value) or "<!--" in value or "```" in value:
            raise ValueError("В публичном тексте найдены комментарии Gemini или служебная разметка")
        if re.search(r"https?://|www\.|\[[0-9]{1,3}\]|cite|\[cite", value, re.I):
            raise ValueError("Уберите ссылки и сноски на источники из финального текста")


def clean_css(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    if "/*" in css or re.search(r"counter(?:s|-increment|-reset)?\s*[:(]|content\s*:\s*['\"]\s*\d", css, re.I):
        raise ValueError("CSS не должен нумеровать информационные блоки")
    return css
