r"""
意图识别模块 - LLM function calling 分类 + 关键词 fallback

参考 E:\ProgramData\AI-CRM\seachat\intents.py
"""
import re
from enum import IntEnum
from typing import Optional


class IntentCode(IntEnum):
    """意图类别"""
    CHAT = 0        # 直接对话，不使用工具
    RAG = 1         # 课程知识库检索
    WEB_SEARCH = 2  # 网络搜索


# ── LLM Function Calling 工具定义 ──

INTENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_intent_rag",
            "description": (
                "用户询问课程知识库中的内容，包括：课程大纲、课程内容、课程安排、"
                "教学计划、学习路径、课程对比、课程推荐、课程适合人群、前置知识要求、"
                "讲师信息、教学方式、报名流程、学费价格、课表时间、上课地点、"
                "证书认证、就业方向、FAQ 等课程相关问题"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_intent_web_search",
            "description": (
                "用户询问需要实时信息或外部知识的问题，包括：最新技术趋势、"
                "行业动态新闻、当前市场行情、最新政策法规、时事资讯、"
                "工具/框架版本对比、编程语言选型、不在课程知识库范围内的专业知识查询"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_intent_chat",
            "description": (
                "用户进行普通对话、闲聊、问候、感谢、询问助手功能、"
                "表达情绪、简单常识问答、编程求助、或其他无法明确归类为"
                "课程咨询或实时信息查询的对话"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

# 工具名 → IntentCode 映射
TOOL_NAME_TO_INTENT = {
    "set_intent_rag": IntentCode.RAG,
    "set_intent_web_search": IntentCode.WEB_SEARCH,
    "set_intent_chat": IntentCode.CHAT,
}

# ── 分类 System Prompt（含 few-shot 示例）──

INTENT_SYSTEM_PROMPT = (
    "你是一个意图分类助手。请根据用户输入调用最合适的 tool 来确定意图类别，只做分类不要回答。"
    "\n\n分类规则："
    "\n- RAG检索：用户询问课程内部资料——课程内容、大纲、价格、讲师、学习路径、就业、FAQ等。"
    "如果用户的问题涉及课程内部信息（例如课程对比、课程效果、课程工具），即使措辞泛化也应归为RAG。"
    "\n- 网络搜索：用户询问外部实时/时效性信息——技术趋势、工具/框架/语言选型对比、行业新闻、"
    "最新动态、招聘市场行情、版本差异、2024-2026年的技术发展、就业薪资数据等。"
    "关键判断：问题答案是否依赖当前（近期）的真实数据？如果是→网络搜索。"
    "\n- 直接对话：普通闲聊、问候、感谢、常识问答、纯学术/理论性编程基础知识问答"
    "（如算法概念、语言语法特性、计算机科学基础概念），或无法明确归类到以上两种的对话。"
    "\n\n示例："
    "\n「Python数据分析课程学什么？」→ RAG检索"
    "\n「这门课多少钱？」→ RAG检索"
    "\n「数据分析需要用到哪些工具？」→ RAG检索"
    "\n「零基础能学会吗？」→ RAG检索"
    "\n「学完能找什么工作？」→ RAG检索"
    "\n「Python怎么样？」→ RAG检索"
    "\n「报班学习和自学哪个好？」→ RAG检索"
    "\n「全日制和周末班什么区别？」→ RAG检索"
    "\n「2025年AI行业最新趋势是什么？」→ 网络搜索"
    "\n「React和Vue哪个好？」→ 网络搜索"
    "\n「Python和Java哪个更适合新手？」→ 网络搜索"
    "\n「Vue 3和Vue 2的主要区别」→ 网络搜索"
    "\n「学Python还是JavaScript对找工作更有帮助？」→ 网络搜索"
    "\n「DeepSeek最新版本有什么新功能？」→ 网络搜索"
    "\n「学完Python能找到工作吗？最近市场怎么样？」→ 网络搜索"
    "\n「你好」→ 直接对话"
    "\n「谢谢你的帮助」→ 直接对话"
    "\n「什么是Python？」→ 直接对话"
    "\n「解释一下什么是递归」→ 直接对话"
    "\n「帮我写一段排序代码」→ 直接对话"
    "\n「讲个笑话吧」→ 直接对话"
)


# ── 关键词 Fallback ──

# 课程相关关键词 → RAG
_RAG_KEYWORDS = re.compile(
    r"(课程|课表|大纲|教学|讲师|老师|上课|下课|报名|学费|价格|费用|"
    r"学习路径|学习路线|学习周期|学多久|多久学完|全日制|周末班|线上|线下|"
    r"试听|优惠|折扣|证书|认证|就业|找工作|毕业|结课|适合|零基础|前置|"
    r"训练营|实操|实战|项目|案例)"
)

# 外部信息关键词 → Web Search
_WEB_SEARCH_KEYWORDS = re.compile(
    r"(最新|最近|今年|202[4-9]|当前|今日|今天|实时|新闻|动态|趋势|行情|"
    r"市场|招聘|薪资排行|行业报告|热点|热点新闻|新功能|发布了|宣布|刚刚|"
    r"对比|哪个好|区别|选型|vs\.?|versus)"
)


def _keyword_intent(query: str) -> IntentCode:
    """关键词匹配 fallback，当 LLM 不可用或出错时使用"""
    q = query.strip()
    if not q:
        return IntentCode.CHAT

    rag_score = len(_RAG_KEYWORDS.findall(q))
    web_score = len(_WEB_SEARCH_KEYWORDS.findall(q))

    if rag_score == 0 and web_score == 0:
        return IntentCode.CHAT

    # RAG 优先（课程咨询助手的默认偏向）；WEB 需要显著多于 RAG 才切换
    if rag_score > 0 or (web_score < 2 and rag_score == 0):
        return IntentCode.RAG

    if web_score >= 2:
        return IntentCode.WEB_SEARCH

    return IntentCode.CHAT


# ── 主入口 ──

def detect_intent(
    llm,
    query: str,
    model: str,
    enabled: bool = True,
) -> tuple:
    """
    分类用户意图。

    Args:
        llm: OpenAI 兼容客户端实例
        query: 用户问题
        model: 模型名
        enabled: 是否启用意图识别

    Returns:
        (IntentCode, source_label)
        source_label: "llm" | "keyword" | "disabled"
    """
    if not enabled:
        return IntentCode.CHAT, "disabled"

    if not llm:
        return _keyword_intent(query), "keyword"

    try:
        response = llm.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            tools=INTENT_TOOLS,
            tool_choice="auto",   # DeepSeek thinking mode 不支持 "required"
            max_tokens=1024,
            temperature=0.0,
        )

        choice = response.choices[0]
        msg = choice.message

        # 方式 1: 模型返回了 tool_calls
        if msg.tool_calls:
            tool_name = msg.tool_calls[0].function.name
            intent = TOOL_NAME_TO_INTENT.get(tool_name)
            if intent is not None:
                return intent, "llm"

        # 方式 2: 模型返回了文本，从文本中提取意图关键词
        content = msg.content or ""
        if "set_intent_rag" in content:
            return IntentCode.RAG, "llm-text"
        if "set_intent_web_search" in content:
            return IntentCode.WEB_SEARCH, "llm-text"
        if "set_intent_chat" in content:
            return IntentCode.CHAT, "llm-text"

        return _keyword_intent(query), "keyword"

    except Exception as e:
        print(f"[Intent] LLM 分类失败，使用关键词 fallback: {e}")
        return _keyword_intent(query), "keyword"
