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


# ── LLM Function Calling 工具定义（已精简描述）──

INTENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_intent_rag",
            "description": (
                "课程内部资料查询：大纲、价格、讲师、学习路径、课程对比、"
                "课程就业、课程涉及的工具/技能、报名流程、FAQ等"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_intent_web_search",
            "description": (
                "需要实时/时效性数据：最新版本特性（含明确版本号）、市场行情、行业新闻、"
                "招聘薪资、2024-2026年趋势、政策变动。"
                "注意：基础概念对比（React vs Vue）不需要搜索"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_intent_chat",
            "description": (
                "普通对话：闲聊、问候、常识、编程技术知识（语法、算法、架构原理）、"
                "基础概念对比、代码编写。不依赖课程资料也不依赖实时数据"
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

# ── 分类 System Prompt（已精简：删冗余规则，保留核心判断法则 + 关键边界示例）──

INTENT_SYSTEM_PROMPT = (
    "你是一个意图分类助手。根据用户输入调用最合适的 tool，只做分类不回答。"
    "\n\n核心法则：这个问题需要\"今天的答案\"还是\"不变的答案\"？"
    "\n- 不变的答案（概念、语法、架构、基础对比、语言选型）→ set_intent_chat"
    "\n- 今天的答案（最新版本、市场行情、薪资、近期事件）→ set_intent_web_search"
    "\n- 课程内部信息（大纲、价格、讲师、就业、工具）→ set_intent_rag"
    "\n\n关键区分："
    "\n- 只要在问本机构课程的具体信息（即使措辞泛化，如'Python怎么样？'）→ RAG"
    "\n- 单纯的工具推荐或语言选型（'现在学X还是Y'不含就业趋势）→ CHAT，不是 WEB"
    "\n- 问\"当前/现在XX技术发展到什么阶段\"（不涉及市场数据/薪资/招聘）→ CHAT"
    "\n- 问外部免费课程/通用资源推荐（非本机构课程）→ CHAT"
    "\n- 技术对比中包含\"趋势/发展/市场/份额\"等词 → WEB_SEARCH，不是 CHAT"
    "\n- 即使外观像基础对比（X vs Y），只要含\"趋势/发展/最新/市场\" → 归 WEB_SEARCH"
    "\n\n示例："
    "\n「Python数据分析课程学什么？」→ RAG"
    "\n「这门课多少钱？」→ RAG"
    "\n「零基础能学会吗？」→ RAG"
    "\n「报班学习和自学哪个好？」→ RAG"
    "\n「全日制和周末班什么区别？」→ RAG"
    "\n「数据分析需要用到哪些工具？」→ RAG"
    "\n「Python怎么样？」→ RAG"
    "\n「2025年AI行业最新趋势是什么？」→ WEB_SEARCH"
    "\n「2026年前端框架市场份额排名」→ WEB_SEARCH"
    "\n「学Python还是JavaScript对找工作更有帮助？」→ WEB_SEARCH"
    "\n「TypeScript和JavaScript发展趋势对比」→ WEB_SEARCH"
    "\n「学完Python能找到工作吗？最近市场怎么样？」→ WEB_SEARCH"
    "\n「对比一下React和Vue」→ CHAT"
    "\n「有哪些好用的AI编程工具？」→ CHAT"
    "\n「现在学Python好还是Go好？」→ CHAT"
    "\n「当前WebAssembly的发展状况」→ CHAT"
    "\n「现在大数据技术发展到什么阶段了？」→ CHAT"
    "\n「有哪些免费的AI课程推荐？」→ CHAT"
    "\n「什么是闭包？」→ CHAT"
    "\n「你好/谢谢」→ CHAT"
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
    r"排名|份额|市场占有率|政策|法规)"
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
    history: Optional[list] = None,
    previous_intent: Optional[int] = None,
) -> tuple:
    """
    分类用户意图（支持多轮对话上下文）。

    Args:
        llm: OpenAI 兼容客户端实例
        query: 用户问题
        model: 模型名
        enabled: 是否启用意图识别
        history: 最近对话历史 [{"role": ..., "content": ...}]（可选）
        previous_intent: 上一轮意图代码（可选）

    Returns:
        (IntentCode, source_label)
        source_label: "llm" | "keyword" | "disabled"
    """
    if not enabled:
        return IntentCode.CHAT, "disabled"

    if not llm:
        return _keyword_intent(query), "keyword"

    # 构建多轮上下文提示
    context_hint = ""
    if previous_intent is not None and history:
        # 提取最近 2 轮对话的关键信息
        recent = history[-4:]  # 最近 4 条（2 轮）
        if recent:
            prev_label = {0: "CHAT", 1: "RAG", 2: "WEB_SEARCH"}.get(previous_intent, "CHAT")
            context_hint = f"\n\n对话上下文（有助于理解指代和追问）："
            context_hint += f"\n- 上一轮意图: {prev_label}"
            for m in recent[-2:]:  # 最近一轮
                role = "用户" if m["role"] == "user" else "助手"
                snippet = m["content"][:80].replace("\n", " ")
                context_hint += f"\n- {role}: {snippet}..."
            context_hint += "\n注意：如果当前问题是接着上一轮的追问（如'Java的呢？''那门课多少钱？'），请结合上下文判断，而非把省略表达当作闲聊。"

    try:
        response = llm.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT + context_hint},
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
