"""
多轮任务路由模块 — 意图引导与任务状态管理

功能：
1. 问题复杂度判断（简单/中等/复杂）
2. 多轮任务类型识别与路由
3. 任务状态机管理（clarifying → gathering → reasoning → answering → done）
4. 缺失信息检测与澄清问题生成
5. 执行计划生成与追踪

参考：A2阶段 chat_history 管理经验
"""
import json
import re
from dataclasses import dataclass, field, asdict
from enum import Enum, IntEnum
from typing import Optional, List, Dict, Any


# ── 枚举定义 ────────────────────────────────────────

class ComplexityLevel(IntEnum):
    """问题复杂度等级"""
    SIMPLE = 1    # 简单：单轮可答，无需额外信息
    MEDIUM = 2    # 中等：需要1-2轮澄清
    COMPLEX = 3   # 复杂：需要多轮信息收集 + 方案制定


class TaskType(str, Enum):
    """任务类型"""
    DIRECT_ANSWER = "direct_answer"      # 直接回答（问候、简单事实）
    COURSE_INQUIRY = "course_inquiry"    # 课程咨询
    TECH_QUESTION = "tech_question"      # 技术问题
    COMPARISON = "comparison"            # 对比分析
    CAREER_GUIDANCE = "career_guidance"  # 职业规划
    STUDY_PLAN = "study_plan"            # 学习规划


class TaskStage(str, Enum):
    """任务阶段"""
    ANALYZING = "analyzing"       # 正在分析问题
    CLARIFYING = "clarifying"     # 需要澄清/追问
    GATHERING = "gathering"       # 信息收集中（调用工具）
    REASONING = "reasoning"       # 综合分析中
    ANSWERING = "answering"       # 生成回答
    DONE = "done"                 # 任务完成


# ── 数据结构 ────────────────────────────────────────

@dataclass
class TaskState:
    """
    任务状态 — 持久化在会话级别
    """
    task_type: TaskType = TaskType.DIRECT_ANSWER
    stage: TaskStage = TaskStage.ANALYZING
    complexity: ComplexityLevel = ComplexityLevel.SIMPLE
    
    # 已收集的信息（键值对）
    collected_info: Dict[str, Any] = field(default_factory=dict)
    
    # 待澄清的问题列表
    pending_questions: List[str] = field(default_factory=list)
    
    # 执行计划步骤
    plan_steps: List[Dict[str, Any]] = field(default_factory=list)
    current_step_index: int = 0
    
    # 原始用户意图
    original_intent: int = 0  # 对应 IntentCode
    
    # 是否已经过一轮交互（用于判断是否是多轮对话）
    round_count: int = 0
    
    # 对话主题/上下文关键词（用于多轮关联）
    topic_keywords: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "task_type": self.task_type.value,
            "stage": self.stage.value,
            "complexity": self.complexity.value,
            "collected_info": self.collected_info,
            "pending_questions": self.pending_questions,
            "plan_steps": self.plan_steps,
            "current_step_index": self.current_step_index,
            "original_intent": self.original_intent,
            "round_count": self.round_count,
            "topic_keywords": self.topic_keywords,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TaskState":
        if not data:
            return cls()
        return cls(
            task_type=TaskType(data.get("task_type", "direct_answer")),
            stage=TaskStage(data.get("stage", "analyzing")),
            complexity=ComplexityLevel(data.get("complexity", 1)),
            collected_info=data.get("collected_info", {}),
            pending_questions=data.get("pending_questions", []),
            plan_steps=data.get("plan_steps", []),
            current_step_index=data.get("current_step_index", 0),
            original_intent=data.get("original_intent", 0),
            round_count=data.get("round_count", 0),
            topic_keywords=data.get("topic_keywords", []),
        )
    
    def advance_stage(self):
        """推进到下一阶段"""
        order = [
            TaskStage.ANALYZING,
            TaskStage.CLARIFYING,
            TaskStage.GATHERING,
            TaskStage.REASONING,
            TaskStage.ANSWERING,
            TaskStage.DONE,
        ]
        idx = order.index(self.stage)
        if idx < len(order) - 1:
            self.stage = order[idx + 1]
    
    def is_multi_round(self) -> bool:
        """判断是否是多轮任务"""
        return self.complexity != ComplexityLevel.SIMPLE or self.round_count > 0


@dataclass
class AnalysisResult:
    """单次分析结果"""
    complexity: ComplexityLevel
    task_type: TaskType
    confidence: float  # 0-1
    missing_info: List[str]  # 缺少的信息维度
    suggested_questions: List[str]  # 建议追问
    plan: List[Dict[str, Any]]  # 执行计划
    should_clarify: bool  # 是否需要先澄清
    reason: str  # 判断理由


# ── 复杂度判断规则（规则 + LLM 混合）──────────────────

# 简单问题关键词/模式
_SIMPLE_PATTERNS = [
    re.compile(r"^(你好|您好|嗨|hi|hello|hey)[!！。]?\s*$", re.I),
    re.compile(r"^(谢谢|感谢|多谢)[!！。]?\s*$"),
    re.compile(r"^(再见|拜拜|bye)[!！。]?\s*$", re.I),
    re.compile(r"^(什么|什么是).{1,20}[?？]\s*$"),  # 简单定义
    re.compile(r"^(怎么|如何).{1,20}[?？]\s*$"),   # 简单操作
    re.compile(r"^(多少钱|价格|费用)[?？]?\s*$"),
    re.compile(r"^\d+\s*[\+\-\*\/]\s*\d+\s*$"),  # 计算
]

# 复杂问题关键词（需要多轮信息收集和深度分析）
_COMPLEX_KEYWORDS = re.compile(
    r"(规划|路径|方案|职业规划|学习计划|"
    r"综合考虑|多个方面|优缺点|利弊|"
    r"转行.{1,10}(做|到|成为|进入)|帮我设计|帮我制定|"
    r"从.{1,10}到.{1,10}(的|需要|怎么)|完整路线|系统学习)"
)

# 中等问题关键词
_MEDIUM_KEYWORDS = re.compile(
    r"(推荐|适合|选择|建议|怎么选|哪个好|值得|有必要|"
    r"区别|不同|差异|对比.{1,10}(和|与|vs))"
)


def _rule_based_complexity(query: str, history_len: int) -> tuple:
    """
    基于规则判断复杂度
    
    Returns: (complexity, reason)
    """
    q = query.strip()
    
    # 1. 检查简单模式
    for pattern in _SIMPLE_PATTERNS:
        if pattern.match(q):
            return ComplexityLevel.SIMPLE, "匹配简单问题模式"
    
    # 2. 非常短的问题（< 15字）且没有复杂关键词 → 简单
    if len(q) < 15 and not _COMPLEX_KEYWORDS.search(q) and not _MEDIUM_KEYWORDS.search(q):
        return ComplexityLevel.SIMPLE, "简短且无明显复杂意图"
    
    # 3. 检查复杂关键词
    if _COMPLEX_KEYWORDS.search(q):
        return ComplexityLevel.COMPLEX, "检测到复杂意图关键词"
    
    # 4. 检查中等关键词
    if _MEDIUM_KEYWORDS.search(q):
        return ComplexityLevel.MEDIUM, "检测到中等意图关键词"
    
    # 5. 多轮对话中的简短追问 → 简单
    if history_len > 2 and len(q) < 20:
        return ComplexityLevel.SIMPLE, "多轮对话中的简短追问"
    
    # 默认中等
    return ComplexityLevel.MEDIUM, "默认判定为中等复杂度"


# ── 任务类型识别规则 ────────────────────────────────

_COURSE_KEYWORDS = re.compile(
    r"(课程|课表|大纲|学费|价格|报名|讲师|班级|"
    r"全日制|周末班|线上|线下|试听|训练营|"
    r"学多久|周期|时长|就业|证书)"
)

_CAREER_KEYWORDS = re.compile(
    r"(就业|工作|职业|转行|跳槽|薪资|工资|招聘|"
    r"前景|发展|规划|简历|面试|offer|找工作)"
)

_STUDY_PLAN_KEYWORDS = re.compile(
    r"(学习路径|学习计划|学习路线|怎么学|从.{0,5}开始|"
    r"零基础|入门|进阶|系统|完整路线)"
)

_COMPARISON_KEYWORDS = re.compile(
    r"(对比|比较|区别|差异|优缺点|哪个好|vs|versus|"
    r"选择.{1,10}还是|.{1,10}和.{1,10}哪个)"
)


def _rule_based_task_type(query: str, intent_code: int) -> TaskType:
    """基于规则和意图代码判断任务类型"""
    q = query.strip().lower()
    
    # 意图代码直接映射
    if intent_code == 0:  # CHAT
        # 再细分
        if _COURSE_KEYWORDS.search(q):
            return TaskType.COURSE_INQUIRY
        if _STUDY_PLAN_KEYWORDS.search(q):
            return TaskType.STUDY_PLAN
        if _CAREER_KEYWORDS.search(q):
            return TaskType.CAREER_GUIDANCE
        if _COMPARISON_KEYWORDS.search(q):
            return TaskType.COMPARISON
        return TaskType.DIRECT_ANSWER
    
    if intent_code == 1:  # RAG
        return TaskType.COURSE_INQUIRY
    
    # Web Search 通常是时效性问题，归为直接回答或职业规划
    return TaskType.DIRECT_ANSWER


# ── 缺失信息检测 ────────────────────────────────────

# 各任务类型需要的核心信息维度
_TASK_REQUIRED_INFO = {
    TaskType.COURSE_INQUIRY: {
        "user_background": ("用户背景", ["基础", "经验", "背景", "学过", "工作", "专业"]),
        "learning_goal": ("学习目标", ["目标", "想", "打算", "为了", "成为", "做"]),
        "time_budget": ("时间预算", ["时间", "多久", "每天", "每周", "周期", "几个月"]),
        "budget": ("费用预算", ["预算", "钱", "价格", "学费", "承受", "贵"]),
    },
    TaskType.STUDY_PLAN: {
        "current_level": ("当前水平", ["基础", "零基础", "入门", "有经验", "学过"]),
        "target": ("目标方向", ["目标", "想做", "方向", "成为", "就业"]),
        "time_available": ("可用时间", ["时间", "多久", "每天", "几个月"]),
    },
    TaskType.CAREER_GUIDANCE: {
        "current_situation": ("当前状况", ["现在", "目前", "工作", "专业", "经验"]),
        "target_field": ("目标领域", ["想", "目标", "转行", "方向"]),
        "location": ("所在城市/意愿", ["城市", "地区", "一线", "老家"]),
    },
    TaskType.COMPARISON: {
        "comparison_target": ("对比对象", ["和", "vs", "与", "还是"]),
        "comparison_dimension": ("对比维度", ["就业", "薪资", "难度", "前景", "效率"]),
    },
}


def _detect_missing_info(query: str, task_type: TaskType) -> List[str]:
    """检测当前查询中缺失的关键信息"""
    if task_type not in _TASK_REQUIRED_INFO:
        return []
    
    missing = []
    q = query.lower()
    for key, (label, keywords) in _TASK_REQUIRED_INFO[task_type].items():
        # 检查是否提到了这个维度的信息
        has_info = any(kw in q for kw in keywords)
        if not has_info:
            missing.append(label)
    return missing


def _generate_clarifying_questions(
    task_type: TaskType, missing_info: List[str], query: str
) -> List[str]:
    """生成澄清问题"""
    questions = []
    
    templates = {
        "用户背景": [
            "方便了解一下您目前的技术基础吗？（零基础/有编程经验/已工作）",
            "您目前是零基础入门，还是有一定相关经验呢？",
        ],
        "学习目标": [
            "您学习这个主要是出于什么目的？（转行/提升/兴趣/工作需求）",
            "方便说说您的学习目标吗？",
        ],
        "时间预算": [
            "您每天大约能投入多少时间学习？",
            "您希望在多长时间内达到目标？",
        ],
        "费用预算": [
            "您对学习费用的预算范围大概是多少？",
        ],
        "当前水平": [
            "您目前在这个领域是什么水平？",
        ],
        "目标方向": [
            "您更倾向哪个具体方向？",
        ],
        "可用时间": [
            "您每天/每周能投入多少时间？",
        ],
        "当前状况": [
            "能简单介绍一下您目前的情况吗？",
        ],
        "目标领域": [
            "您希望进入哪个具体领域？",
        ],
        "对比维度": [
            "您更关心哪些方面的对比？（薪资/就业/学习难度/发展前景）",
        ],
    }
    
    for info in missing_info[:2]:  # 最多问2个
        if info in templates:
            # 简单用第一个模板，实际可加入更多变体
            questions.append(templates[info][0])
    
    return questions


def _generate_plan_steps(task_type: TaskType, missing_info: List[str]) -> List[Dict[str, Any]]:
    """生成执行计划步骤"""
    base_steps = []
    
    if missing_info:
        base_steps.append({
            "step": 1,
            "title": "信息澄清",
            "description": f"了解用户的{', '.join(missing_info[:2])}等背景信息",
            "status": "pending",
        })
    
    # 根据任务类型添加后续步骤
    type_steps = {
        TaskType.COURSE_INQUIRY: [
            {"step": 2, "title": "资料检索", "description": "检索课程相关资料", "status": "pending"},
            {"step": 3, "title": "方案推荐", "description": "根据背景匹配合适课程", "status": "pending"},
        ],
        TaskType.STUDY_PLAN: [
            {"step": 2, "title": "路径设计", "description": "规划学习阶段与内容", "status": "pending"},
            {"step": 3, "title": "方案输出", "description": "生成完整学习计划", "status": "pending"},
        ],
        TaskType.CAREER_GUIDANCE: [
            {"step": 2, "title": "行业分析", "description": "分析目标行业现状", "status": "pending"},
            {"step": 3, "title": "路径建议", "description": "给出转行/提升建议", "status": "pending"},
        ],
        TaskType.COMPARISON: [
            {"step": 2, "title": "信息收集", "description": "收集对比对象信息", "status": "pending"},
            {"step": 3, "title": "对比分析", "description": "多维度对比分析", "status": "pending"},
        ],
        TaskType.TECH_QUESTION: [
            {"step": 2, "title": "知识检索", "description": "检索相关技术资料", "status": "pending"},
            {"step": 3, "title": "回答生成", "description": "生成技术解答", "status": "pending"},
        ],
    }
    
    extra = type_steps.get(task_type, [
        {"step": 2, "title": "分析处理", "description": "分析问题并生成回答", "status": "pending"},
    ])
    
    # 重新编号
    all_steps = base_steps + extra
    for i, step in enumerate(all_steps, 1):
        step["step"] = i
    
    return all_steps


# ── LLM 增强分析（可选）─────────────────────────────

COMPLEXITY_ANALYSIS_PROMPT = """你是一个问题分析助手。请分析用户输入的问题复杂度，判断需要多少轮交互才能给出满意回答。

复杂度定义：
- 简单(1)：单轮可答，无需额外信息。如：问候、简单事实查询、明确的技术问题。
- 中等(2)：需要1-2轮澄清，补充少量背景信息。如："推荐课程"但没说自己情况。
- 复杂(3)：需要多轮信息收集和深度分析。如："帮我规划从零到AI工程师的学习路径"。

请输出 JSON 格式：
{
  "complexity": 1|2|3,
  "task_type": "direct_answer|course_inquiry|tech_question|comparison|career_guidance|study_plan",
  "missing_info": ["缺失的信息维度"],
  "should_clarify": true|false,
  "reason": "判断理由（一句话）"
}"""


def _llm_analyze_query(llm, query: str, model: str, history: list) -> Optional[AnalysisResult]:
    """使用LLM分析问题（规则无法确定时）"""
    if not llm:
        return None
    
    try:
        # 构建上下文
        history_text = ""
        if history:
            recent = history[-6:]  # 最近6条
            history_text = "\n".join([
                f"{'用户' if m['role'] == 'user' else '助手'}: {m['content'][:100]}"
                for m in recent
            ])
        
        messages = [
            {"role": "system", "content": COMPLEXITY_ANALYSIS_PROMPT},
            {"role": "user", "content": f"对话历史（最近几条）：\n{history_text}\n\n当前问题：{query}"},
        ]
        
        response = llm.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=512,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        
        content = response.choices[0].message.content or "{}"
        result = json.loads(content)
        
        complexity = ComplexityLevel(result.get("complexity", 2))
        task_type = TaskType(result.get("task_type", "direct_answer"))
        missing = result.get("missing_info", [])
        should_clarify = result.get("should_clarify", False)
        reason = result.get("reason", "LLM分析")
        
        # 生成追问
        questions = _generate_clarifying_questions(task_type, missing, query) if should_clarify else []
        
        # 生成计划
        plan = _generate_plan_steps(task_type, missing)
        
        return AnalysisResult(
            complexity=complexity,
            task_type=task_type,
            confidence=0.75,
            missing_info=missing,
            suggested_questions=questions,
            plan=plan,
            should_clarify=should_clarify and len(questions) > 0,
            reason=reason,
        )
    except Exception as e:
        print(f"[TaskRouter] LLM分析失败: {e}")
        return None


# ── 主路由器 ────────────────────────────────────────

class TaskRouter:
    """
    多轮任务路由器
    
    负责：
    1. 接收用户输入 + 当前任务状态
    2. 判断复杂度、任务类型
    3. 决定下一步动作（直接回答 / 澄清追问 / 执行计划）
    4. 更新任务状态
    """
    
    def __init__(self, llm=None, model: str = "", use_llm: bool = True):
        self.llm = llm
        self.model = model
        self.use_llm = use_llm and llm is not None
    
    def analyze(
        self,
        query: str,
        current_state: Optional[TaskState],
        history: list,
        intent_code: int = 0,
    ) -> tuple:
        """
        分析用户输入，返回 (AnalysisResult, updated_state)
        
        Args:
            query: 用户输入
            current_state: 当前任务状态（None表示新会话）
            history: 对话历史
            intent_code: 原始意图代码
        
        Returns:
            (AnalysisResult, TaskState)
        """
        # 1. 初始化/更新状态
        if current_state is None:
            state = TaskState()
        else:
            state = current_state
        
        state.round_count += 1
        state.original_intent = intent_code
        
        # 2. 先尝试规则判断
        rule_complexity, rule_reason = _rule_based_complexity(query, len(history))
        rule_task_type = _rule_based_task_type(query, intent_code)
        
        # 3. 检测缺失信息（基于规则）
        rule_missing = _detect_missing_info(query, rule_task_type)
        rule_questions = _generate_clarifying_questions(rule_task_type, rule_missing, query)
        rule_plan = _generate_plan_steps(rule_task_type, rule_missing)
        
        # 4. 如果是多轮对话（round_count > 1），更新 collected_info
        if state.round_count > 1:
            # 简单信息提取：将用户输入作为补充信息
            state.collected_info[f"round_{state.round_count}"] = query
            # 更新主题关键词
            self._update_topic_keywords(state, query)
        
        # 5. 判断是否需要 LLM 增强分析
        # 规则已经明确为简单，直接走快速通道
        if rule_complexity == ComplexityLevel.SIMPLE:
            result = AnalysisResult(
                complexity=ComplexityLevel.SIMPLE,
                task_type=rule_task_type,
                confidence=0.9,
                missing_info=[],
                suggested_questions=[],
                plan=[{"step": 1, "title": "直接回答", "description": "单轮处理", "status": "in_progress"}],
                should_clarify=False,
                reason=rule_reason,
            )
            state.task_type = rule_task_type
            state.complexity = ComplexityLevel.SIMPLE
            state.stage = TaskStage.ANSWERING
            return result, state
        
        # 6. 规则判为中等/复杂，或 use_llm 开启，尝试 LLM 分析
        if self.use_llm:
            llm_result = _llm_analyze_query(self.llm, query, self.model, history)
            if llm_result:
                # 以LLM结果为主，但置信度低时结合规则
                if llm_result.confidence >= 0.7:
                    result = llm_result
                else:
                    # 混合：取更保守的复杂度
                    final_complexity = max(rule_complexity, llm_result.complexity)
                    result = AnalysisResult(
                        complexity=final_complexity,
                        task_type=llm_result.task_type,
                        confidence=0.65,
                        missing_info=llm_result.missing_info or rule_missing,
                        suggested_questions=llm_result.suggested_questions or rule_questions,
                        plan=llm_result.plan or rule_plan,
                        should_clarify=llm_result.should_clarify or len(rule_questions) > 0,
                        reason=f"规则:{rule_reason} | LLM:{llm_result.reason}",
                    )
                state.task_type = result.task_type
                state.complexity = result.complexity
                state.stage = TaskStage.CLARIFYING if result.should_clarify else TaskStage.GATHERING
                state.pending_questions = result.suggested_questions
                state.plan_steps = result.plan
                return result, state
        
        # 7. 纯规则路径（无LLM或LLM失败）
        should_clarify = len(rule_questions) > 0 and rule_complexity != ComplexityLevel.SIMPLE
        result = AnalysisResult(
            complexity=rule_complexity,
            task_type=rule_task_type,
            confidence=0.7,
            missing_info=rule_missing,
            suggested_questions=rule_questions,
            plan=rule_plan,
            should_clarify=should_clarify,
            reason=rule_reason,
        )
        state.task_type = rule_task_type
        state.complexity = rule_complexity
        state.stage = TaskStage.CLARIFYING if should_clarify else TaskStage.GATHERING
        state.pending_questions = rule_questions
        state.plan_steps = rule_plan
        return result, state
    
    def _update_topic_keywords(self, state: TaskState, query: str):
        """从用户输入中提取主题关键词"""
        # 简单实现：提取技术名词、课程相关词
        tech_keywords = re.findall(
            r"(Python|Java|JavaScript|Go|Rust|C\+\+|前端|后端|"
            r"AI|人工智能|机器学习|深度学习|数据分析|大数据|"
            r"React|Vue|Angular|Node\.js|Django|Flask|Spring|"
            r"全栈|DevOps|云计算|Docker|K8s|Kubernetes|"
            r"算法|数据结构|数据库|MySQL|Redis|MongoDB)",
            query,
            re.I
        )
        for kw in tech_keywords:
            kw_lower = kw.lower()
            if kw_lower not in [k.lower() for k in state.topic_keywords]:
                state.topic_keywords.append(kw)
    
    def should_skip_clarification(self, state: TaskState, query: str) -> bool:
        """
        判断用户本轮输入是否回答了之前的澄清问题
        """
        if state.round_count <= 1:
            return False
        
        # 如果有 pending_questions 且用户输入较长（>10字），认为是补充信息
        if state.pending_questions and len(query.strip()) > 10:
            # 清空待澄清问题，标记信息已收集
            state.pending_questions = []
            state.collected_info["user_response"] = query
            # 推进阶段
            if state.stage == TaskStage.CLARIFYING:
                state.advance_stage()
            return True
        
        return False
    
    def build_system_hint(self, state: TaskState) -> str:
        """
        根据当前任务状态构建系统提示词补充
        """
        hints = []
        
        if state.round_count > 1:
            hints.append(f"当前是第 {state.round_count} 轮对话，请自然延续之前的交流。")
        
        if state.topic_keywords:
            hints.append(f"对话主题涉及: {', '.join(state.topic_keywords[:3])}")
        
        if state.task_type == TaskType.COURSE_INQUIRY:
            hints.append("用户正在咨询课程，请结合课程资料优先回答。")
        elif state.task_type == TaskType.STUDY_PLAN:
            hints.append("用户需要学习规划建议，请给出阶段性、可执行的建议。")
        elif state.task_type == TaskType.CAREER_GUIDANCE:
            hints.append("用户关注职业发展，请给出务实、有数据支撑的建议。")
        elif state.task_type == TaskType.COMPARISON:
            hints.append("用户在做对比分析，请客观呈现各方优缺点。")
        
        if state.collected_info:
            info_items = []
            for k, v in list(state.collected_info.items())[-3:]:  # 最近3条
                if isinstance(v, str) and len(v) < 100:
                    info_items.append(f"- {k}: {v}")
            if info_items:
                hints.append("已收集的信息:\n" + "\n".join(info_items))
        
        return "\n\n".join(hints) if hints else ""
