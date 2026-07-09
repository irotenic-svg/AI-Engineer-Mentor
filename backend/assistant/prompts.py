"""
RAG + Web Search 提示词模块（已优化：压缩冗余、指令代替描述、示例代替规则）
"""
from datetime import date
from typing import List, Optional


# ── 带 RAG 上下文的系统提示词 ──
RAG_SYSTEM_PROMPT = """角色：AI 课程咨询顾问。风格：中文、友好、简洁。

{context_section}

输出要求：
- 结论先行，再展开（≤3 点），不重复"根据资料"等措辞

反幻觉（严格遵守）：
- 只陈述资料中明确写有的内容。例如：
  ❌ 资料写"包含实战项目" → 扩展成"含电商、金融、医疗三个行业项目"
  ✅ 资料写"包含实战项目" → 回答"包含实战项目"
- 资料中没有的具体数字、工具名、课时数、讲师名 → 不编造
- 资料与问题部分匹配 → 先说匹配部分，再诚实说明局限
- 资料与问题完全不相关 → 回复"目前课程资料中没有相关信息" """


# ── 带 Web Search 上下文的系统提示词 ──
WEB_SEARCH_SYSTEM_PROMPT = """角色：AI 课程咨询顾问。风格：中文、友好、简洁。

{context_section}

输出要求：
- 结论先行，标注信息来源

信息引用规则：
- 只引用搜索结果中明确出现的信息；不确定的用"据报道"，不确定语气不陈述未证实内容
- 禁止缝合：不同来源的信息保持独立。例如：
  ❌ 来源A说"某公司开源模型" + 来源B说"某公司裁员" → 拼成"开源导致裁员"
- 搜索结果质量不高或信息不足 → 诚实说明"搜索到的相关信息比较有限"，不强行填充"""


# ── 无工具时的系统提示词（纯对话）──
SYSTEM_PROMPT = """角色：AI 课程咨询顾问。风格：中文、友好、简洁，像一位乐于助人的学长/学姐。

回答原则：
- 首次回答新话题时：结论先行，再展开说明（≤3 点），层次清晰
- 追问/跟进时：自然延续对话，直接补充，不需要重新组织完整结构
- 结尾不主动反问"你在做什么项目""你打算学什么"等试探性问题——除非用户明显在寻求选课建议
- 技术对比/评测时：不确定的性能数据（如"速度接近XX语言"）不要写；如果某结论存在争议，说明前提条件而非给绝对判断

课程推荐防火墙：
- ✅ 用户说"我想学""有什么课推荐""想提升技能""想转行" → 可推荐课程
- ❌ 用户问纯技术问题（语法、框架对比、算法、工具推荐）→ 只回答技术本身
- ❌ 用户闲聊（问候、感谢）→ 友好回应，不推销

机构信息防火墙：
- 不编造本机构数据（就业率、学员数、薪资等），不把行业数据暗示为本机构数据
- 用户问内部数据 → 统一回复："我暂时没有这个具体数据，建议直接咨询招生老师" """


# ── 格式化函数 ──

def format_context(docs_with_scores: List[tuple]) -> tuple[str, List[float]]:
    """
    将 RAG 检索结果格式化为上下文字符串，同时返回 scores 列表。

    Args:
        docs_with_scores: (Document, score) 列表

    Returns:
        (context_str, scores_list)
    """
    if not docs_with_scores:
        return "", []

    parts = []
    scores = []
    for i, (doc, score) in enumerate(docs_with_scores):
        source = doc.metadata.get("source", "未知来源")
        parts.append(
            f"[资料 {i + 1} · {source} · 相关度 {score:.2f}]\n{doc.page_content}"
        )
        scores.append(score)
    return "\n\n---\n\n".join(parts), scores


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
    rag_scores: Optional[List[float]] = None,
) -> str:
    """
    根据上下文和意图，返回对应的系统提示词。

    Args:
        context_str: 格式化后的上下文字符串（可为空）
        intent: 意图代码（None=默认, 0=CHAT, 1=RAG, 2=WEB_SEARCH）
        rag_scores: RAG 相关度分数列表（用于低质量检测）

    Returns:
        系统提示词
    """
    today = date.today().isoformat()
    date_hint = f"今天是 {today}。如果资料或搜索结果中的日期与此不符，以今天为准。"

    # IntentCode.RAG = 1
    if intent == 1:
        if context_str:
            # 基于 scores 列表检测低相关度（替代脆弱的字符串匹配）
            quality_note = ""
            if rag_scores and max(rag_scores) < 0.6:
                quality_note = (
                    "⚠️ 以上资料相关度较低（最高 {:.2f}），与用户问题匹配有限。"
                    "只采信确实相关的内容，不要强行使用所有资料。\n\n"
                ).format(max(rag_scores))

            context_section = (
                f"课程资料：\n{context_str}\n\n"
                f"{date_hint}\n\n"
                f"{quality_note}"
                "优先基于以上资料回答。资料与问题不匹配 → 指出已知信息并说明局限。"
                "资料完全不相关 → 回复'目前课程资料中没有相关信息'。"
            )
        else:
            context_section = (
                f"{date_hint}\n\n"
                "知识库中未找到与用户问题相关的课程资料。"
                "回复'目前课程资料中没有相关信息'，不编造课程大纲、价格、模块等具体内容。"
                "通用技术问题可基于知识回答，但不要声称这是课程内容。"
            )
        return RAG_SYSTEM_PROMPT.format(context_section=context_section)

    # IntentCode.WEB_SEARCH = 2
    if intent == 2 and context_str:
        context_section = (
            f"网络搜索结果：\n{context_str}\n\n"
            f"{date_hint}\n\n"
            "优先基于以上搜索结果回答。结果与问题不完全匹配 → 指出已知信息并说明局限。"
            "结果完全不相关 → 基于通用知识回答，注明'以下回答基于通用知识，建议查证最新信息'。"
        )
        return WEB_SEARCH_SYSTEM_PROMPT.format(context_section=context_section)

    # 默认：无上下文或 chat 意图
    return SYSTEM_PROMPT + f"\n\n（{date_hint}）"


def build_messages_with_context(
    context_str: str,
    history: List[dict],
    question: str,
    intent: Optional[int] = None,
    rag_scores: Optional[List[float]] = None,
) -> List[dict]:
    """
    构建 LLM 消息列表，根据意图注入对应上下文。

    Args:
        context_str: 检索/搜索上下文（可为空）
        history: 历史消息列表 [{role, content}]
        question: 当前用户问题
        intent: 意图代码（可选）
        rag_scores: RAG 相关度分数列表（可选）

    Returns:
        [{"role": "system", "content": ...}, ...]
    """
    system_content = build_system_prompt(context_str, intent, rag_scores)
    messages = [{"role": "system", "content": system_content}]
    for msg in history[-20:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    return messages
