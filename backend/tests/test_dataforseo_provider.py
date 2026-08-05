from app import models
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.services import (
    COMPETITOR_RESULTS_PER_QUERY,
    build_competitor_brief_for_item,
    build_dataforseo_locations_url,
    build_dataforseo_user_data_url,
    extract_dataforseo_country_location_codes,
    generate_competitor_search_queries,
    normalize_slug,
    parse_dataforseo_credentials,
    regenerate_competitor_queries,
)


def test_competitor_collection_uses_first_six_google_results() -> None:
    assert COMPETITOR_RESULTS_PER_QUERY == 6


def test_dataforseo_credentials_parse_login_password_pair() -> None:
    provider = models.AiProvider(
        name="DataForSEO",
        provider_type="dataforseo",
        endpoint_url="https://api.dataforseo.com/v3",
        model="Google Organic SERP Live Advanced",
        api_key="login@example.com:secret-password",
    )

    assert parse_dataforseo_credentials(provider) == ("login@example.com", "secret-password")


def test_dataforseo_user_data_url_is_built_from_base_endpoint() -> None:
    assert build_dataforseo_user_data_url("https://api.dataforseo.com/v3") == "https://api.dataforseo.com/v3/appendix/user_data"
    assert (
        build_dataforseo_user_data_url("https://api.dataforseo.com/v3/appendix/user_data")
        == "https://api.dataforseo.com/v3/appendix/user_data"
    )


def test_dataforseo_locations_catalog_is_dynamic_for_all_country_codes() -> None:
    assert build_dataforseo_locations_url("https://api.dataforseo.com/v3") == (
        "https://api.dataforseo.com/v3/serp/google/locations"
    )
    payload = {
        "tasks": [
            {
                "result": [
                    {"country_iso_code": "DK", "location_code": 2208, "location_type": "Country"},
                    {"country_iso_code": "DK", "location_code": 1005010, "location_type": "City"},
                    {"country_iso_code": "RO", "location_code": 2642, "location_type": "Country"},
                ]
            }
        ]
    }

    assert extract_dataforseo_country_location_codes(payload) == {"DK": 2208, "RO": 2642}


def test_competitor_brief_does_not_invent_license_verification_gap() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSession() as db:
        task = models.GenerationTask(
            title="DK test",
            geo="DK",
            language="da",
            topics_count=1,
            collect_competitors=True,
        )
        item = models.ContentItem(
            task=task,
            topic="Nye online casinoer",
            slug="/nye-online-casinoer/",
            generated_json={},
            idempotency_key="dynamic-brief-item",
        )
        db.add(item)
        db.flush()

        for index in range(4):
            query = models.CompetitorQuery(
                content_item_id=item.id,
                query=f"nye online casinoer {index}",
                position=index + 1,
            )
            db.add(query)
            db.flush()
            result = models.CompetitorResult(
                content_item_id=item.id,
                query_id=query.id,
                query_text=query.query,
                position=1,
                url=f"https://competitor{index}.example/casino",
                normalized_url=f"https://competitor{index}.example/casino",
            )
            db.add(result)
            db.flush()
            headings = [{"level": 2, "text": "Betalingsmetoder"}]
            if index == 0:
                headings.append({"level": 2, "text": "Sådan kontrollerer du licensen"})
            db.add(
                models.CompetitorPage(
                    content_item_id=item.id,
                    competitor_result_id=result.id,
                    url=result.url,
                    http_status=200,
                    headings=headings,
                    text_content="Relevant competitor page content.",
                    word_count=1000,
                )
            )
        db.commit()

        build_competitor_brief_for_item(db, item)

        assert item.competitor_brief["geo"] == "DK"
        assert item.competitor_brief["language"] == "da"
        assert item.competitor_brief["topics_to_cover"] == ["Betalingsmetoder"]
        recommended_text = " ".join(
            item.competitor_brief["topics_to_cover"] + item.competitor_brief["content_gaps"]
        ).casefold()
        assert "licens" not in recommended_text


def test_competitor_query_generation_uses_only_words_from_topic() -> None:
    topic = "Beste Online Casinos in Deutschland 2026: Legale Anbieter im Vergleich"
    queries = generate_competitor_search_queries(
        topic,
        geo="DE",
        language="de",
    )

    topic_words = {
        "beste", "online", "casinos", "in", "deutschland", "2026", "legale", "anbieter", "im", "vergleich"
    }
    assert queries == [
        "beste online casinos deutschland 2026",
        "deutschland 2026 legale anbieter vergleich",
        "online casinos deutschland 2026 legale",
        "casinos deutschland 2026 legale anbieter",
        "beste online casinos deutschland",
    ]
    assert len(queries) == 5
    assert all(set(query.split()).issubset(topic_words) for query in queries)
    assert all(3 <= len(query.split()) <= 5 for query in queries)


def test_competitor_queries_are_unique_across_topics() -> None:
    first = generate_competitor_search_queries(
        "Beste Online Casinos in Deutschland 2026: Legale Anbieter im Vergleich",
        geo="DE",
        language="de",
    )
    second_topic = "Legale Online Casinos in Deutschland: Anbieter mit GGL-Lizenz"
    second = generate_competitor_search_queries(second_topic, geo="DE", language="de", excluded_queries=set(first))
    second_topic_words = {"legale", "online", "casinos", "in", "deutschland", "anbieter", "mit", "ggl-lizenz"}

    assert set(first).isdisjoint(second)
    assert all(set(query.split()).issubset(second_topic_words) for query in second)


def test_normalize_slug_uses_first_five_topic_words() -> None:
    assert (
        normalize_slug("Beste Online Casinos in Deutschland 2026: Legale Anbieter im Vergleich")
        == "/beste-online-casinos-in-deutschland/"
    )


def test_regenerate_competitor_queries_clears_old_research() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSession() as db:
        task = models.GenerationTask(
            title="DE test",
            geo="DE",
            language="de",
            topics_count=1,
            collect_competitors=True,
        )
        item = models.ContentItem(
            task=task,
            topic="Beste Online Casinos in Deutschland 2026: Legale Anbieter im Vergleich",
            slug="/beste-online-casinos/",
            generated_json={},
            idempotency_key="test-item",
            competitor_research_status="brief_ready",
            competitor_brief={"old": True},
            competitor_brief_text="old",
        )
        db.add(item)
        db.flush()
        old_query = models.CompetitorQuery(content_item_id=item.id, query="old query", position=1)
        db.add(old_query)
        db.flush()
        old_result = models.CompetitorResult(
            content_item_id=item.id,
            query_id=old_query.id,
            query_text=old_query.query,
            position=1,
            url="https://competitor.example/page",
            normalized_url="https://competitor.example/page",
        )
        db.add(old_result)
        db.flush()
        db.add(
            models.CompetitorPage(
                content_item_id=item.id,
                competitor_result_id=old_result.id,
                url=old_result.url,
                http_status=200,
                word_count=1000,
            )
        )
        db.commit()

        new_queries = regenerate_competitor_queries(db, item, "DE", "de")
        db.commit()

        assert item.competitor_research_status == "queries_ready"
        assert item.competitor_brief is None
        assert item.competitor_brief_text is None
        assert [query.query for query in new_queries] != ["old query"]
        assert db.scalar(select(func.count()).select_from(models.CompetitorResult)) == 0
        assert db.scalar(select(func.count()).select_from(models.CompetitorPage)) == 0
