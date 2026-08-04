from app import models
from app.services import build_dataforseo_user_data_url, generate_competitor_search_queries, parse_dataforseo_credentials


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


def test_competitor_query_generation_keeps_short_relevant_queries() -> None:
    queries = generate_competitor_search_queries(
        "Beste Online Casinos in Deutschland 2026: Legale Anbieter im Vergleich",
        geo="DE",
        language="de",
    )

    assert 2 <= len(queries) <= 3
    assert "legale online casinos ggl" in queries
    assert all(3 <= len(query.split()) <= 5 for query in queries)
