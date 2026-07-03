"""
嵌入模块 - 基于 sentence-transformers 的 BGE-M3 嵌入模型
封装为 LangChain Embeddings 接口
"""
from typing import List, Optional

from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer


# 模块级单例
_embedder_instance: Optional["BGEM3Embeddings"] = None


class BGEM3Embeddings(Embeddings):
    """
    BGE-M3 嵌入模型 (BAAI/bge-m3)
    支持中英文双语，1024维向量，GPU/CPU 推理
    """

    def __init__(self, model_name: str = "BAAI/bge-m3", device: str = "auto"):
        if device == "auto":
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = SentenceTransformer(
            model_name,
            device=device,
            local_files_only=True,  # 离线模式，避免 HuggingFace 连接超时
        )
        self._model_name = model_name
        self._device = device

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """嵌入文档列表（批量）"""
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=True,
            batch_size=32,
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        """嵌入单条查询"""
        embedding = self._model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def device(self) -> str:
        return self._device


def get_embedder(
    model_name: str = "BAAI/bge-m3", device: str = "auto"
) -> BGEM3Embeddings:
    """获取嵌入模型单例"""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = BGEM3Embeddings(model_name, device)
    return _embedder_instance
