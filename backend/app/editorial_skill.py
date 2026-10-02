"""Editorial instructions shared by all article generation requests."""

from pathlib import Path


AI_NEUTRALIZER_MARKER = "=== AI NEUTRALIZER EDITORIAL SKILL ==="
AI_NEUTRALIZER_TEXT = (
    Path(__file__).parent / "data" / "ai_neutralizer.md"
).read_text(encoding="utf-8").strip()


def prepend_editorial_skill(prompt: str) -> str:
    return (
        f"{AI_NEUTRALIZER_MARKER}\n"
        f"{AI_NEUTRALIZER_TEXT}\n"
        "=== END AI NEUTRALIZER EDITORIAL SKILL ===\n\n"
        "Применяй скилл как редакционную основу при подготовке и написании текста. "
        "Примеры из скилла иллюстрируют подачу, а не подтверждают факты для текущей статьи. "
        "Конкретное ТЗ ниже задаёт тему, язык, GEO, обязательные блоки и формат ответа. "
        "Внутренние проверки скилла выполняй без вывода в статью. "
        "Для дополнительного research используй доступные инструменты поиска. "
        "Если поиск недоступен, опирайся на предоставленные источники и факты; "
        "не выдумывай данные, ссылки и результаты проверки и не утверждай, "
        "что выполнил поиск. При нехватке подтверждений сузь утверждение "
        "или обозначь ограничение.\n\n"
        "=== ТЗ И КОНТЕКСТ ГЕНЕРАЦИИ ===\n"
        f"{prompt}"
    )
