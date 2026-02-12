from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    app_name: str
    app_env: str
    database_url: str
    openai_api_key: str | None = None
    openai_model: str
    confidence_threshold: float
    upload_dir: str
    ocr_dir: str
    extraction_dir: str

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def normalize_openai_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
