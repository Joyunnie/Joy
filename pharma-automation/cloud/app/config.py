from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str  # Required — set PHARMA_DATABASE_URL
    api_key_hash_algorithm: str = "sha256"
    jwt_secret_key: str  # Required — set PHARMA_JWT_SECRET_KEY
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # P32: OCR 엔진 설정 ("google_vision" | "mock")
    ocr_engine: str = "google_vision"
    google_vision_api_key: str = ""

    # P33: 업로드 디렉토리
    upload_dir: str = "uploads/receipts"

    model_config = SettingsConfigDict(env_prefix="PHARMA_")


settings = Settings()
