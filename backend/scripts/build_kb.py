"""
知识库构建脚本
遍历 knowledge/ 目录 → 提取文本 → 分块 → 嵌入 → ChromaDB 持久化

用法: python scripts/build_kb.py
"""
import sys
from pathlib import Path

# 确保 backend 在 sys.path 中（支持从项目根目录或 scripts/ 目录运行）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_DIR = _PROJECT_ROOT / "backend"
sys.path.insert(0, str(_BACKEND_DIR))

from config import load_settings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from assistant.embeddings import get_embedder
from assistant.vectorstore import VectorStoreManager
from file_utils import extract_text


def build_knowledge_base():
    """主构建流程"""
    settings = load_settings()

    knowledge_dir = Path(settings.knowledge_absolute_dir)
    chroma_dir = Path(settings.chroma_absolute_dir)

    print(f"[1/5] 检查知识库目录: {knowledge_dir}")
    if not knowledge_dir.exists():
        print(f"  [ERROR] 目录不存在，正在创建...")
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        print(f"  请在 {knowledge_dir} 中放入课程文档 (.txt/.md/.docx/.pdf/.xlsx/.html)")
        print(f"  然后重新运行此脚本。")
        return

    # 收集支持的文件
    supported_exts = {".txt", ".md", ".docx", ".pdf", ".xlsx", ".html", ".ipynb", ".pptx"}
    files = sorted(
        [f for f in knowledge_dir.rglob("*") if f.suffix.lower() in supported_exts and f.is_file()]
    )

    if not files:
        print(f"  [ERROR] 目录为空，没有找到支持的文档文件")
        print(f"  支持的格式: {', '.join(supported_exts)}")
        return

    print(f"  找到 {len(files)} 个文档文件")

    # ── 加载文档 ──
    print(f"\n[2/5] 加载并提取文本...")
    documents: list[Document] = []
    skip_count = 0
    for fp in files:
        text = extract_text(str(fp), fp.name)
        if not text or text.startswith("[") and text.endswith("]") and "错误" in text or "不支持" in text:
            print(f"  [WARN] 跳过: {fp.name} ({'提取失败' if not text else text[:50]})")
            skip_count += 1
            continue
        documents.append(
            Document(
                page_content=text,
                metadata={"source": fp.name, "path": str(fp), "type": fp.suffix.lower()[1:]},
            )
        )

    if not documents:
        print("  [ERROR] 没有成功提取任何文档内容")
        return

    total_chars = sum(len(d.page_content) for d in documents)
    print(f"  成功加载 {len(documents)} 个文档，共 {total_chars:,} 字符")

    # ── 分块 ──
    print(f"\n[3/5] 文本分块 (chunk_size={settings.chunk_size}, overlap={settings.chunk_overlap})...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " ", ""],
        keep_separator=True,
    )
    chunks = splitter.split_documents(documents)
    # 过滤过短的 chunk
    chunks = [c for c in chunks if len(c.page_content.strip()) >= 10]
    print(f"  生成 {len(chunks)} 个文档块")

    # ── 初始化嵌入模型 ──
    print(f"\n[4/5] 初始化嵌入模型: {settings.embedding_model}")
    try:
        embedder = get_embedder(settings.embedding_model, settings.embedding_device)
    except Exception as e:
        print(f"  [ERROR] 嵌入模型加载失败: {e}")
        print(f"\n  BGE-M3 模型约 2.2 GB，首次使用需下载。")
        print(f"  请运行以下命令手动下载:")
        print(f"    python -c \"from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')\"")
        print(f"  如果网络受限，可设置环境变量 HF_ENDPOINT=https://hf-mirror.com 使用镜像站。")
        return

    print(f"  设备: {embedder.device}")

    # ── 构建向量库 ──
    print(f"\n[5/5] 构建向量库 → {chroma_dir}")
    Chroma = None  # 延迟导入
    try:
        from langchain_chroma import Chroma as _Chroma

        Chroma = _Chroma
    except ImportError:
        print("  [ERROR] 未安装 langchain-chroma，请运行: pip install langchain-chroma")
        return

    # 删除旧集合
    import shutil

    if chroma_dir.exists():
        shutil.rmtree(chroma_dir)
        print("  已清空旧向量库")

    chroma_dir.mkdir(parents=True, exist_ok=True)

    # 批量添加（每批 500 条，避免 OOM）
    batch_size = 500
    vs = None
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        if vs is None:
            vs = Chroma.from_documents(
                documents=batch,
                embedding=embedder,
                persist_directory=str(chroma_dir),
                collection_name="course_knowledge",
            )
        else:
            vs.add_documents(batch)
        print(f"  已处理 {min(i + batch_size, len(chunks))}/{len(chunks)} 块")

    print(f"\n  [OK] 构建完成!")
    print(f"  向量库: {chroma_dir}")
    print(f"  集合名: course_knowledge")
    print(f"  文档块数: {len(chunks)}")
    print(f"  源文件数: {len(files) - skip_count}")

    # 来源分布
    from collections import Counter

    sources = Counter(c.metadata.get("source", "unknown") for c in chunks)
    print(f"\n  各文件块数分布:")
    for src, cnt in sources.most_common(10):
        print(f"    {cnt:5d}  {src}")


if __name__ == "__main__":
    build_knowledge_base()
