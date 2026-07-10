"""
后续问题推荐模块 — 基于对话上下文生成智能追问

设计思路：
1. 规则模板为主（低成本、快速、可控）
2. 动态关键词填充（从对话中提取技术/课程/方向名词）
3. 去重过滤（不重复用户已问过的问题）
4. 按任务类型和复杂度调整推荐数量
5. 结合用户画像做个性化（用户背景影响推荐内容）
"""
import re
from typing import List, Dict, Optional, Any


# ── 任务类型 → 推荐模板库 ───────────────────────────

# 课程咨询相关追问
_COURSE_TEMPLATES = [
    "{course}课程的费用是多少？",
    "{course}课程要学多久？",
    "零基础可以学{course}吗？",
    "{course}课程有试听吗？",
    "学完{course}能到什么水平？",
    "{course}课程上课时间怎么安排？",
    "报名{course}需要什么条件？",
    "{course}课程有就业推荐吗？",
    "{course}和{alt_course}哪个更适合我？",
]

# 学习规划相关追问
_STUDY_PLAN_TEMPLATES = [
    "从零到掌握{tech}大概需要多久？",
    "每天学习{tech}需要投入多少时间？",
    "学习{tech}前需要先掌握什么基础知识？",
    "{tech}的学习路线怎么安排比较合理？",
    "学{tech}的过程中有什么常见的坑？",
    "有没有什么好的{tech}学习资源推荐？",
    "学完{tech}后可以做什么方向的工作？",
]

# 职业规划相关追问
_CAREER_TEMPLATES = [
    "{field}方向的就业前景目前怎么样？",
    "{field}岗位的薪资水平大概是多少？",
    "转行做{field}需要多长时间准备？",
    "{field}岗位的面试一般考什么？",
    "没有相关经验怎么进入{field}领域？",
    "{field}和{alt_field}哪个发展更好？",
]

# 技术问题相关追问
_TECH_TEMPLATES = [
    "{tech}和{alt_tech}有什么区别？",
    "实际项目中{tech}是怎么使用的？",
    "使用{tech}需要注意什么常见问题？",
    "学习{tech}之前需要掌握哪些基础知识？",
    "{tech}目前的最新发展趋势是什么？",
    "{tech}适合什么类型的项目？",
]

# 对比分析相关追问
_COMPARISON_TEMPLATES = [
    "如果我是零基础，选{option_a}还是{option_b}更好？",
    "{option_a}和{option_b}在就业方面哪个更有优势？",
    "学完{option_a}和{option_b}后薪资差异大吗？",
    "{option_a}和{option_b}的学习难度分别怎么样？",
    "从长期发展来看，{option_a}和{option_b}哪个更好？",
]

# 通用追问（所有类型都适用）
_GENERAL_TEMPLATES = [
    "能举个实际例子吗？",
    "这个需要多长时间？",
    "费用大概是多少？",
    "零基础能学会吗？",
    "学完后能做什么？",
]


# 任务类型 → 模板映射
_TASK_TYPE_TEMPLATES = {
    "course_inquiry": _COURSE_TEMPLATES,
    "study_plan": _STUDY_PLAN_TEMPLATES,
    "career_guidance": _CAREER_TEMPLATES,
    "tech_question": _TECH_TEMPLATES,
    "comparison": _COMPARISON_TEMPLATES,
    "direct_answer": _GENERAL_TEMPLATES,
}


# ── 关键词提取（用于填充模板）───────────────────────

# 技术/课程名词
_TECH_KEYWORDS = re.compile(
    r"(Python|Java|JavaScript|Go|Rust|C\+\+|C#|"
    r"React|Vue|Angular|Node\.js|Django|Flask|Spring|"
    r"前端|后端|全栈|AI|人工智能|机器学习|深度学习|"
    r"数据分析|大数据|算法|数据结构|数据库|"
    r"云计算|DevOps|Docker|Kubernetes|K8s|"
    r"测试|运维|安全|产品|运营)",
    re.I
)

# 职业方向
_FIELD_KEYWORDS = re.compile(
    r"(程序员|开发工程师|数据分析师|算法工程师|"
    r"AI工程师|人工智能工程师|产品经理|测试工程师|"
    r"运维工程师|DevOps工程师|全栈工程师|前端工程师|"
    r"后端工程师|Java工程师|Python工程师|数据科学家|"
    r"技术总监|架构师|CTO)",
    re.I
)


def _extract_tech_keywords(text: str) -> List[str]:
    """从文本中提取技术关键词"""
    found = _TECH_KEYWORDS.findall(text)
    # 去重并保留大小写
    seen = set()
    result = []
    for kw in found:
        kw_lower = kw.lower()
        if kw_lower not in seen:
            seen.add(kw_lower)
            result.append(kw)
    return result


def _extract_field_keywords(text: str) -> List[str]:
    """从文本中提取职业方向关键词"""
    found = _FIELD_KEYWORDS.findall(text)
    seen = set()
    result = []
    for kw in found:
        kw_lower = kw.lower()
        if kw_lower not in seen:
            seen.add(kw_lower)
            result.append(kw)
    return result


# ── 模板填充 ────────────────────────────────────────

def _fill_template(template: str, keywords: List[str]) -> str:
    """用关键词填充模板"""
    result = template
    
    # 填充 {course} / {tech} / {field}
    if keywords:
        result = result.replace("{course}", keywords[0])
        result = result.replace("{tech}", keywords[0])
        result = result.replace("{field}", keywords[0])
    
    # 填充替代项（如果存在）
    if len(keywords) >= 2:
        result = result.replace("{alt_course}", keywords[1])
        result = result.replace("{alt_tech}", keywords[1])
        result = result.replace("{alt_field}", keywords[1])
    else:
        # 没有替代项时，用通用词替换
        result = result.replace("{alt_course}", "其他")
        result = result.replace("{alt_tech}", "其他技术")
        result = result.replace("{alt_field}", "其他方向")
    
    # 对比模板特殊处理
    if "{option_a}" in result:
        if len(keywords) >= 2:
            result = result.replace("{option_a}", keywords[0])
            result = result.replace("{option_b}", keywords[1])
        else:
            # 对比模板但没有两个关键词，不返回
            return ""
    
    return result


def _deduplicate_and_filter(
    candidates: List[str],
    asked_questions: List[str],
    min_len: int = 8,
) -> List[str]:
    """
    去重过滤候选问题。
    
    Args:
        candidates: 候选问题列表
        asked_questions: 用户已问过的问题
        min_len: 最小长度过滤
    
    Returns:
        过滤后的候选列表
    """
    seen = set()
    result = []
    
    # 标准化已问问题（用于去重）
    asked_normalized = set()
    for q in asked_questions:
        # 简单标准化：去除标点、空格、转小写
        normalized = re.sub(r"[\s?？,，.。!！]", "", q).lower()
        asked_normalized.add(normalized)
    
    for c in candidates:
        if not c or len(c) < min_len:
            continue
        
        # 标准化候选
        normalized = re.sub(r"[\s?？,，.。!！]", "", c).lower()
        
        # 检查是否已问过（相似度匹配）
        if normalized in asked_normalized:
            continue
        
        # 检查是否重复（候选列表内部）
        if normalized in seen:
            continue
        
        # 检查是否包含未填充的模板变量
        if re.search(r"\{[a-z_]+\}", c):
            continue
        
        seen.add(normalized)
        result.append(c)
    
    return result


# ── 主推荐引擎 ──────────────────────────────────────

class SuggestionEngine:
    """
    后续问题推荐引擎
    
    用法：
        engine = SuggestionEngine()
        suggestions = engine.generate(
            task_type="course_inquiry",
            history=[...],
            user_profile={...},
            count=3,
        )
    """
    
    def __init__(self):
        pass
    
    def generate(
        self,
        task_type: str,
        history: List[Dict[str, str]],
        user_profile: Optional[Dict[str, Any]] = None,
        count: int = 3,
    ) -> List[str]:
        """
        生成推荐问题列表。
        
        Args:
            task_type: 任务类型（如 course_inquiry）
            history: 对话历史
            user_profile: 用户画像（可选）
            count: 推荐数量
        
        Returns:
            推荐问题列表（去重、过滤后）
        """
        # 1. 收集所有对话文本（用于提取关键词）
        all_text = ""
        asked_questions = []
        for msg in history:
            content = msg.get("content", "")
            if msg.get("role") == "user":
                all_text += content + "\n"
                asked_questions.append(content)
            else:
                all_text += content[:500] + "\n"  # 助手回答只取前500字
        
        if not all_text:
            return []
        
        # 2. 提取关键词
        tech_keywords = _extract_tech_keywords(all_text)
        field_keywords = _extract_field_keywords(all_text)
        all_keywords = tech_keywords + field_keywords
        
        # 3. 获取模板
        templates = _TASK_TYPE_TEMPLATES.get(task_type, _GENERAL_TEMPLATES)
        
        # 4. 填充模板
        candidates = []
        for tpl in templates:
            filled = _fill_template(tpl, all_keywords)
            if filled:
                candidates.append(filled)
        
        # 5. 添加通用追问（补充）
        for tpl in _GENERAL_TEMPLATES:
            if task_type != "direct_answer":  # 通用类型已包含通用模板
                filled = _fill_template(tpl, all_keywords)
                if filled:
                    candidates.append(filled)
        
        # 6. 去重过滤
        candidates = _deduplicate_and_filter(candidates, asked_questions)
        
        # 7. 个性化调整（根据用户画像）
        if user_profile:
            candidates = self._personalize(candidates, user_profile, all_keywords)
        
        # 8. 截断到指定数量
        return candidates[:count]
    
    def _personalize(
        self,
        candidates: List[str],
        profile: Dict[str, Any],
        keywords: List[str],
    ) -> List[str]:
        """
        根据用户画像个性化推荐。
        
        策略：
        - 零基础 → 优先推荐"零基础能学吗""需要先学什么"
        - 转行 → 优先推荐"就业前景""薪资"
        - 有经验 → 优先推荐"进阶""提升"
        """
        background = profile.get("background", "")
        goal = profile.get("learning_goal", "")
        
        scored = []
        for c in candidates:
            score = 0
            # 基础匹配
            if background == "零基础":
                if "零基础" in c or "基础" in c:
                    score += 3
                if "先掌握" in c or "前置" in c:
                    score += 2
            elif background == "转行":
                if "就业" in c or "前景" in c or "薪资" in c:
                    score += 3
                if "准备" in c or "面试" in c:
                    score += 2
            elif background == "有经验":
                if "进阶" in c or "提升" in c or "深入" in c:
                    score += 3
            
            # 目标匹配
            if "转行" in goal and ("转行" in c or "跨行" in c):
                score += 2
            if "就业" in goal and ("就业" in c or "找工作" in c):
                score += 2
            if "提升" in goal and ("进阶" in c or "深入" in c):
                score += 2
            
            scored.append((score, c))
        
        # 按分数排序（高分数优先）
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored]
    
    def generate_from_answer(
        self,
        answer: str,
        task_type: str,
        history: List[Dict[str, str]],
        user_profile: Optional[Dict[str, Any]] = None,
        count: int = 3,
    ) -> List[str]:
        """
        基于最新回答生成追问。
        与 generate 的区别：额外考虑 answer 内容中的信息。
        """
        # 将 answer 追加到 keywords 提取源
        all_text = answer[:1000]  # 取回答前1000字
        for msg in history[-4:]:  # 最近4条
            all_text += "\n" + msg.get("content", "")[:500]
        
        tech_keywords = _extract_tech_keywords(all_text)
        field_keywords = _extract_field_keywords(all_text)
        all_keywords = tech_keywords + field_keywords
        
        asked_questions = [msg.get("content", "") for msg in history if msg.get("role") == "user"]
        
        templates = _TASK_TYPE_TEMPLATES.get(task_type, _GENERAL_TEMPLATES)
        candidates = []
        for tpl in templates:
            filled = _fill_template(tpl, all_keywords)
            if filled:
                candidates.append(filled)
        
        candidates = _deduplicate_and_filter(candidates, asked_questions)
        
        if user_profile:
            candidates = self._personalize(candidates, user_profile, all_keywords)
        
        return candidates[:count]


# ── 便捷函数 ────────────────────────────────────────

def generate_suggestions(
    task_type: str,
    history: List[Dict[str, str]],
    user_profile: Optional[Dict[str, Any]] = None,
    count: int = 3,
) -> List[str]:
    """便捷函数：生成推荐问题"""
    engine = SuggestionEngine()
    return engine.generate(task_type, history, user_profile, count)
