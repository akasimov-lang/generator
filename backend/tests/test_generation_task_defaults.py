from app.schemas import GenerationTaskCreate


def test_generation_task_default_target_is_2000_words() -> None:
    payload = GenerationTaskCreate(
        title="Default word count",
        geo="DE",
        language="de",
        topics=["Beste Online Casinos"],
    )

    assert payload.target_words == 2000


def test_generation_task_title_can_be_generated_by_service() -> None:
    payload = GenerationTaskCreate(
        geo="DE",
        language="de",
        topics=["Beste Online Casinos"],
    )

    assert payload.title is None
