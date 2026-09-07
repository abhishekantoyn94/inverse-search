from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://inverse:inverse@localhost:5432/inverse"

    opensearch_url: str = "http://localhost:9200"
    opensearch_user: str | None = None
    opensearch_password: str | None = None

    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-large"
    available_chat_models: list[str] = [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4.1-mini",
        "gpt-4.1",
        "o4-mini",
    ]

    courtlistener_api_token: str = ""
    govinfo_api_key: str = "DEMO_KEY"  # api.data.gov's public demo key — low rate limits, fine for MVP volumes
    congress_gov_api_key: str = ""
    tavily_api_key: str = ""

    app_env: str = "development"


settings = Settings()
