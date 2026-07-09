"""
网络搜索模块 - Tavily API 封装

提供实时网页搜索，返回与 RAG sources 格式兼容的结果。
"""
from typing import Optional


class WebSearchManager:
    """Tavily 搜索管理器，支持优雅降级"""

    def __init__(self, api_key: str, enabled: bool = True):
        self._enabled = enabled and bool(api_key)
        self._api_key = api_key
        self._client = None
        if self._enabled:
            try:
                from tavily import TavilyClient
                self._client = TavilyClient(api_key=api_key)
                print("[WebSearch] Tavily client initialized")
            except Exception as e:
                print(f"[WebSearch] Tavily init failed: {e}")
                self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled and self._client is not None

    def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "advanced",
    ) -> dict:
        """
        执行网络搜索。

        Args:
            query: 搜索查询
            max_results: 最大返回结果数
            search_depth: "basic" 或 "advanced"

        Returns:
            {"query": str, "results": list[dict], "response_time": float, "error": str|None}
        """
        if not self.enabled:
            return {
                "query": query,
                "results": [],
                "response_time": 0.0,
                "error": "Web search is disabled or not configured",
            }

        try:
            response = self._client.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results,
                include_answer=False,
            )

            results = []
            for r in response.get("results", []):
                if r.get("score", 0) >= 0.5:  # 过滤低相关度结果
                    results.append({
                        "content": r.get("content", ""),
                        "source": r.get("url", ""),
                        "url": r.get("url", ""),
                        "title": r.get("title", ""),
                        "score": round(r.get("score", 0), 4),
                    })

            return {
                "query": response.get("query", query),
                "results": results,
                "response_time": response.get("response_time", 0.0),
                "error": None,
            }

        except Exception as e:
            print(f"[WebSearch] Search failed: {e}")
            return {
                "query": query,
                "results": [],
                "response_time": 0.0,
                "error": str(e),
            }

    def format_sources(self, results: list[dict]) -> list[dict]:
        """
        将搜索结果格式化为前端兼容的 sources 列表。
        输出与 RAG format_sources() 兼容，额外包含 title 和 url 字段。

        Returns:
            [{"content": str, "source": str, "score": float, "title": str, "url": str}, ...]
        """
        sources = []
        for r in results:
            content = r.get("content", "")
            preview = content[:200] + ("..." if len(content) > 200 else "")
            sources.append({
                "content": preview,
                "source": r.get("url", ""),
                "score": r.get("score", 0),
                "title": r.get("title", ""),
                "url": r.get("url", ""),
            })
        return sources


# ── Web 上下文格式化（模块级函数）──

import re

# 匹配 AI 搜索引擎残留的 citation 标记，如 【5†L9-L18】、【1†L5-L7】
_CITATION_PATTERN = re.compile(r'【\d+[†‡]\s*[^】]+】')


def _clean_content(text: str) -> str:
    """清洗搜索结果中的 citation 标记和多余空白"""
    text = _CITATION_PATTERN.sub('', text)
    # 合并清洗产生的连续空白
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def format_web_context(results: list[dict]) -> str:
    """
    将网络搜索结果格式化为 LLM 上下文字符串。
    自动清洗 AI 搜索引擎残留的 citation 标记。

    Args:
        results: [{"content": ..., "title": ..., "url": ..., "score": ...}, ...]

    Returns:
        格式化的上下文字符串
    """
    if not results:
        return ""

    parts = []
    for i, r in enumerate(results):
        content = _clean_content(r.get('content', ''))
        parts.append(
            f"[网络来源 {i + 1} · {r.get('title', '未知')} · 相关度 {r.get('score', 0):.2f}]\n"
            f"URL: {r.get('url', '')}\n"
            f"{content}"
        )
    return "\n\n---\n\n".join(parts)
