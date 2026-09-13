from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    llm_provider: str = "groq"
    # The 20B model is fast enough for the structured pipeline and has a
    # separate quota bucket from the previously exhausted 120B model.
    llm_model: str = "openai/gpt-oss-20b"
    llm_fallback_models: str = "qwen/qwen3.6-27b,openai/gpt-oss-120b"
    groq_api_key: str = ""
    videos_per_day: int = Field(default=1, ge=1, le=15)
    dry_run: bool = True
    max_render_retries: int = Field(default=3, ge=1, le=5)
    video_min_duration: float = Field(default=60, ge=1)
    video_max_duration: float = Field(default=360, ge=10)
    manim_quality: str = "low_quality"
    youtube_privacy: str = "private"
    tts_provider: str = "edge"
    tts_voice: str = "en-US-AriaNeural"
    youtube_client_secret_file: Path = ROOT_DIR / "secrets" / "client_secret.json"
    youtube_token_file: Path = ROOT_DIR / "secrets" / "youtube_token.json"

    workbook_path: Path = ROOT_DIR / "input" / "prompts.xlsx"
    database_path: Path = ROOT_DIR / "database" / "agent.db"
    generated_dir: Path = ROOT_DIR / "generated"
    logs_dir: Path = ROOT_DIR / "logs"


def get_settings() -> Settings:
    return Settings()
