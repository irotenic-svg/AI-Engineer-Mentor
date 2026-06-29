"""
LLM 模块 - 基于 OpenAI SDK 封装 DeepSeek API
"""
from openai import OpenAI

from config import Settings


def create_llm(settings: Settings) -> OpenAI:
    """创建 OpenAI 兼容客户端实例"""
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )
