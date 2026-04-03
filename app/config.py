from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    openai_api_key: str = ""
    llm_model: str = "gpt-4o"
    orchestrix_api_url: str = "http://localhost:8000"
    log_level: str = "INFO"
    api_key: str = ""  # Optional auth key for incoming requests
    max_request_body_kb: int = 512  # Max request payload size

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
