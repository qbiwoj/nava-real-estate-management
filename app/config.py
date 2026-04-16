from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://nava:nava@localhost:5432/nava"
    TEST_DATABASE_URL: str = "postgresql+asyncpg://nava:nava@localhost:5432/nava_test"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    MODEL_ID: str = "claude-sonnet-4-6"


settings = Settings()
