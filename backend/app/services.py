import asyncio
import copy
import html
import json
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urlparse, urlunparse

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
DATAFORSEO_DEFAULT_ENDPOINT = "https://api.dataforseo.com/v3"
DATAFORSEO_USER_DATA_PATH = "/appendix/user_data"
DATAFORSEO_LOCATIONS_PATH = "/serp/google/locations"
DATAFORSEO_SERP_PATH = "/serp/google/organic/live/advanced"
COMPETITOR_QUERY_LIMIT = 5
COMPETITOR_RESULTS_PER_QUERY = 6
MAX_COMPETITOR_PAGE_CHARS = 1_200_000
MAX_COMPETITOR_TEXT_CHARS = 60_000
DATAFORSEO_COUNTRY_ALIASES = {"UK": "GB"}
DATAFORSEO_LOCATION_CACHE: dict[tuple[str, str], dict[str, int]] = {}
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
- Поисковые запросы по теме: {{SEARCH_QUERIES}}
- URL конкурентов из выдачи: {{COMPETITOR_URLS}}
- Краткий анализ конкурентов: {{COMPETITOR_SUMMARY}}
- Content gaps: {{CONTENT_GAPS}}
- Частые заголовки конкурентов: {{COMMON_HEADINGS}}
- Темы, подтвержденные анализом нескольких конкурентов: {{MISSING_BLOCKS_TO_COVER}}

Контекст ниши:
Онлайн-казино, ставки, casino providers, легальные Anbieter, лицензии, Spielerschutz, Zahlungen, Auszahlungen, KYC, Datenschutz, Limits, sichere Online Casinos.

Главная цель:
Создать полезную, структурированную, юридически аккуратную страницу, которая полно отвечает на поисковый интент пользователя и пригодна для редакторской проверки перед публикацией.

Если передан анализ конкурентов:
- Используй его только как исследовательский контекст.
- Не копируй конкурентов и не делай близкий перефраз.
- Не повторяй структуру конкурентов один в один.
- Делай оригинальную структуру, закрывай интент полнее и аккуратно отмечай факты, которые нужно проверить.
- Не утверждай в публичном тексте, что ты изучил Google или конкретных конкурентов.

Внутренняя SEO-логика, НЕ выводить в текст:
1. Главный интент.
2. 8-12 подинтентов.
3. Главный ключ.
4. Вторичные ключи.
5. FAQ-запросы.
6. Legal/Safety/Payment кластеры.
7. Гипотетические content gaps.
8. Риски фактов, которые нужно проверить редактору.

Правила локализации и анализа:
- Структуру и набор смысловых блоков определяй динамически по теме, выбранному гео, языку и фактически собранным материалам конкурентов.
- Не добавляй обязательный блок только потому, что он обычно встречается в нише или был нужен для другой страны.
- Не добавляй раздел о проверке лицензии, если эта тема не подтверждена анализом нескольких конкурентов для текущего гео.

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
- Поисковые запросы: {{{{SEARCH_QUERIES}}}}
- URL конкурентов: {{{{COMPETITOR_URLS}}}}
- Анализ конкурентов: {{{{COMPETITOR_SUMMARY}}}}
- Content gaps: {{{{CONTENT_GAPS}}}}
- Частые заголовки конкурентов: {{{{COMMON_HEADINGS}}}}
- Недостающие блоки: {{{{MISSING_BLOCKS_TO_COVER}}}}

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
- Если передан competitor brief, используй его только как исследовательский контекст.
- Не копируй конкурентов, не делай близкий перефраз и не повторяй их структуру один в один.
- Не утверждай в публичном тексте, что ты изучил Google, TOP выдачи или конкретные сайты.
- Закрывай intent полнее конкурентов, но без вымышленных фактов.

{PROMPT_FORMAT_CONTRACT}
"""


def now_payload_time() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def make_block_id() -> str:
    return uuid.uuid4().hex[:10]


def normalize_slug(topic: str) -> str:
    title_words = re.findall(r"[\w]+", topic, flags=re.UNICODE)
    short_title = " ".join(title_words[:5]) if title_words else topic
    slug = slugify(short_title) or uuid.uuid4().hex[:8]
    return f"/{slug}/"


def concise_h1_from_topic(topic: str, max_words: int = 10, max_chars: int = 70) -> str:
    clean_topic = clean_text(topic)
    if not clean_topic:
        return "Content"
    primary_part = re.split(r"\s*[:|–—]\s*", clean_topic, maxsplit=1)[0].strip() or clean_topic
    words = primary_part.split()
    if len(words) > max_words:
        primary_part = " ".join(words[:max_words])
    if len(primary_part) > max_chars:
        shortened = primary_part[: max_chars + 1].rsplit(" ", 1)[0].strip()
        primary_part = shortened or primary_part[:max_chars].strip()
    return primary_part.rstrip(" ,;:-") or clean_topic


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


def compact_lines(values: list[object], limit: int | None = None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_text(value)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
        if limit and len(result) >= limit:
            break
    return result


def normalize_competitor_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = re.sub(r"/+", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = parsed.query
    return urlunparse((scheme.lower(), netloc, path, "", query, ""))


def hostname_from_url(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.lower().removeprefix("www.")


def is_own_domain(url: str, site: models.Site | None) -> bool:
    site_host = hostname_from_url(site.base_url if site else None)
    url_host = hostname_from_url(url)
    if not site_host or not url_host:
        return False
    return url_host == site_host or url_host.endswith(f".{site_host}")


def generate_competitor_search_queries(topic: str, geo: str, language: str, excluded_queries: set[str] | None = None) -> list[str]:
    del geo, language
    text = re.sub(r"[/|:()\\[\\],.!?]+", " ", topic.lower())
    tokens = re.findall(r"[\wäöüßáàâçéèêíìîñóòôúùû-]+", text, flags=re.IGNORECASE)
    stopwords = {
        "und",
        "oder",
        "mit",
        "für",
        "der",
        "die",
        "das",
        "ein",
        "eine",
        "einer",
        "im",
        "in",
        "am",
        "an",
        "auf",
        "von",
        "the",
        "and",
        "for",
        "with",
    }
    meaningful = [token for token in tokens if len(token) > 2 and token not in stopwords]
    source_words = meaningful if meaningful else tokens
    if not source_words:
        return compact_lines([clean_text(topic.lower())], 1)

    candidates: list[str] = []
    for size in (5, 4, 3):
        if len(source_words) >= size:
            last_start = len(source_words) - size
            starts = [0, last_start, *range(1, last_start)]
            for start in starts:
                candidates.append(" ".join(source_words[start : start + size]))
    if not candidates:
        candidates.append(" ".join(source_words[:5]))
    excluded = {clean_text(query.lower()) for query in (excluded_queries or set())}
    available = [query for query in compact_lines(candidates) if clean_text(query.lower()) not in excluded]
    return available[:COMPETITOR_QUERY_LIMIT]


def task_competitor_queries(db: Session, item: models.ContentItem) -> set[str]:
    return set(
        db.scalars(
            select(models.CompetitorQuery.query)
            .join(models.ContentItem, models.ContentItem.id == models.CompetitorQuery.content_item_id)
            .where(models.ContentItem.task_id == item.task_id)
            .where(models.ContentItem.id != item.id)
        ).all()
    )


def ensure_competitor_queries(db: Session, item: models.ContentItem, geo: str, language: str) -> list[models.CompetitorQuery]:
    existing = db.scalars(
        select(models.CompetitorQuery)
        .where(models.CompetitorQuery.content_item_id == item.id)
        .order_by(models.CompetitorQuery.position.asc())
    ).all()
    if existing:
        return existing

    queries = generate_competitor_search_queries(item.topic, geo, language, task_competitor_queries(db, item))
    for index, query in enumerate(queries, start=1):
        db.add(
            models.CompetitorQuery(
                content_item_id=item.id,
                query=query,
                position=index,
                status="draft",
            )
        )
    item.competitor_research_status = "queries_ready"
    item.competitor_research_progress = 0
    item.competitor_research_error = None
    db.flush()
    return db.scalars(
        select(models.CompetitorQuery)
        .where(models.CompetitorQuery.content_item_id == item.id)
        .order_by(models.CompetitorQuery.position.asc())
    ).all()


def regenerate_competitor_queries(db: Session, item: models.ContentItem, geo: str, language: str) -> list[models.CompetitorQuery]:
    clear_competitor_research(db, item)
    queries = generate_competitor_search_queries(item.topic, geo, language, task_competitor_queries(db, item))
    for index, query in enumerate(queries, start=1):
        db.add(
            models.CompetitorQuery(
                content_item_id=item.id,
                query=query,
                position=index,
                status="draft",
            )
        )
    item.competitor_research_status = "queries_ready"
    item.competitor_research_progress = 0
    item.competitor_research_error = None
    db.flush()
    return db.scalars(
        select(models.CompetitorQuery)
        .where(models.CompetitorQuery.content_item_id == item.id)
        .order_by(models.CompetitorQuery.position.asc())
    ).all()


def replace_competitor_queries(db: Session, item: models.ContentItem, queries: list[str]) -> None:
    clean_queries = compact_lines(queries, 5)
    if not clean_queries:
        raise ValueError("At least one search query is required")
    clear_competitor_research(db, item)
    for index, query in enumerate(clean_queries, start=1):
        db.add(
            models.CompetitorQuery(
                content_item_id=item.id,
                query=query,
                position=index,
                status="draft",
            )
        )
    item.competitor_research_status = "queries_ready"
    item.competitor_research_progress = 0
    item.competitor_research_error = None
    db.flush()


def clear_competitor_research(db: Session, item: models.ContentItem) -> None:
    page_ids = select(models.CompetitorPage.id).where(models.CompetitorPage.content_item_id == item.id)
    result_ids = select(models.CompetitorResult.id).where(models.CompetitorResult.content_item_id == item.id)
    query_ids = select(models.CompetitorQuery.id).where(models.CompetitorQuery.content_item_id == item.id)
    for page in db.scalars(select(models.CompetitorPage).where(models.CompetitorPage.id.in_(page_ids))).all():
        db.delete(page)
    for result in db.scalars(select(models.CompetitorResult).where(models.CompetitorResult.id.in_(result_ids))).all():
        db.delete(result)
    # Results reference their source queries, so persist their deletion before
    # deleting the queries themselves (PostgreSQL enforces this foreign key).
    db.flush()
    for query in db.scalars(select(models.CompetitorQuery).where(models.CompetitorQuery.id.in_(query_ids))).all():
        db.delete(query)
    item.competitor_brief = None
    item.competitor_brief_text = None
    item.competitor_research_progress = 0
    item.competitor_research_error = None
    db.flush()


class CompetitorHTMLExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta_description = ""
        self.h1 = ""
        self.headings: list[dict] = []
        self.paragraphs: list[str] = []
        self.list_items: list[str] = []
        self.tables: list[list[list[str]]] = []
        self._ignore_depth = 0
        self._collectors: list[dict] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._current_table: list[list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if tag in {"script", "style", "noscript", "svg", "canvas", "iframe", "form", "button", "nav", "footer"}:
            self._ignore_depth += 1
            return
        if self._ignore_depth:
            return
        if tag == "meta":
            meta_name = (attrs_dict.get("name") or attrs_dict.get("property") or "").lower()
            if meta_name in {"description", "og:description", "twitter:description"} and attrs_dict.get("content"):
                if not self.meta_description:
                    self.meta_description = clean_text(attrs_dict["content"])
            return
        if tag == "table":
            self._current_table = []
            return
        if tag == "tr" and self._current_table is not None:
            self._current_row = []
            return
        if tag in {"td", "th"} and self._current_row is not None:
            self._current_cell = []
            self._collectors.append({"tag": tag, "text": []})
            return
        if tag in {"title", "h1", "h2", "h3", "p", "li"}:
            self._collectors.append({"tag": tag, "text": []})

    def handle_data(self, data: str) -> None:
        if self._ignore_depth:
            return
        for collector in self._collectors:
            collector["text"].append(data)
        if self._current_cell is not None:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._ignore_depth and tag in {"script", "style", "noscript", "svg", "canvas", "iframe", "form", "button", "nav", "footer"}:
            self._ignore_depth -= 1
            return
        if self._ignore_depth:
            return
        if tag in {"td", "th"} and self._current_row is not None and self._current_cell is not None:
            cell = clean_text(" ".join(self._current_cell))
            if cell:
                self._current_row.append(cell)
            self._current_cell = None
        if tag == "tr" and self._current_table is not None and self._current_row is not None:
            if self._current_row:
                self._current_table.append(self._current_row)
            self._current_row = None
            return
        if tag == "table" and self._current_table is not None:
            if self._current_table:
                self.tables.append(self._current_table[:20])
            self._current_table = None
            return

        for index in range(len(self._collectors) - 1, -1, -1):
            collector = self._collectors[index]
            if collector["tag"] != tag:
                continue
            self._collectors.pop(index)
            text = clean_text(" ".join(collector["text"]))
            if not text:
                return
            if tag == "title" and not self.title:
                self.title = text
            elif tag == "h1" and not self.h1:
                self.h1 = text
            elif tag in {"h2", "h3"}:
                self.headings.append({"level": int(tag[1]), "text": text})
            elif tag == "p" and len(text) >= 40:
                self.paragraphs.append(text)
            elif tag == "li" and len(text) >= 8:
                self.list_items.append(text)
            return

    def payload(self) -> dict:
        text_blocks = compact_lines([self.h1, *[item["text"] for item in self.headings], *self.paragraphs, *self.list_items])
        text_content = clean_multiline_text("\n\n".join(text_blocks))[:MAX_COMPETITOR_TEXT_CHARS]
        faq = [
            {"question": item, "answer": ""}
            for item in self.list_items
            if item.endswith("?") or item.lower().startswith(("was ", "wie ", "warum ", "wann ", "where ", "what ", "how "))
        ][:12]
        return {
            "title": self.title,
            "h1": self.h1,
            "meta_description": self.meta_description,
            "headings": self.headings[:80],
            "text_content": text_content,
            "tables": self.tables[:8],
            "lists": compact_lines(self.list_items, 80),
            "faq": faq,
            "word_count": len(re.findall(r"\b[\w'-]+\b", text_content, flags=re.UNICODE)),
        }


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


def validate_content_for_publication(item: models.ContentItem) -> dict:
    if item.status not in {"generated", "rejected", "approved", "scheduled", "retry_scheduled", "publishing"}:
        raise ValueError(f"Content in status '{item.status}' cannot be approved or published")
    quality = analyze_content_quality(item.generated_json)
    if quality["issues"]:
        messages = [str(issue.get("message") or issue.get("code") or "Invalid content") for issue in quality["issues"]]
        raise ValueError("Content validation failed: " + "; ".join(messages[:10]))
    return quality


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
    competitor_brief: dict | None = None,
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
    if competitor_brief:
        payload["generation_meta"]["competitor_research"] = {
            "status": "used",
            "generated_at": competitor_brief.get("generated_at"),
            "search_queries": competitor_brief.get("search_queries", []),
            "competitor_urls": competitor_brief.get("competitor_urls", []),
            "content_gaps": competitor_brief.get("content_gaps", []),
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
    competitor_brief: dict | None = None,
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
            competitor_brief=competitor_brief,
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
        competitor_brief=competitor_brief,
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
    competitor_brief: dict | None = None,
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
        competitor_brief=competitor_brief,
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
        competitor_brief=competitor_brief,
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
    page_title = topic.strip()
    page_h1 = concise_h1_from_topic(topic)
    page["title"] = page_title
    page["breadcrumb"] = page_title
    page["description"] = article_parts["meta_description"] or clean_text(article_parts["body"])[:155] or page["description"]
    page["content"]["blocks"] = build_blocks_from_ai_text(
        generated_text=article_parts["body"] or generated_text,
        topic=page_h1,
        shortcode=shortcode,
        include_toc=include_toc,
        include_faq=include_faq,
    )
    base_payload["generation_meta"]["generator"] = "gemini"
    base_payload["generation_meta"]["model"] = provider.model
    base_payload["generation_meta"]["usage"] = usage
    if competitor_brief:
        base_payload["generation_meta"]["competitor_research"] = {
            "status": "used",
            "generated_at": competitor_brief.get("generated_at"),
            "search_queries": competitor_brief.get("search_queries", []),
            "competitor_urls": competitor_brief.get("competitor_urls", []),
            "content_gaps": competitor_brief.get("content_gaps", []),
        }
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
    competitor_brief: dict | None = None,
) -> str:
    template = prompt_template.strip() if prompt_template and prompt_template.strip() else DEFAULT_CONTENT_PROMPT_TEMPLATE
    slug = normalize_slug(topic)
    competitor_values = prompt_context_from_brief(competitor_brief)
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
        **competitor_values,
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
        "- Title must repeat the Topic exactly, without additions, rewriting, or a year that is absent from the Topic.\n"
        "- H1 must be a concise, informative version of the Topic: use its primary part before a colon and avoid subtitles.\n"
        f"- Country/geo: {geo}\n"
        f"- Language: {language}\n"
        f"- Target words: {target_words or 'not specified'}\n"
        f"- Include TOC-related headings: {'yes' if include_toc else 'no'}\n"
        f"- Include FAQ: {'yes' if include_faq else 'no'}\n"
        f"- Shortcode block context: {shortcode or 'none'}\n"
        "- Return plain article text only. Do not return JSON or Markdown fences.\n"
    )
    if competitor_brief:
        prompt += (
            "\n\nCompetitor research context:\n"
            f"{render_competitor_brief_for_prompt(competitor_brief)}\n"
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
        .order_by(models.PromptTemplate.created_at.desc(), models.PromptTemplate.updated_at.desc())
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

    if provider.provider_type == "dataforseo":
        return await validate_dataforseo_provider(provider)

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


async def validate_dataforseo_provider(provider: models.AiProvider) -> models.AiProvider:
    try:
        login, password = parse_dataforseo_credentials(provider)
        user_data_url = build_dataforseo_user_data_url(provider.endpoint_url)
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                user_data_url,
                auth=(login, password),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        provider.validation_status = "invalid"
        provider.validation_message = describe_dataforseo_error(exc)
        return provider

    status_code = int(payload.get("status_code") or 0) if isinstance(payload, dict) else 0
    if status_code != 20000:
        provider.validation_status = "invalid"
        provider.validation_message = describe_dataforseo_payload_error(payload)
        return provider

    task = first_dataforseo_task(payload)
    task_status = int(task.get("status_code") or status_code) if task else status_code
    if task_status != 20000:
        provider.validation_status = "invalid"
        provider.validation_message = describe_dataforseo_payload_error(payload)
        return provider

    account_login = login
    result = task.get("result") if task else None
    if isinstance(result, list) and result and isinstance(result[0], dict):
        account_login = str(result[0].get("login") or account_login)

    provider.validation_status = "valid"
    provider.validation_message = f"DataForSEO API connected. Login: {account_login}"
    return provider


def parse_dataforseo_credentials(provider: models.AiProvider) -> tuple[str, str]:
    raw_credentials = (provider.api_key or "").strip()
    if not raw_credentials:
        raise ValueError("DataForSEO API login and API password are not configured")

    if raw_credentials.startswith("{"):
        try:
            payload = json.loads(raw_credentials)
        except ValueError as exc:
            raise ValueError("DataForSEO credentials JSON is invalid") from exc
        login = str(payload.get("login") or "").strip()
        password = str(payload.get("password") or "").strip()
    else:
        if ":" not in raw_credentials:
            raise ValueError("DataForSEO credentials must use login:password format")
        login, password = (part.strip() for part in raw_credentials.split(":", 1))

    if not login or not password:
        raise ValueError("DataForSEO API login and API password are required")

    return login, password


def build_dataforseo_user_data_url(endpoint_url: str) -> str:
    clean_url = (endpoint_url or DATAFORSEO_DEFAULT_ENDPOINT).rstrip("/")
    if clean_url.endswith(DATAFORSEO_USER_DATA_PATH):
        return clean_url
    return f"{clean_url}{DATAFORSEO_USER_DATA_PATH}"


def build_dataforseo_locations_url(endpoint_url: str) -> str:
    clean_url = (endpoint_url or DATAFORSEO_DEFAULT_ENDPOINT).rstrip("/")
    if clean_url.endswith(DATAFORSEO_LOCATIONS_PATH):
        return clean_url
    return f"{clean_url}{DATAFORSEO_LOCATIONS_PATH}"


def extract_dataforseo_country_location_codes(payload: dict | object) -> dict[str, int]:
    if not isinstance(payload, dict):
        return {}
    task = first_dataforseo_task(payload)
    result = task.get("result") if task else None
    if not isinstance(result, list):
        return {}

    preferred: dict[str, int] = {}
    fallback: dict[str, int] = {}
    for location in result:
        if not isinstance(location, dict):
            continue
        country_code = str(location.get("country_iso_code") or "").strip().upper()
        try:
            location_code = int(location.get("location_code"))
        except (TypeError, ValueError):
            continue
        if not country_code:
            continue
        fallback.setdefault(country_code, location_code)
        if str(location.get("location_type") or "").strip().casefold() == "country":
            preferred[country_code] = location_code

    return {country_code: preferred.get(country_code, code) for country_code, code in fallback.items()}


async def get_dataforseo_country_location_code(provider: models.AiProvider, geo: str) -> int:
    login, password = parse_dataforseo_credentials(provider)
    endpoint = build_dataforseo_locations_url(provider.endpoint_url)
    cache_key = (endpoint, login)
    locations = DATAFORSEO_LOCATION_CACHE.get(cache_key)
    if locations is None:
        async with httpx.AsyncClient(timeout=45) as client:
            for attempt in range(3):
                try:
                    response = await client.get(
                        endpoint,
                        auth=(login, password),
                        headers={"Content-Type": "application/json"},
                    )
                    break
                except httpx.TransportError as exc:
                    if attempt == 2:
                        raise ValueError(
                            f"DataForSEO locations request failed after 3 attempts: {type(exc).__name__}"
                        ) from exc
                    await asyncio.sleep(attempt + 1)
        response.raise_for_status()
        payload = response.json()
        status_code = int(payload.get("status_code") or 0) if isinstance(payload, dict) else 0
        task = first_dataforseo_task(payload)
        task_status = int(task.get("status_code") or status_code) if task else status_code
        if status_code != 20000 or task_status != 20000:
            raise ValueError(describe_dataforseo_payload_error(payload))
        locations = extract_dataforseo_country_location_codes(payload)
        if not locations:
            raise ValueError("DataForSEO returned an empty Google locations catalog")
        DATAFORSEO_LOCATION_CACHE[cache_key] = locations

    country_code = DATAFORSEO_COUNTRY_ALIASES.get(geo.strip().upper(), geo.strip().upper())
    location_code = locations.get(country_code)
    if location_code is None:
        raise ValueError(f"DataForSEO has no Google country location for geo {country_code}")
    return location_code


def first_dataforseo_task(payload: dict) -> dict | None:
    tasks = payload.get("tasks")
    if isinstance(tasks, list) and tasks and isinstance(tasks[0], dict):
        return tasks[0]
    return None


def describe_dataforseo_payload_error(payload: dict | object) -> str:
    if not isinstance(payload, dict):
        return "DataForSEO returned an unexpected response"

    status_code = payload.get("status_code")
    status_message = payload.get("status_message")
    task = first_dataforseo_task(payload)
    if task:
        status_code = task.get("status_code") or status_code
        status_message = task.get("status_message") or status_message

    parts = ["DataForSEO validation failed", str(status_code or ""), str(status_message or "")]
    return ": ".join(part for part in parts if part).strip()[:500]


def describe_dataforseo_error(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError) and error.response.status_code == 401:
        return (
            "HTTP 401: DataForSEO rejected credentials. "
            "Use API password from DataForSEO API Access, not the dashboard password."
        )
    return describe_ai_provider_error(error)


def get_dataforseo_provider(db: Session) -> models.AiProvider:
    provider = db.scalar(
        select(models.AiProvider)
        .where(models.AiProvider.provider_type == "dataforseo")
        .where(models.AiProvider.is_active.is_(True))
        .order_by(models.AiProvider.validation_status.desc(), models.AiProvider.created_at.desc())
        .limit(1)
    )
    if not provider:
        raise ValueError("DataForSEO provider is not configured")
    return provider


async def call_dataforseo_google_serp(provider: models.AiProvider, keyword: str, geo: str, language: str) -> dict:
    login, password = parse_dataforseo_credentials(provider)
    endpoint = f"{(provider.endpoint_url or DATAFORSEO_DEFAULT_ENDPOINT).rstrip('/')}{DATAFORSEO_SERP_PATH}"
    location_code = await get_dataforseo_country_location_code(provider, geo)
    body = [
        {
            "keyword": keyword,
            "location_code": location_code,
            "language_code": language.lower(),
            "device": "desktop",
            "os": "windows",
        }
    ]
    async with httpx.AsyncClient(timeout=45) as client:
        for attempt in range(3):
            try:
                response = await client.post(endpoint, json=body, auth=(login, password), headers={"Content-Type": "application/json"})
                break
            except httpx.TransportError as exc:
                if attempt == 2:
                    raise ValueError(f"DataForSEO request failed after 3 attempts: {type(exc).__name__}") from exc
                await asyncio.sleep(attempt + 1)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        provider.validation_status = "invalid"
        provider.validation_message = describe_dataforseo_error(exc)
        provider.validated_at = datetime.now(timezone.utc)
        raise ValueError(provider.validation_message) from exc
    payload = response.json()
    status_code = int(payload.get("status_code") or 0) if isinstance(payload, dict) else 0
    task = first_dataforseo_task(payload)
    task_status = int(task.get("status_code") or status_code) if task else status_code
    if status_code != 20000 or task_status != 20000:
        raise ValueError(describe_dataforseo_payload_error(payload))
    provider.validation_status = "valid"
    provider.validation_message = "DataForSEO SERP API connected"
    provider.validated_at = datetime.now(timezone.utc)
    provider.last_used_at = datetime.now(timezone.utc)
    return payload


def extract_organic_serp_items(payload: dict) -> list[dict]:
    task = first_dataforseo_task(payload)
    if not task:
        return []
    result = task.get("result")
    if not isinstance(result, list) or not result:
        return []
    result_item = result[0] if isinstance(result[0], dict) else {}
    items = result_item.get("items")
    if not isinstance(items, list):
        return []
    organic_items: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("type") not in {"organic", "featured_snippet"}:
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        organic_items.append(
            {
                "position": int(item.get("rank_group") or item.get("rank_absolute") or len(organic_items) + 1),
                "url": url,
                "title": clean_text(item.get("title")),
                "snippet": clean_text(item.get("description") or item.get("snippet")),
            }
        )
    return organic_items


async def collect_competitor_serp_for_item(db: Session, item: models.ContentItem) -> models.ContentItem:
    task = db.get(models.GenerationTask, item.task_id)
    site = db.get(models.Site, item.site_id) if item.site_id else None
    if not task:
        raise ValueError("Generation task not found")
    queries = ensure_competitor_queries(db, item, task.geo, task.language)
    provider = get_dataforseo_provider(db)

    item.competitor_research_status = "collecting_serp"
    item.competitor_research_progress = 5
    item.competitor_research_error = None
    db.commit()

    for page in db.scalars(select(models.CompetitorPage).where(models.CompetitorPage.content_item_id == item.id)).all():
        db.delete(page)
    for result in db.scalars(select(models.CompetitorResult).where(models.CompetitorResult.content_item_id == item.id)).all():
        db.delete(result)
    item.competitor_brief = None
    item.competitor_brief_text = None
    db.flush()

    seen_urls: set[str] = set()
    total_results = 0
    for query_index, query in enumerate(queries, start=1):
        query.status = "collecting"
        db.commit()
        payload = await call_dataforseo_google_serp(provider, query.query, task.geo, task.language)
        added_for_query = 0
        for serp_item in extract_organic_serp_items(payload)[:COMPETITOR_RESULTS_PER_QUERY]:
            url = serp_item["url"]
            if is_own_domain(url, site):
                continue
            normalized_url = normalize_competitor_url(url)
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            db.add(
                models.CompetitorResult(
                    content_item_id=item.id,
                    query_id=query.id,
                    query_text=query.query,
                    position=serp_item["position"],
                    url=url,
                    normalized_url=normalized_url,
                    title=serp_item["title"],
                    snippet=serp_item["snippet"],
                    source_provider="dataforseo",
                    status="discovered",
                )
            )
            added_for_query += 1
            total_results += 1
        query.result_count = added_for_query
        query.status = "serp_collected"
        item.competitor_research_progress = 5 + int(query_index / len(queries) * 30)
        db.commit()

    item.competitor_research_status = "serp_collected" if total_results else "serp_empty"
    db.commit()
    db.refresh(item)
    return item


async def fetch_competitor_pages_for_item(db: Session, item: models.ContentItem) -> models.ContentItem:
    results = db.scalars(
        select(models.CompetitorResult)
        .where(models.CompetitorResult.content_item_id == item.id)
        .order_by(models.CompetitorResult.query_text.asc(), models.CompetitorResult.position.asc())
    ).all()
    if not results:
        raise ValueError("No competitor URLs collected")

    item.competitor_research_status = "fetching_pages"
    item.competitor_research_progress = 35
    db.commit()

    for page in db.scalars(select(models.CompetitorPage).where(models.CompetitorPage.content_item_id == item.id)).all():
        db.delete(page)
    db.flush()

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ContentGeneratorBot/1.0; +http://91.199.133.86)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    async with httpx.AsyncClient(timeout=25, follow_redirects=True, headers=headers) as client:
        for result_index, result in enumerate(results, start=1):
            page_data = {
                "title": None,
                "h1": None,
                "meta_description": None,
                "headings": [],
                "text_content": None,
                "tables": [],
                "lists": [],
                "faq": [],
                "word_count": 0,
            }
            http_status = None
            error_message = None
            try:
                response = await client.get(result.url)
                http_status = response.status_code
                result.status = "fetched" if response.status_code < 400 else "fetch_failed"
                if response.status_code < 400:
                    extractor = CompetitorHTMLExtractor()
                    extractor.feed(response.text[:MAX_COMPETITOR_PAGE_CHARS])
                    page_data = extractor.payload()
                else:
                    error_message = f"HTTP {response.status_code}"
            except Exception as exc:
                result.status = "fetch_failed"
                error_message = str(exc)[:500]

            db.add(
                models.CompetitorPage(
                    content_item_id=item.id,
                    competitor_result_id=result.id,
                    url=result.url,
                    http_status=http_status,
                    title=page_data["title"],
                    h1=page_data["h1"],
                    meta_description=page_data["meta_description"],
                    headings=page_data["headings"],
                    text_content=page_data["text_content"],
                    tables=page_data["tables"],
                    lists=page_data["lists"],
                    faq=page_data["faq"],
                    word_count=page_data["word_count"],
                    error_message=error_message,
                    fetched_at=datetime.now(timezone.utc),
                )
            )
            item.competitor_research_progress = 35 + int(result_index / len(results) * 55)
            db.commit()

    item.competitor_research_status = "pages_fetched"
    item.competitor_research_progress = 90
    db.commit()
    db.refresh(item)
    return item


def build_competitor_brief_for_item(db: Session, item: models.ContentItem) -> models.ContentItem:
    queries = db.scalars(
        select(models.CompetitorQuery)
        .where(models.CompetitorQuery.content_item_id == item.id)
        .order_by(models.CompetitorQuery.position.asc())
    ).all()
    results = db.scalars(
        select(models.CompetitorResult)
        .where(models.CompetitorResult.content_item_id == item.id)
        .order_by(models.CompetitorResult.query_text.asc(), models.CompetitorResult.position.asc())
    ).all()
    pages = db.scalars(
        select(models.CompetitorPage)
        .where(models.CompetitorPage.content_item_id == item.id)
        .order_by(models.CompetitorPage.word_count.desc())
    ).all()
    analyzable_pages = [
        page
        for page in pages
        if (page.http_status or 0) < 400 and (clean_text(page.text_content) or (page.headings or []))
    ]
    if not analyzable_pages:
        raise ValueError("No parsed competitor pages found")

    heading_counter: Counter[str] = Counter()
    heading_examples: dict[str, str] = {}
    for page in analyzable_pages:
        page_heading_keys: set[str] = set()
        for heading in page.headings or []:
            if not isinstance(heading, dict):
                continue
            text = clean_text(heading.get("text"))
            if not text:
                continue
            key = text.casefold()
            heading_examples.setdefault(key, text)
            page_heading_keys.add(key)
        heading_counter.update(page_heading_keys)

    # A subject becomes a recommendation only when it is present on a meaningful
    # share of the localized SERP pages. This prevents a country-specific block
    # (for example, license verification) from being invented when competitors do
    # not actually cover it.
    minimum_page_coverage = max(2, (len(analyzable_pages) + 3) // 4)
    confirmed_heading_keys = [
        key
        for key, count in heading_counter.most_common()
        if count >= minimum_page_coverage
    ][:14]
    common_headings = [heading_examples[key] for key in confirmed_heading_keys]
    topics_to_cover = common_headings[:8]
    content_gaps = [
        (
            f"Тема подтверждена {heading_counter[key]} из {len(analyzable_pages)} страниц конкурентов: "
            f"{heading_examples[key]}."
        )
        for key in confirmed_heading_keys
        if heading_counter[key] < len(analyzable_pages)
    ][:8]

    competitor_summaries = []
    for page in analyzable_pages[:12]:
        page_headings = [
            clean_text(heading.get("text"))
            for heading in (page.headings or [])
            if isinstance(heading, dict)
        ][:8]
        competitor_summaries.append(
            {
                "url": page.url,
                "title": page.title,
                "h1": page.h1,
                "word_count": page.word_count,
                "http_status": page.http_status,
                "headings": page_headings,
                "tables_found": len(page.tables or []),
                "lists_found": len(page.lists or []),
                "faq_items_found": len(page.faq or []),
            }
        )

    brief = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_version": 2,
        "analysis_basis": "localized_competitor_evidence_only",
        "topic": item.topic,
        "geo": item.task.geo if item.task else None,
        "language": item.task.language if item.task else None,
        "analyzed_pages_count": len(analyzable_pages),
        "minimum_page_coverage": minimum_page_coverage,
        "search_queries": [query.query for query in queries],
        "competitor_urls": [result.url for result in results],
        "competitor_summary": competitor_summaries,
        "common_headings": common_headings,
        "content_gaps": content_gaps,
        "topics_to_cover": topics_to_cover,
        # Kept for compatibility with existing prompt-template placeholders.
        # Values are observed competitor topics, not invented "missing" blocks.
        "missing_blocks_to_cover": topics_to_cover,
        "notes": [
            "Использовать конкурентов только как исследовательский контекст.",
            "Не копировать и не делать близкий перефраз.",
            "Добавлять смысловые блоки только при подтверждении несколькими конкурентами текущего гео.",
            "Не добавлять проверку лицензии, если эта тема не подтверждена несколькими конкурентами.",
            "Факты, бренды, лицензии и юридические утверждения проверять перед публикацией.",
        ],
    }
    item.competitor_brief = brief
    item.competitor_brief_text = render_competitor_brief_for_prompt(brief)
    item.competitor_research_status = "brief_ready"
    item.competitor_research_progress = 100
    item.competitor_research_error = None
    db.commit()
    db.refresh(item)
    return item


async def collect_competitor_research_for_item(db: Session, item: models.ContentItem) -> models.ContentItem:
    item.competitor_research_status = "queued"
    item.competitor_research_progress = 1
    item.competitor_research_error = None
    db.commit()
    await collect_competitor_serp_for_item(db, item)
    await fetch_competitor_pages_for_item(db, item)
    build_competitor_brief_for_item(db, item)
    db.refresh(item)
    return item


def render_competitor_brief_for_prompt(brief: dict | None) -> str:
    if not brief:
        return "No competitor research was collected."
    competitor_lines = []
    for competitor in brief.get("competitor_summary", [])[:12]:
        if not isinstance(competitor, dict):
            continue
        headings = competitor.get("headings") or []
        competitor_lines.append(
            "\n".join(
                [
                    f"- URL: {competitor.get('url')}",
                    f"  Title/H1: {competitor.get('title') or competitor.get('h1') or 'not extracted'}",
                    f"  Words: {competitor.get('word_count') or 0}; tables: {competitor.get('tables_found') or 0}; lists: {competitor.get('lists_found') or 0}; FAQ-like items: {competitor.get('faq_items_found') or 0}",
                    f"  Headings: {', '.join(str(item) for item in headings[:8]) or 'not extracted'}",
                ]
            )
        )
    sections = [
        "Search queries:\n" + "\n".join(f"- {item}" for item in brief.get("search_queries", [])),
        "Competitor URLs:\n" + "\n".join(f"- {item}" for item in brief.get("competitor_urls", [])[:20]),
        "Competitor summary:\n" + "\n".join(competitor_lines),
        "Common competitor headings:\n" + "\n".join(f"- {item}" for item in brief.get("common_headings", [])),
        "Content gaps to close:\n" + "\n".join(f"- {item}" for item in brief.get("content_gaps", [])),
        "Competitor-confirmed topics to consider:\n" + "\n".join(f"- {item}" for item in brief.get("topics_to_cover", [])),
        (
            "Rules:\n"
            "- Do not copy competitors.\n"
            "- Do not closely paraphrase competitors.\n"
            "- Use this only as research context.\n"
            "- Do not invent a content gap from a generic niche checklist.\n"
            "- Do not add license-verification content unless it is listed among the competitor-confirmed topics.\n"
            "- Build an original structure and mark facts that need editorial verification."
        ),
    ]
    return "\n\n".join(section for section in sections if section.strip())[:20_000]


def prompt_context_from_brief(brief: dict | None) -> dict[str, str]:
    if not brief:
        return {
            "search_queries": "No competitor research collected.",
            "competitor_urls": "No competitor research collected.",
            "competitor_summary": "No competitor research collected.",
            "content_gaps": "No competitor research collected.",
            "common_headings": "No competitor research collected.",
            "missing_blocks_to_cover": "No competitor research collected.",
        }
    return {
        "search_queries": "\n".join(f"- {item}" for item in brief.get("search_queries", [])) or "No search queries collected.",
        "competitor_urls": "\n".join(f"- {item}" for item in brief.get("competitor_urls", [])[:20]) or "No competitor URLs collected.",
        "competitor_summary": render_competitor_brief_for_prompt(brief),
        "content_gaps": "\n".join(f"- {item}" for item in brief.get("content_gaps", [])) or "No content gaps detected.",
        "common_headings": "\n".join(f"- {item}" for item in brief.get("common_headings", [])) or "No common headings detected.",
        "missing_blocks_to_cover": "\n".join(f"- {item}" for item in brief.get("topics_to_cover", [])) or "No competitor-confirmed topics detected.",
    }


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
    title = topic.strip()
    h1 = concise_h1_from_topic(topic)
    slug = normalize_slug(topic)
    description = f"Useful guide about {topic} for {geo} readers in {language}."
    headings = [
        h1,
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


def create_generation_task(db: Session, payload: GenerationTaskCreate, created_by_user_id: str | None = None) -> models.GenerationTask:
    clean_topics = [topic.strip() for topic in payload.topics if topic.strip()]
    prompt_template = compose_prompt_with_base(db, payload.prompt_template)
    site = db.get(models.Site, payload.site_id) if payload.site_id else None
    automatic_title = (
        f"{site.name} · {len(clean_topics)} тем · {payload.language.upper()}-{payload.geo.upper()}"
        if site
        else f"Без проекта · {len(clean_topics)} тем · {payload.language.upper()}-{payload.geo.upper()}"
    )
    task = models.GenerationTask(
        title=payload.title.strip() if payload.title and payload.title.strip() else automatic_title,
        created_by_user_id=created_by_user_id,
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
        collect_competitors=payload.collect_competitors,
        status="draft" if payload.save_as_draft else ("research_queries_ready" if payload.collect_competitors else "created"),
    )
    db.add(task)
    db.flush()

    for index, topic in enumerate(clean_topics, start=1):
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
            competitor_research_status="queries_ready" if payload.collect_competitors else "not_requested",
            idempotency_key=f"{payload.geo.lower()}-{payload.language.lower()}-{slugify(topic)}-{index}-{uuid.uuid4().hex[:8]}",
        )
        db.add(item)
        db.flush()
        if payload.collect_competitors:
            ensure_competitor_queries(db, item, payload.geo, payload.language)

    db.commit()
    db.refresh(task)
    return task


def generate_task_items(db: Session, task: models.GenerationTask) -> models.GenerationTask:
    mutable_items = [item for item in task.items if item.status not in {"scheduled", "retry_scheduled", "publication_paused", "publishing", "published"}]
    if not mutable_items:
        raise ValueError("Task has no content that can be generated")
    task.status = "generating"
    db.commit()
    provider = db.get(models.AiProvider, task.ai_provider_id) if task.ai_provider_id else None
    site = db.get(models.Site, task.site_id) if task.site_id else None
    try:
        for item in mutable_items:
            item.status = "generating"
            item.generation_progress = 15
            item.generation_error = None
            db.commit()
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
                        competitor_brief=item.competitor_brief,
                    )
                )
                item.slug = item.generated_json["pages"][0]["slug"]
                item.word_count = count_words(item.generated_json)
            item.generation_progress = 90
            item.generation_prompt_name = task.prompt_template_name
            item.generated_at = datetime.now(timezone.utc)
            item.status = "generated"
            item.generation_progress = 100
            db.commit()
        task.status = "generated"
    except Exception as exc:
        db.rollback()
        for item in mutable_items:
            if item.status in {"generation_queued", "generating"}:
                item.status = "generation_failed"
                item.generation_error = f"{type(exc).__name__}: {exc}"[:500]
        task.status = "generation_failed"
        db.commit()
        raise
    db.commit()
    db.refresh(task)
    return task


def run_task_pipeline(db: Session, task: models.GenerationTask, competitor_attempts: int = 2) -> models.GenerationTask:
    locked_statuses = {"scheduled", "retry_scheduled", "publication_paused", "publishing", "published"}
    item_ids = [item.id for item in task.items if item.status not in locked_statuses]
    if not item_ids:
        raise ValueError("Task has no content that can be generated")

    task.status = "generating"
    db.commit()
    failed_items = 0

    for item_id in item_ids:
        item = db.get(models.ContentItem, item_id)
        if not item:
            continue

        if task.collect_competitors and not item.competitor_brief:
            research_error: Exception | None = None
            for _ in range(max(1, competitor_attempts)):
                try:
                    asyncio.run(collect_competitor_research_for_item(db, item))
                    research_error = None
                    break
                except Exception as exc:
                    research_error = exc
                    db.rollback()
                    item = db.get(models.ContentItem, item_id)
                    if not item:
                        break
                    item.competitor_research_status = "research_failed"
                    item.competitor_research_error = f"{type(exc).__name__}: {exc}"[:500]
                    db.commit()

            if research_error is not None:
                item = db.get(models.ContentItem, item_id)
                if item:
                    item.status = "generation_failed"
                    item.generation_error = f"Не удалось собрать конкурентов: {type(research_error).__name__}: {research_error}"[:500]
                    db.commit()
                failed_items += 1
                continue

        item = db.get(models.ContentItem, item_id)
        if not item:
            continue
        try:
            generate_content_item(db, item)
        except Exception:
            failed_items += 1

    task = db.get(models.GenerationTask, task.id)
    if not task:
        raise ValueError("Generation task not found")
    task.status = "generation_failed" if failed_items else "generated"
    db.commit()
    db.refresh(task)
    return task


def generate_content_item(db: Session, item: models.ContentItem) -> models.ContentItem:
    if item.status in {"scheduled", "retry_scheduled", "publication_paused", "publishing", "published"}:
        raise ValueError(f"Content in status '{item.status}' cannot be regenerated")
    task = db.get(models.GenerationTask, item.task_id)
    if not task:
        raise ValueError("Generation task not found")
    provider = db.get(models.AiProvider, task.ai_provider_id) if task.ai_provider_id else None
    site = db.get(models.Site, task.site_id) if task.site_id else None
    item.status = "generating"
    item.generation_progress = 15
    item.generation_error = None
    task.status = "generating"
    db.commit()
    try:
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
                    competitor_brief=item.competitor_brief,
                )
            )
            item.slug = item.generated_json["pages"][0]["slug"]
            item.word_count = count_words(item.generated_json)
        item.generation_progress = 90
        item.generation_prompt_name = task.prompt_template_name
        item.generated_at = datetime.now(timezone.utc)
        item.status = "generated"
        item.generation_progress = 100
        active_items = [task_item for task_item in task.items if task_item.id != item.id and task_item.status in {"generation_queued", "generating"}]
        failed_items = [task_item for task_item in task.items if task_item.id != item.id and task_item.status == "generation_failed"]
        task.status = "generating" if active_items else "generation_failed" if failed_items else "generated"
        db.commit()
        db.refresh(item)
        return item
    except Exception as exc:
        db.rollback()
        failed_item = db.get(models.ContentItem, item.id)
        failed_task = db.get(models.GenerationTask, item.task_id)
        if failed_item:
            failed_item.status = "generation_failed"
            failed_item.generation_error = f"{type(exc).__name__}: {exc}"[:500]
        if failed_task:
            failed_task.status = "generation_failed"
        db.commit()
        raise


def schedule_campaign(db: Session, payload: PublicationCampaignCreate) -> models.PublicationCampaign:
    site = db.get(models.Site, payload.site_id)
    if not site or not site.is_active:
        raise ValueError("Publication site not found or inactive")
    item_ids = list(dict.fromkeys(payload.content_item_ids))
    if len(item_ids) != len(payload.content_item_ids):
        raise ValueError("Campaign contains duplicate content items")
    items = db.scalars(select(models.ContentItem).where(models.ContentItem.id.in_(item_ids))).all()
    items_by_id = {item.id: item for item in items}
    if len(items_by_id) != len(item_ids):
        raise ValueError("One or more content items were not found")
    for item_id in item_ids:
        item = items_by_id[item_id]
        if item.site_id != payload.site_id:
            raise ValueError("Campaign can include only content from the selected site")
        if item.status != "approved":
            raise ValueError("Campaign can include only approved content")
        validate_content_for_publication(item)

    task_ids = {item.task_id for item in items}
    task_created_rows = db.execute(
        select(models.GenerationTask.id, models.GenerationTask.created_at)
        .where(models.GenerationTask.id.in_(task_ids))
    ).all()
    task_created_at = {task_id: created_at for task_id, created_at in task_created_rows}
    ordered_items = sorted(
        items,
        key=lambda item: (task_created_at.get(item.task_id, item.created_at), item.created_at, item.id),
    )
    section_queues: dict[str, list[models.ContentItem]] = {}
    for item in ordered_items:
        section_queues.setdefault(item.section_id or "__without_section__", []).append(item)
    publication_order: list[models.ContentItem] = []
    while any(section_queues.values()):
        for section_items in section_queues.values():
            if section_items:
                publication_order.append(section_items.pop(0))

    campaign = models.PublicationCampaign(
        name=payload.name,
        site_id=payload.site_id,
        start_at=payload.start_at,
        interval_minutes=payload.interval_minutes,
        items_per_run=payload.items_per_run,
        status="active",
    )
    db.add(campaign)
    db.flush()
    for index, item in enumerate(publication_order):
        item.publication_campaign_id = campaign.id
        item.status = "scheduled"
        publication_slot = index // payload.items_per_run
        item.scheduled_at = payload.start_at + timedelta(minutes=payload.interval_minutes * publication_slot)
    db.commit()
    db.refresh(campaign)
    return campaign


def approve_and_schedule_item(db: Session, item: models.ContentItem) -> models.PublicationCampaign:
    if item.status not in {"generated", "rejected", "approved"}:
        raise ValueError(f"Content in status '{item.status}' cannot be sent to publication")
    if not item.site_id:
        raise ValueError("Select a project before publication")
    if not item.section_id:
        raise ValueError("Select a menu item before publication")
    section = db.get(models.Section, item.section_id)
    if not section or section.site_id != item.site_id:
        raise ValueError("Menu item does not belong to the content site")
    validate_content_for_publication(item)
    item.status = "approved"
    db.flush()
    return schedule_campaign(
        db,
        PublicationCampaignCreate(
            name=f"Dashboard · {item.topic}"[:180],
            site_id=item.site_id,
            content_item_ids=[item.id],
            start_at=datetime.now(timezone.utc),
            interval_minutes=1440,
            items_per_run=1,
        ),
    )


def update_campaign_status(db: Session, campaign: models.PublicationCampaign, action: str) -> models.PublicationCampaign:
    items = db.scalars(
        select(models.ContentItem)
        .where(models.ContentItem.publication_campaign_id == campaign.id)
        .order_by(models.ContentItem.scheduled_at.asc(), models.ContentItem.created_at.asc())
    ).all()
    if action == "pause":
        if campaign.status != "active":
            raise ValueError("Only an active campaign can be paused")
        campaign.status = "paused"
        for item in items:
            if item.status in {"scheduled", "retry_scheduled"}:
                item.status = "publication_paused"
    elif action == "resume":
        if campaign.status != "paused":
            raise ValueError("Only a paused campaign can be resumed")
        campaign.status = "active"
        campaign_start = campaign.start_at
        if campaign_start.tzinfo is None:
            campaign_start = campaign_start.replace(tzinfo=timezone.utc)
        resume_at = max(datetime.now(timezone.utc), campaign_start)
        paused_items = [item for item in items if item.status == "publication_paused"]
        for index, item in enumerate(paused_items):
            item.status = "scheduled"
            item.scheduled_at = resume_at + timedelta(minutes=campaign.interval_minutes * index)
    elif action == "stop":
        if campaign.status not in {"active", "paused"}:
            raise ValueError("Only an active or paused campaign can be stopped")
        campaign.status = "stopped"
        for item in items:
            if item.status in {"scheduled", "retry_scheduled", "publication_paused"}:
                item.status = "approved"
                item.scheduled_at = None
    else:
        raise ValueError("Unknown campaign action")
    db.commit()
    db.refresh(campaign)
    return campaign


def refresh_campaign_status(db: Session, campaign_id: str | None) -> None:
    if not campaign_id:
        return
    campaign = db.get(models.PublicationCampaign, campaign_id)
    if not campaign or campaign.status not in {"active", "paused"}:
        return
    pending = db.scalar(
        select(func.count(models.ContentItem.id))
        .where(models.ContentItem.publication_campaign_id == campaign_id)
        .where(models.ContentItem.status.in_(["scheduled", "retry_scheduled", "publication_paused", "publishing"]))
    ) or 0
    if pending == 0:
        failed = db.scalar(
            select(func.count(models.ContentItem.id))
            .where(models.ContentItem.publication_campaign_id == campaign_id)
            .where(models.ContentItem.status == "publication_failed")
        ) or 0
        campaign.status = "completed_with_errors" if failed else "completed"


def get_dashboard(db: Session) -> dict:
    total_tasks = db.scalar(
        select(func.count(models.GenerationTask.id)).where(models.GenerationTask.archived_at.is_(None))
    ) or 0
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

    active_tasks = db.scalars(
        select(models.GenerationTask)
        .where(models.GenerationTask.archived_at.is_(None))
        .order_by(models.GenerationTask.created_at.desc())
        .limit(6)
    ).all()
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
    try:
        validate_content_for_publication(item)
    except ValueError as exc:
        db.add(
            models.PublicationLog(
                content_item_id=item.id,
                endpoint_url=site.publication_endpoint,
                request_payload=item.generated_json,
                error_message=str(exc),
            )
        )
        item.status = "publication_failed"
        refresh_campaign_status(db, item.publication_campaign_id)
        db.commit()
        return
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
            item.status = "publication_failed"
            item.scheduled_at = None
        else:
            item.status = "publication_failed"
        refresh_campaign_status(db, item.publication_campaign_id)
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
        item.status = "publication_failed"
        item.scheduled_at = None
        refresh_campaign_status(db, item.publication_campaign_id)
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
        "menu_type": section.menu_type,
    }
    payload["publication_target"] = publication_target
    for page in payload.get("pages", []):
        if isinstance(page, dict):
            page["sectionId"] = section.external_id
            page["sectionPath"] = section.path
    return payload
