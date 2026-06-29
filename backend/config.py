"""
配置管理模块 - 加载 .env 环境变量
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)


@dataclass
class Settings:
    """应用配置"""

    # DeepSeek LLM
    deepseek_api_key: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", "")
    )
    deepseek_base_url: str = field(
        default_factory=lambda: os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        )
    )
    deepseek_model: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    )

    # Flask
    flask_env: str = field(
        default_factory=lambda: os.getenv("FLASK_ENV", "development")
    )
    flask_host: str = field(
        default_factory=lambda: os.getenv("FLASK_HOST", "0.0.0.0")
    )
    flask_port: int = field(
        default_factory=lambda: int(os.getenv("FLASK_PORT", "5000"))
    )

    # Database
    db_path: str = field(
        default_factory=lambda: os.getenv(
            "DB_PATH", "./backend/data/mentor.db"
        )
    )

    @property
    def llm_api_key(self) -> str:
        return self.deepseek_api_key

    @property
    def llm_base_url(self) -> str:
        return self.deepseek_base_url

    @property
    def llm_model(self) -> str:
        return self.deepseek_model


def load_settings() -> Settings:
    """加载并返回配置实例"""
    return Settings()
