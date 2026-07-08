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

    # ── RAG ──
    rag_enabled: bool = field(
        default_factory=lambda: os.getenv("RAG_ENABLED", "true").lower() == "true"
    )
    chroma_dir: str = field(
        default_factory=lambda: os.getenv("CHROMA_DIR", "./backend/data/chroma")
    )
    knowledge_dir: str = field(
        default_factory=lambda: os.getenv("KNOWLEDGE_DIR", "./backend/data/knowledge")
    )
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    )
    embedding_device: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_DEVICE", "auto")
    )

    # ── Retrieval ──
    retrieval_top_k: int = field(
        default_factory=lambda: int(os.getenv("RETRIEVAL_TOP_K", "5"))
    )
    retrieval_score_threshold: float = field(
        default_factory=lambda: float(os.getenv("RETRIEVAL_SCORE_THRESHOLD", "0.45"))
    )

    # ── Chunking ──
    chunk_size: int = field(
        default_factory=lambda: int(os.getenv("CHUNK_SIZE", "500"))
    )
    chunk_overlap: int = field(
        default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "50"))
    )

    # ── Tavily Web Search ──
    tavily_api_key: str = field(
        default_factory=lambda: os.getenv("TAVILY_API_KEY", "")
    )
    web_search_enabled: bool = field(
        default_factory=lambda: os.getenv("WEB_SEARCH_ENABLED", "true").lower() == "true"
    )
    web_search_max_results: int = field(
        default_factory=lambda: int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))
    )

    # ── Intent Recognition ──
    intent_enabled: bool = field(
        default_factory=lambda: os.getenv("INTENT_ENABLED", "true").lower() == "true"
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

    @property
    def chroma_absolute_dir(self) -> str:
        p = Path(self.chroma_dir)
        if not p.is_absolute():
            p = (_PROJECT_ROOT / p).resolve()
        return str(p)

    @property
    def knowledge_absolute_dir(self) -> str:
        p = Path(self.knowledge_dir)
        if not p.is_absolute():
            p = (_PROJECT_ROOT / p).resolve()
        return str(p)


def load_settings() -> Settings:
    """加载并返回配置实例"""
    return Settings()
