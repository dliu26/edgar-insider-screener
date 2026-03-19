from pydantic_settings import BaseSettings
from pydantic import field_validator
import json


class Settings(BaseSettings):
    edgar_user_agent: str = "Daniel Liu daniel@dartmouth.edu"
    polygon_api_key: str = ""
    cache_ttl_seconds: int = 3600
    market_cap_ttl_seconds: int = 86400
    max_market_cap_usd: float = 50_000_000_000
    cors_origins: list[str] = ["http://localhost:3000"]
    port: int = 8000

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
