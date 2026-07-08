"""
RAG + Web Search 提示词模块
"""
from typing import List, Optional


# ── 带 RAG 上下文的系统提示词 ──
RAG_SYSTEM_PROMPT = """你是 AI 课程咨询助手，主要职责是为用户提供课程相关的咨询和答疑。

{context_section}

对话风格：
- 用中文回答，语气友好、耐心、像一位乐于助人的学长/学姐
- 回答简明扼要，条理清晰
- 遇到课程相关话题时，自然地结合课程资料内容给出建议
- 推荐课程时客观分析利弊，不夸大效果
- 不要把话题强行扭回课程咨询，先回答用户的问题，再适时关联课程
- 回答问题时自然流畅，不要反复说"根据资料""根据上下文"等措辞"""


# ── 带 Web Search 上下文的系统提示词 ──
WEB_SEARCH_SYSTEM_PROMPT = """你是 AI 课程咨询助手，主要职责是为用户提供课程相关的咨询和答疑。

{context_section}

对话风格：
- 用中文回答，语气友好、耐心、像一位乐于助人的学长/学姐
- 回答简明扼要，条理清晰
- 优先基于以上网络搜索结果进行回答，引用信息时自然地提及来源
- 如果搜索结果不足以回答问题，说明局限并建议用户如何获取更准确的信息
- 基于搜索结果的时效性信息要注意说明时间背景
- 不要把话题强行扭回课程咨询，先回答用户的问题，再适时关联课程"""


# ── 无工具时的系统提示词（纯对话）──
SYSTEM_PROMPT = """你是 AI 课程咨询助手，主要职责是为用户提供课程相关的咨询和答疑。

你的能力包括但不限于：
- 解答课程内容、学习路径、就业前景等问题
- 根据用户背景和需求推荐合适的课程
- 分析用户上传的文件内容，回答相关问题
- 回答用户提出的各类技术问题、学习困惑

对话风格：
- 用中文回答，语气友好、耐心、像一位乐于助人的学长/学姐
- 回答简明扼要，条理清晰
- 遇到课程相关话题时，自然地结合课程内容给出建议
- 推荐课程时客观分析利弊，不夸大效果
- 用户上传文件时，仔细分析内容并给出有用反馈
- 不要把话题强行扭回课程咨询，先回答用户的问题，再适时关联课程"""


# ── 格式化函数 ──

def format_context(docs_with_scores: List[tuple]) -> str:
    """
    将 RAG 检索结果格式化为上下文字符串

    Args:
        docs_with_scores: (Document, score) 列表

    Returns:
        格式化的上下文字符串
    """
    if not docs_with_scores:
        return ""

    parts = []
    for i, (doc, score) in enumerate(docs_with_scores):
        source = doc.metadata.get("source", "未知来源")
        parts.append(
            f"[资料 {i + 1} · {source} · 相关度 {score:.2f}]\n{doc.page_content}"
        )
    return "\n\n---\n\n".join(parts)


def format_sources(docs_with_scores: List[tuple]) -> List[dict]:
    """
    将 RAG 检索结果格式化为前端来源数据

    Args:
        docs_with_scores: (Document, score) 列表

    Returns:
        [{content, source, score}] 列表
    """
    sources = []
    seen = set()
    for doc, score in docs_with_scores:
        preview = doc.page_content[:200]
        if len(doc.page_content) > 200:
            preview += "..."
        key = preview[:80]
        if key not in seen:
            seen.add(key)
            sources.append(
                {
                    "content": preview,
                    "source": doc.metadata.get("source", "未知来源"),
                    "score": round(score, 4),
                }
            )
    return sources


# ── System Prompt 构建（意图感知）──

def build_system_prompt(
    context_str: str,
    intent: Optional[int] = None,
) -> str:
    """
    根据上下文和意图，返回对应的系统提示词。

    Args:
        context_str: 格式化后的上下文字符串（可为空）
        intent: 意图代码（None=默认, 0=CHAT, 1=RAG, 2=WEB_SEARCH）

    Returns:
        系统提示词
    """
    # IntentCode.RAG = 1
    if intent == 1 and context_str:
        context_section = (
            f"已有课程资料：\n{context_str}\n\n"
            "请优先基于以上课程资料进行回答。如果资料与用户问题不完全匹配，"
            "指出已知的相关信息，并说明局限。如果资料完全不相关，"
            "基于你的通用知识回答，并说明'以下回答不基于特定课程资料'。"
        )
        return RAG_SYSTEM_PROMPT.format(context_section=context_section)

    # IntentCode.WEB_SEARCH = 2
    if intent == 2 and context_str:
        context_section = (
            f"最新网络搜索结果：\n{context_str}\n\n"
            "请优先基于以上网络搜索结果进行回答。如果搜索结果与用户问题不完全匹配，"
            "指出已知的相关信息，并说明搜索局限。如果搜索结果完全不相关，"
            "基于你的通用知识回答，并说明'以下回答基于通用知识，建议查证最新信息'。"
        )
        return WEB_SEARCH_SYSTEM_PROMPT.format(context_section=context_section)

    # 默认：无上下文或 chat 意图
    return SYSTEM_PROMPT


def build_messages_with_context(
    context_str: str,
    history: List[dict],
    question: str,
    intent: Optional[int] = None,
) -> List[dict]:
    """
    构建 LLM 消息列表，根据意图注入对应上下文。

    Args:
        context_str: 检索/搜索上下文（可为空）
        history: 历史消息列表 [{role, content}]
        question: 当前用户问题
        intent: 意图代码（可选）

    Returns:
        [{"role": "system", "content": ...}, ...]
    """
    system_content = build_system_prompt(context_str, intent)
    messages = [{"role": "system", "content": system_content}]
    for msg in history[-20:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    return messages
