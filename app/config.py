from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://redis:6379/0"
    groq_api_key: str
    upload_dir: str = "/app/uploads"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
