from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://nava:nava@localhost:5432/nava"
    TEST_DATABASE_URL: str = "postgresql+asyncpg://nava:nava@localhost:5432/nava_test"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    THREAD_SIMILARITY_THRESHOLD: float = 0.25
    TOP_N_FEW_SHOT: int = 5


settings = Settings()
