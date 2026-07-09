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
                "用户询问需要实时/时效性/最新数据的信息。关键特征：问题答案会随时间变化。"
                "包括：最新版本特性、当前市场行情、行业新闻动态、招聘薪资数据、"
                "2024-2026年趋势、政策法规变动、近期事件、明确包含时间词的查询。"
                "注意：基础概念对比（如'React和Vue的区别'）不需要网络搜索——"
                "这些知识是稳定的，模型可以直接回答。"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_intent_chat",
            "description": (
                "用户进行普通对话、闲聊、问候、感谢、询问助手功能、表达情绪、"
                "简单常识问答、编程技术基础知识问答、编程求助。"
                "关键特征：答案不依赖实时数据，属于模型训练数据中已有的稳定知识。"
                "包括：语言语法特性、算法概念、框架架构原理、基础技术概念对比（如React vs Vue）、"
                "编程调试求助、代码编写、以及其他无法明确归为课程咨询或实时查询的对话。"
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
    "\n\n核心判断法则：这个问题需要一个\"今天的答案\"还是\"不变的答案\"？"
    "\n- \"不变的答案\"（概念定义、语法规则、架构原理、基础对比、工具推荐）→ 直接对话"
    "\n- \"今天的答案\"（最新版本、市场份额、薪资行情、近期事件）→ 网络搜索"
    "\n- 课程内部信息（大纲、价格、讲师、就业、课程涉及的工具和技能）→ RAG检索"
    "\n\n分类规则："
    "\n- RAG检索：用户询问课程内部资料——课程内容、大纲、价格、讲师、学习路径、"
    "课程对比、课程效果、课程就业方向、课程中会用到哪些工具/技能、FAQ等。"
    "关键：只要是在询问本机构课程的具体信息，即使措辞泛化也应归为RAG。"
    "\n- 网络搜索：用户询问需要实时/时效性数据的问题。"
    "关键特征：答案会随时间变化，不查最新数据就无法准确回答。"
    "例如：最新版本特性（含明确版本号如React 19）、当前市场行情、行业新闻、"
    "招聘薪资数据、2024-2026年的趋势、政策法规变动。"
    "注意：单纯的工具推荐或语言选型问题不需要搜索——"
    "这些模型可以直接基于稳定知识回答。"
    "\n- 直接对话：普通闲聊、问候、感谢、常识问答、编程技术知识问答、"
    "基础概念对比、工具/语言推荐。"
    "所有不涉及课程资料也不需要实时数据的对话。"
    "\n\n示例："
    "\n「Python数据分析课程学什么？」→ RAG检索"
    "\n「这门课多少钱？」→ RAG检索"
    "\n「数据分析需要用到哪些工具？」→ RAG检索"
    "\n「Python怎么样？」→ RAG检索"
    "\n「零基础能学会吗？」→ RAG检索"
    "\n「学完能找什么工作？」→ RAG检索"
    "\n「报班学习和自学哪个好？」→ RAG检索"
    "\n「全日制和周末班什么区别？」→ RAG检索"
    "\n「2025年AI行业最新趋势是什么？」→ 网络搜索"
    "\n「DeepSeek最新版本有什么新功能？」→ 网络搜索"
    "\n「学Python还是JavaScript对找工作更有帮助？」→ 网络搜索"
    "\n「2026年前端框架市场份额排名」→ 网络搜索"
    "\n「学完Python能找到工作吗？最近市场怎么样？」→ 网络搜索"
    "\n「对比一下React和Vue」→ 直接对话"
    "\n「React和Vue的区别是什么？」→ 直接对话"
    "\n「现在学Python好还是Go好？」→ 直接对话"
    "\n「有哪些好用的AI编程工具？」→ 直接对话"
    "\n「现在大数据技术发展到什么阶段了？」→ 直接对话"
    "\n「Python和Java语法上有什么区别？」→ 直接对话"
    "\n「什么是闭包？」→ 直接对话"
    "\n「Django和Flask的架构区别」→ 直接对话"
    "\n「帮我写一段排序代码」→ 直接对话"
    "\n「什么是Python？」→ 直接对话"
    "\n「你好」→ 直接对话"
    "\n「谢谢你的帮助」→ 直接对话"
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
