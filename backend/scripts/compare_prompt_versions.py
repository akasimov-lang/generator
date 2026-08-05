import json
import re
from collections import Counter

from sqlalchemy import select

from app import models
from app.db import SessionLocal


TASK_TITLES = {
    "v4": "DE обзорник: Gemini v4 prompt test",
    "v5": "DE обзорник: Gemini v5 prompt test",
}
WORD_RE = re.compile(r"[\wÀ-ÿА-Яа-яЁё-]+", re.UNICODE)
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
LICENSE_TERMS = ("lizenz", "ggl", "oasis", "lugas", "glüstv", "whitelist")
TESTING_CLAIMS = (
    "wir haben getestet",
    "wir testeten",
    "von uns getestet",
    "unsere experten haben geprüft",
    "unsere experten testeten",
)


def strings_from_value(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in strings_from_value(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in strings_from_value(item)]
    return []


def item_metrics(item: models.ContentItem, target_words: int) -> dict:
    page = item.generated_json["pages"][0]
    blocks = page.get("content", {}).get("blocks", [])
    public_text = "\n".join(
        text
        for block in blocks
        if block.get("type") != "toc"
        for text in strings_from_value(block.get("data"))
    )
    lowered = public_text.casefold()
    headers = [
        block.get("data", {})
        for block in blocks
        if block.get("type") == "header" and isinstance(block.get("data"), dict)
    ]
    h1 = next((str(header.get("text") or "") for header in headers if header.get("level") == 1), "")
    h2 = [str(header.get("text") or "") for header in headers if header.get("level") == 2]
    paragraphs = [
        str(block.get("data", {}).get("text") or "")
        for block in blocks
        if block.get("type") == "paragraph" and isinstance(block.get("data"), dict)
    ]
    paragraph_lengths = [len(WORD_RE.findall(text)) for text in paragraphs if text]
    faq_questions = sum(
        1
        for block in blocks
        if block.get("type") == "faq"
        for text in strings_from_value(block.get("data"))
        if text.strip()
    )
    block_types = Counter(str(block.get("type") or "unknown") for block in blocks)
    meta_description = str(page.get("description") or "")
    word_delta_percent = round(abs(item.word_count - target_words) / target_words * 100, 1)
    score_parts = {
        "target_length": 20 if word_delta_percent <= 15 else 10 if word_delta_percent <= 25 else 0,
        "h2_structure": 15 if 6 <= len(h2) <= 10 else 8 if 4 <= len(h2) <= 12 else 0,
        "meta_length": 10 if 140 <= len(meta_description) <= 160 else 5 if 120 <= len(meta_description) <= 180 else 0,
        "title_exact": 10 if page.get("title") == item.topic else 0,
        "concise_h1": 10 if 3 <= len(WORD_RE.findall(h1)) <= 10 else 5 if len(WORD_RE.findall(h1)) <= 14 else 0,
        "no_public_urls": 10 if not URL_RE.search(public_text) else 0,
        "no_placeholders": 10 if "[muss geprüft" not in lowered else 0,
        "readable_paragraphs": 10 if paragraph_lengths and sum(paragraph_lengths) / len(paragraph_lengths) <= 120 else 0,
        "faq_present": 5 if block_types.get("faq", 0) else 0,
    }
    return {
        "topic": item.topic,
        "status": item.status,
        "words": item.word_count,
        "target_delta_percent": word_delta_percent,
        "title_exact": page.get("title") == item.topic,
        "meta_chars": len(meta_description),
        "h1": h1,
        "h1_words": len(WORD_RE.findall(h1)),
        "h2_count": len(h2),
        "h2": h2,
        "block_types": dict(block_types),
        "average_paragraph_words": round(sum(paragraph_lengths) / len(paragraph_lengths), 1) if paragraph_lengths else 0,
        "public_urls": len(URL_RE.findall(public_text)),
        "placeholders": lowered.count("[muss geprüft"),
        "license_term_mentions": sum(lowered.count(term) for term in LICENSE_TERMS),
        "testing_claims": sum(lowered.count(claim) for claim in TESTING_CLAIMS),
        "confirmed_competitor_topics": (item.competitor_brief or {}).get("topics_to_cover", []),
        "score": sum(score_parts.values()),
        "score_parts": score_parts,
    }


def main() -> None:
    db = SessionLocal()
    try:
        report: dict[str, object] = {"versions": {}, "competitor_input_equal": {}}
        tasks = {
            version: db.scalar(select(models.GenerationTask).where(models.GenerationTask.title == title))
            for version, title in TASK_TITLES.items()
        }
        if not all(tasks.values()):
            raise ValueError("One or both comparison tasks were not found")

        items_by_version = {
            version: {item.topic: item for item in task.items}
            for version, task in tasks.items()
        }
        shared_topics = sorted(set(items_by_version["v4"]) & set(items_by_version["v5"]))
        for version, task in tasks.items():
            metrics = [item_metrics(items_by_version[version][topic], task.target_words or 2000) for topic in shared_topics]
            report["versions"][version] = {
                "task_id": task.id,
                "status": task.status,
                "prompt": task.prompt_template_name,
                "average_words": round(sum(item["words"] for item in metrics) / len(metrics), 1),
                "average_score": round(sum(item["score"] for item in metrics) / len(metrics), 1),
                "total_license_term_mentions": sum(item["license_term_mentions"] for item in metrics),
                "total_testing_claims": sum(item["testing_claims"] for item in metrics),
                "items": metrics,
            }

        for topic in shared_topics:
            v4_urls = set((items_by_version["v4"][topic].competitor_brief or {}).get("competitor_urls", []))
            v5_urls = set((items_by_version["v5"][topic].competitor_brief or {}).get("competitor_urls", []))
            report["competitor_input_equal"][topic] = {
                "equal": v4_urls == v5_urls,
                "v4_urls": len(v4_urls),
                "v5_urls": len(v5_urls),
            }
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
