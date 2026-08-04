from app import models
from app.services import build_dataforseo_user_data_url, parse_dataforseo_credentials


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
