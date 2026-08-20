from pathlib import Path

from sqlalchemy import select

from app import models
from app.db import SessionLocal


TARGET_PROMPT_NAME = "Промпт тест 1 v6"
SOURCE_PROMPT_NAMES = ("Промпт тест 1 v5", "Промпт тест 1 v4")
PROMPT_FILE = Path(__file__).resolve().parents[2] / "prompts" / "prompt_test_1_v6.txt"


def load_v6_content() -> str:
    content = PROMPT_FILE.read_text(encoding="utf-8").strip()
    if not content.startswith("Рабочий промпт для конкретной задачи. Версия 6."):
        raise ValueError(f"Unexpected V6 prompt content in {PROMPT_FILE}")
    return content


def upsert_v6_prompt(db) -> tuple[models.PromptTemplate, bool]:
    content = load_v6_content()
    prompt = db.scalar(select(models.PromptTemplate).where(models.PromptTemplate.name == TARGET_PROMPT_NAME))
    created = prompt is None
    if prompt is None:
        source_prompt = None
        for source_name in SOURCE_PROMPT_NAMES:
            source_prompt = db.scalar(select(models.PromptTemplate).where(models.PromptTemplate.name == source_name))
            if source_prompt:
                break
        prompt = models.PromptTemplate(
            site_id=source_prompt.site_id if source_prompt else None,
            name=TARGET_PROMPT_NAME,
            content=content,
            is_default=False,
        )
        db.add(prompt)
    else:
        prompt.content = content
        prompt.is_default = False
    db.commit()
    db.refresh(prompt)
    return prompt, created


def main() -> None:
    db = SessionLocal()
    try:
        prompt, created = upsert_v6_prompt(db)
        action = "Created" if created else "Updated"
        print(f"{action} prompt: {prompt.id} ({prompt.name})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
