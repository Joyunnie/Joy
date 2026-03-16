from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://pharma_user:pharma_pass@db:5432/pharma"
    api_key_hash_algorithm: str = "sha256"

    model_config = SettingsConfigDict(env_prefix="PHARMA_")


settings = Settings()
