"""
向量存储模块 - Chroma 向量数据库操作（langchain_chroma）
"""
from typing import List, Dict, Any, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document

from .embeddings import BGEM3Embeddings


class VectorStoreManager:
    """Chroma 向量存储管理器"""

    def __init__(
        self,
        persist_dir: str,
        embedding: BGEM3Embeddings,
        collection_name: str = "course_knowledge",
    ):
        self._persist_dir = persist_dir
        self._embedding = embedding
        self._collection_name = collection_name
        self._vectorstore: Optional[Chroma] = None

    @property
    def vectorstore(self) -> Chroma:
        """获取或初始化向量存储（懒加载）"""
        if self._vectorstore is None:
            self._vectorstore = Chroma(
                collection_name=self._collection_name,
                embedding_function=self._embedding,
                persist_directory=self._persist_dir,
            )
        return self._vectorstore

    def add_documents(self, documents: List[Document]) -> None:
        """批量添加 LangChain Document"""
        self.vectorstore.add_documents(documents)

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> None:
        """批量添加文本"""
        self.vectorstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)

    def as_retriever(self, search_kwargs: Optional[Dict[str, Any]] = None):
        """获取 LangChain Retriever"""
        if search_kwargs is None:
            search_kwargs = {"k": 5, "score_threshold": 0.45}
        return self.vectorstore.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs=search_kwargs,
        )

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        """相似度搜索"""
        return self.vectorstore.similarity_search(query, k=k)

    def similarity_search_with_relevance_scores(
        self, query: str, k: int = 5
    ) -> List[tuple]:
        """带分数的相似度搜索，返回 (Document, score) 列表"""
        return self.vectorstore.similarity_search_with_relevance_scores(query, k=k)

    def delete_collection(self) -> None:
        """删除集合"""
        if self._vectorstore is not None:
            self._vectorstore.delete_collection()
            self._vectorstore = None

    def count(self) -> int:
        """获取集合中的文档数"""
        return self.vectorstore._collection.count()

    def get_collection_stats(self) -> Dict[str, Any]:
        """获取集合统计"""
        collection = self.vectorstore._collection
        return {"name": collection.name, "count": collection.count()}
