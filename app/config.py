import os
from functools import lru_cache
from pydantic import BaseModel

class Settings(BaseModel):
    app_secret: str = os.getenv("APP_SECRET", "change-me")
    base_url: str = os.getenv("APP_BASE_URL", "http://localhost:8000")
    env: str = os.getenv("ENV", "dev")

    # ASR
    asr_provider: str = os.getenv("ASR_PROVIDER", "local")  # local|assemblyai|deepgram (deepgram not implemented below)
    whisper_model_size: str = os.getenv("WHISPER_MODEL_SIZE", "small")
    assemblyai_key: str | None = os.getenv("ASSEMBLYAI_API_KEY")

    # LLM
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")  # openai|ollama
    openai_key: str | None = os.getenv("OPENAI_API_KEY")
    ollama_base: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1")

    # Email
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_pass: str = os.getenv("SMTP_PASS", "")
    from_email: str = os.getenv("FROM_EMAIL", "")

    # Slack
    slack_webhook: str | None = os.getenv("SLACK_WEBHOOK_URL")
    
    # Auth
    jwt_secret: str = os.getenv("JWT_SECRET", os.getenv("APP_SECRET", "change-me"))
    jwt_alg: str = os.getenv("JWT_ALG", "HS256")
    jwt_expires_minutes: int = int(os.getenv("JWT_EXPIRES_MINUTES", "60"))

    admin_user: str = os.getenv("ADMIN_USER", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "")  # set in env!

    # Comma-separated list: "key1,key2"
    api_keys_csv: str = os.getenv("API_KEYS", "")
    @property
    def api_keys(self) -> list[str]:
        return [k.strip() for k in self.api_keys_csv.split(",") if k.strip()]

    dev_allow_no_auth: bool = os.getenv("DEV_ALLOW_NO_AUTH", "0") == "1"

@lru_cache
def get_settings() -> Settings:
    return Settings()
