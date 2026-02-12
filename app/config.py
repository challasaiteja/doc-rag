from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Document Intake POC"
    app_env: str = "development"
    database_url: str = "sqlite:///./document-intake.db"
    anthropic_api_key: str = ""
    confidence_threshold: float = 0.8
    upload_dir: str = "./storage/uploads"
    ocr_dir: str = "./storage/ocr"
    extraction_dir: str = "./storage/extractions"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
