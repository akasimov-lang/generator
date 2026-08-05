import copy

from sqlalchemy import delete, select

from app import models
from app.db import SessionLocal
from app.schemas import GenerationTaskCreate
from app.services import build_competitor_brief_for_item, compose_prompt_with_base, create_generation_task
from app.worker import generate_task_content_job


SOURCE_PROMPT_NAME = "Промпт тест 1 v4"
TARGET_PROMPT_NAME = "Промпт тест 1 v5"
SOURCE_TASK_TITLE = "DE обзорник: Gemini v4 prompt test"
TARGET_TASK_TITLE = "DE обзорник: Gemini v5 prompt test"


def build_v5_content(v4_content: str) -> str:
    content = v4_content.replace("Версия 4.", "Версия 5.", 1)
    content = content.replace(
        "- Блоки, которые требуется раскрыть лучше: {{MISSING_BLOCKS_TO_COVER}}",
        "- Темы, подтверждённые несколькими конкурентами текущего гео: {{MISSING_BLOCKS_TO_COVER}}",
    )
    content = content.replace(
        "- Не сообщай читателю о Google, выдаче, конкурентном анализе или просмотренных страницах.",
        """- Не сообщай читателю о Google, выдаче, конкурентном анализе или просмотренных страницах.
- Brief не является универсальным чек-листом ниши: используй только темы, подтверждённые несколькими конкурентами текущего гео.
- Если тема отсутствует у конкурентов или встречается единично, не объявляй её content gap и не добавляй отдельный раздел.
- Не добавляй раздел о проверке лицензии, если проверка лицензии не указана среди подтверждённых конкурентами тем.""",
    )
    old_intent_block = """Разделение близких интентов:
- Для темы «beste» объясняй критерии сравнения и порядок выбора. Не создавай рейтинг операторов без проверенного набора данных.
- Для темы «legal/legale/GGL» концентрируйся на проверке правового статуса, лицензии, ограничениях и действиях пользователя до регистрации.
- Для темы «neue» объясняй, как проверить заявленную новизну, актуальность лицензии и условия нового предложения. Не называй оператор новым без подтверждённой даты.
- Для темы «Spielotheken/Slots» концентрируйся на слотах, механике, лимитах, RTP как понятии, платежах и защите игрока.
- Для темы «sicher/erkennen» создавай практическую инструкцию распознавания рисков, красных флагов и последовательной проверки."""
    new_intent_block = """Динамическая адаптация интента и страны:
- Ниша всегда одна — онлайн-казино; не меняй нишу, но адаптируй лексику, пользовательские ожидания и структуру под {{GEO}} и {{LANGUAGE}}.
- Определяй тип страницы по смыслу {{TOPIC}} на выбранном языке, а не по фиксированному списку немецких слов.
- Не переноси требования, регуляторов, термины и обязательные разделы из одной страны в другую.
- Сравнительную тему раскрывай через критерии выбора без вымышленного рейтинга; тему о новых казино — через признаки новизны; тему безопасности — через подтверждённые конкурентами риски и действия.
- Юридические сведения и проверку лицензии включай только тогда, когда они подтверждены несколькими конкурентами текущего гео; единичное упоминание не считается основанием для отдельного блока."""
    if old_intent_block not in content:
        raise ValueError("Expected v4 intent block was not found")
    content = content.replace(old_intent_block, new_intent_block)
    content = content.replace(
        "- Для Германии раскрывай только релевантные теме аспекты GGL, KYC, OASIS/LUGAS, платежей, лимитов и Spielerschutz; не вставляй весь набор автоматически в каждую статью.",
        "- Для выбранного гео раскрывай только подтверждённые конкурентами локальные аспекты; не вставляй автоматически регуляторов, лицензии и правила другой страны.",
    )
    content = content.replace(
        "- Если динамический или юридически значимый факт не подтверждён входными данными, сформулируй раздел без конкретного спорного значения либо не включай этот факт.",
        "- Спорные, динамические и юридически значимые утверждения можно включать без отдельной проверки фактов и без служебных предупреждений в тексте.",
    )
    content = content.replace(
        "Формат ответа:\n",
        """Жёсткий запрет служебных пометок в публичном тексте — это правило имеет приоритет над базовым промптом:
- Не выводи замечания, placeholders и маркеры необходимости проверки ни на каком языке.
- Запрещены любые варианты конструкций вроде [Muss geprüft werden], [Needs verification], [Требует проверки], [Проверить редактору], TODO, TBD и аналогичные формулировки, в том числе внутри таблиц, списков и FAQ.
- Не используй placeholders операторов и брендов: [Anbieter 1], [Provider 1], [Оператор 1] и их аналоги.
- Спорные, динамические и неподтверждённые утверждения указывать можно без проверки фактов; формулируй их как обычный публичный текст без предупреждений и маркеров проверки.
- Если нет проверенных данных об операторах, не создавай вымышленные карточки и описания операторов; вместо них используй обезличенную таблицу критериев выбора.
- Не создавай замечания о необходимости проверки фактов даже в служебном блоке Editor Check.

Формат ответа:
""",
        1,
    )
    content = content.replace("- Неподтверждённые факты в публичном тексте: нет / перечислить\n", "")
    content = content.replace("- Legal-риск: OK / Risiko\n", "")
    content = content.replace("- Следующая проверка редактора перед публикацией: ...\n", "")
    return content


def clone_competitor_research(db, source_item: models.ContentItem, target_item: models.ContentItem) -> None:
    db.execute(delete(models.CompetitorQuery).where(models.CompetitorQuery.content_item_id == target_item.id))

    query_map: dict[str, models.CompetitorQuery] = {}
    source_queries = db.scalars(
        select(models.CompetitorQuery)
        .where(models.CompetitorQuery.content_item_id == source_item.id)
        .order_by(models.CompetitorQuery.position.asc())
    ).all()
    for source in source_queries:
        target = models.CompetitorQuery(
            content_item_id=target_item.id,
            query=source.query,
            position=source.position,
            status=source.status,
            result_count=source.result_count,
        )
        db.add(target)
        db.flush()
        query_map[source.id] = target

    result_map: dict[str, models.CompetitorResult] = {}
    source_results = db.scalars(
        select(models.CompetitorResult)
        .where(models.CompetitorResult.content_item_id == source_item.id)
        .order_by(models.CompetitorResult.query_text.asc(), models.CompetitorResult.position.asc())
    ).all()
    for source in source_results:
        target = models.CompetitorResult(
            content_item_id=target_item.id,
            query_id=query_map[source.query_id].id if source.query_id in query_map else None,
            query_text=source.query_text,
            position=source.position,
            url=source.url,
            normalized_url=source.normalized_url,
            title=source.title,
            snippet=source.snippet,
            source_provider=source.source_provider,
            status=source.status,
        )
        db.add(target)
        db.flush()
        result_map[source.id] = target

    source_pages = db.scalars(
        select(models.CompetitorPage).where(models.CompetitorPage.content_item_id == source_item.id)
    ).all()
    for source in source_pages:
        if source.competitor_result_id not in result_map:
            continue
        db.add(
            models.CompetitorPage(
                content_item_id=target_item.id,
                competitor_result_id=result_map[source.competitor_result_id].id,
                url=source.url,
                http_status=source.http_status,
                title=source.title,
                h1=source.h1,
                meta_description=source.meta_description,
                headings=copy.deepcopy(source.headings or []),
                text_content=source.text_content,
                tables=copy.deepcopy(source.tables or []),
                lists=copy.deepcopy(source.lists or []),
                faq=copy.deepcopy(source.faq or []),
                word_count=source.word_count,
                error_message=source.error_message,
                fetched_at=source.fetched_at,
            )
        )
    db.flush()
    build_competitor_brief_for_item(db, target_item)


def main() -> None:
    db = SessionLocal()
    try:
        source_prompt = db.scalar(
            select(models.PromptTemplate).where(models.PromptTemplate.name == SOURCE_PROMPT_NAME)
        )
        source_task = db.scalar(
            select(models.GenerationTask).where(models.GenerationTask.title == SOURCE_TASK_TITLE)
        )
        if not source_prompt or not source_task:
            raise ValueError("Source v4 prompt or task was not found")

        v5_content = build_v5_content(source_prompt.content)
        target_prompt = db.scalar(
            select(models.PromptTemplate).where(models.PromptTemplate.name == TARGET_PROMPT_NAME)
        )
        if not target_prompt:
            target_prompt = models.PromptTemplate(
                site_id=source_prompt.site_id,
                name=TARGET_PROMPT_NAME,
                content=v5_content,
                is_default=False,
            )
            db.add(target_prompt)
        else:
            target_prompt.content = v5_content
        existing_task = db.scalar(
            select(models.GenerationTask).where(models.GenerationTask.title == TARGET_TASK_TITLE)
        )
        if existing_task:
            existing_task.prompt_template_name = TARGET_PROMPT_NAME
            existing_task.prompt_template = compose_prompt_with_base(db, v5_content)
            db.commit()
            print(f"Updated prompt: {target_prompt.id}")
            print(f"Updated existing task snapshot: {existing_task.id} ({existing_task.status})")
            return
        db.flush()

        source_items = sorted(source_task.items, key=lambda item: item.created_at)
        target_task = create_generation_task(
            db,
            GenerationTaskCreate(
                title=TARGET_TASK_TITLE,
                geo=source_task.geo,
                language=source_task.language,
                topics=[item.topic for item in source_items],
                site_id=source_task.site_id,
                section_id=source_task.section_id,
                ai_provider_id=source_task.ai_provider_id,
                payload_mode=source_task.payload_mode,
                target_words=source_task.target_words,
                prompt_template_name=TARGET_PROMPT_NAME,
                prompt_template=v5_content,
                include_toc=True,
                include_faq=True,
                collect_competitors=True,
            ),
            created_by_user_id=source_task.created_by_user_id,
        )
        target_items = {item.topic: item for item in target_task.items}
        for source_item in source_items:
            clone_competitor_research(db, source_item, target_items[source_item.topic])
        target_task.status = "generation_queued"
        for item in target_task.items:
            item.status = "generation_queued"
            item.generation_progress = 1
        db.commit()
        generate_task_content_job.delay(target_task.id)
        print(f"Created prompt: {target_prompt.id}")
        print(f"Created and queued task: {target_task.id}")
        print(f"Cloned competitor research for {len(target_task.items)} topics")
    finally:
        db.close()


if __name__ == "__main__":
    main()
