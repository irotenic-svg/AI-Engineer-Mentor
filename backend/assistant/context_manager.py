"""
对话上下文管理模块 — 智能上下文压缩、会话摘要、用户画像提取

核心功能：
1. 基于 token 估算的上下文压缩（保留最近完整对话 + 远期摘要）
2. 会话摘要生成（对话主题、用户需求、已确认信息）
3. 用户画像提取（技术背景、学习目标、偏好，跨会话持久化）

参考：A2阶段 chat_history 管理方法
"""
import json
import re
from typing import List, Dict, Optional, Any


# ── Token 估算（简单字符法，无需 tiktoken）────────────────

def estimate_tokens(text: str) -> int:
    """
    粗略估算文本 token 数。
    中文：1字 ≈ 1.5 token，英文：1词 ≈ 1.3 token，混合取平均。
    """
    if not text:
        return 0
    # 中文/日文/韩文字符数
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]", text))
    # 其他字符（按空白分词估算）
    other_chars = len(text) - cjk_chars
    other_words = len(text.split())
    # 混合估算
    return int(cjk_chars * 1.5 + other_words * 1.3 + other_chars * 0.3)


def estimate_messages_tokens(messages: List[Dict[str, str]]) -> int:
    """估算消息列表的总 token 数（含角色标记开销）"""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        total += estimate_tokens(content)
        total += 4  # role + 格式开销
    return total


# ── 上下文压缩策略 ──────────────────────────────────

# 默认上下文 token 预算（留给历史消息的部分）
DEFAULT_CONTEXT_BUDGET = 3500  # 假设总预算 4096，系统提示词+上下文占 3500
# 保留最近完整对话的轮数
RECENT_PRESERVE_ROUNDS = 6  # 最近3轮 QA（6条消息）
# 摘要触发阈值：当历史消息超过此轮数时生成摘要
SUMMARY_TRIGGER_ROUNDS = 10


class ContextManager:
    """
    对话上下文管理器
    
    负责：
    - 将原始历史消息压缩到 token 预算内
    - 生成/维护会话摘要
    - 提取/更新用户画像
    """

    def __init__(self, context_budget: int = DEFAULT_CONTEXT_BUDGET):
        self.context_budget = context_budget
        self.recent_preserve = RECENT_PRESERVE_ROUNDS

    # ── 核心接口：压缩历史消息 ──

    def compress_history(
        self,
        history: List[Dict[str, str]],
        session_summary: Optional[str] = None,
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        """
        将完整历史消息压缩到 token 预算内。
        
        策略：
        1. 如果总历史在预算内 → 保留全部
        2. 超出预算 → 保留最近 N 轮完整对话，对早期对话做摘要
        3. 如果已有会话摘要 → 用摘要替代早期对话
        
        Args:
            history: 原始历史消息 [{role, content}]
            session_summary: 已有的会话摘要文本
            user_profile: 用户画像字典
        
        Returns:
            压缩后的消息列表（可直接注入 LLM messages）
        """
        if not history:
            return []

        total_tokens = estimate_messages_tokens(history)
        if total_tokens <= self.context_budget:
            return history

        # 超出预算：拆分近期和远期
        recent_msgs = history[-self.recent_preserve:]
        early_msgs = history[:-self.recent_preserve]

        # 如果已有会话摘要，直接用它替代早期对话
        if session_summary:
            summary_msg = {
                "role": "system",
                "content": f"【会话摘要】\n{session_summary}",
            }
            return [summary_msg] + recent_msgs

        # 没有摘要：对早期对话做规则摘要
        early_summary = self._summarize_messages_rule_based(early_msgs)
        if early_summary:
            summary_msg = {
                "role": "system",
                "content": f"【对话前文摘要】\n{early_summary}",
            }
            return [summary_msg] + recent_msgs

        # 兜底：直接截断到最近保留轮数
        return recent_msgs

    # ── 规则摘要（无需LLM，低成本）──────────────────

    def _summarize_messages_rule_based(self, messages: List[Dict[str, str]]) -> str:
        """
        基于规则对历史消息做摘要。
        提取关键信息点，而非完整对话。
        """
        if not messages:
            return ""

        # 收集用户问题要点
        user_points = []
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")[:200]  # 截断
                # 提取关键信息（去除问候、感谢等噪音）
                if len(content) > 10 and not self._is_noise(content):
                    user_points.append(content)

        # 收集助手回答要点（只取第一句/结论）
        assistant_points = []
        for msg in messages:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                first_sentence = content.split("。")[0].split("\n")[0][:150]
                if len(first_sentence) > 10:
                    assistant_points.append(first_sentence)

        if not user_points and not assistant_points:
            return ""

        parts = []
        if user_points:
            parts.append("已讨论的问题：" + "；".join(user_points[-3:]))  # 最近3个
        if assistant_points:
            parts.append("已给出的要点：" + "；".join(assistant_points[-3:]))

        return "\n".join(parts)

    @staticmethod
    def _is_noise(text: str) -> bool:
        """判断是否是噪音信息（问候、感谢等）"""
        noise_patterns = [
            r"^(你好|您好|嗨|hi|hello|hey)[!！]?\s*$",
            r"^(谢谢|感谢|多谢|不客气)[!！]?\s*$",
            r"^(再见|拜拜|bye)[!！]?\s*$",
            r"^(好的|OK|ok|嗯|哦)[!！]?\s*$",
        ]
        for pattern in noise_patterns:
            if re.search(pattern, text.strip(), re.I):
                return True
        return False

    # ── 会话摘要生成（更完整的版本）──────────────────

    def generate_session_summary(
        self,
        history: List[Dict[str, str]],
        existing_summary: Optional[str] = None,
    ) -> str:
        """
        生成会话摘要。用于定期保存到数据库，替代早期对话。
        
        采用规则提取，不需要调用LLM（节省成本）。
        """
        if not history or len(history) < 4:
            return existing_summary or ""

        # 提取所有用户问题
        user_queries = []
        for msg in history:
            if msg.get("role") == "user":
                q = msg.get("content", "").strip()[:300]
                if q and not self._is_noise(q):
                    user_queries.append(q)

        # 提取助手回答中的关键信息（课程名、价格、时间等）
        key_info = []
        for msg in history:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                # 提取课程相关信息
                course_info = self._extract_course_info(content)
                if course_info:
                    key_info.extend(course_info)
                # 提取技术相关推荐
                tech_info = self._extract_tech_info(content)
                if tech_info:
                    key_info.extend(tech_info)

        # 去重并截断
        key_info = list(dict.fromkeys(key_info))[:8]
        user_queries = user_queries[-5:]  # 最近5个问题

        parts = []
        if user_queries:
            parts.append(f"对话主题：{'；'.join(user_queries)}")
        if key_info:
            parts.append(f"已确认信息：{'；'.join(key_info)}")

        summary = "\n".join(parts)

        # 如果有已有摘要，合并
        if existing_summary:
            summary = f"{existing_summary}\n\n[后续对话]\n{summary}"

        return summary[:1500]  # 控制摘要长度

    @staticmethod
    def _extract_course_info(text: str) -> List[str]:
        """从文本中提取课程相关信息"""
        info = []
        # 价格
        price = re.findall(r"(\d+\s*万|\d{3,5}\s*元|学费\s*[:：]?\s*\d+)", text)
        if price:
            info.append(f"价格相关：{price[0]}")
        # 时长
        duration = re.findall(r"(\d+\s*个月|\d+\s*周|\d+\s*天|周期\s*[:：]?\s*\d+)", text)
        if duration:
            info.append(f"时长：{duration[0]}")
        # 课程名
        courses = re.findall(r"(《.+?》|Python|Java|前端|后端|AI|数据分析|人工智能|机器学习)", text)
        if courses:
            info.append(f"涉及课程：{'、'.join(list(dict.fromkeys(courses))[:3])}")
        return info

    @staticmethod
    def _extract_tech_info(text: str) -> List[str]:
        """从文本中提取技术相关信息"""
        info = []
        # 技术栈
        techs = re.findall(
            r"(Python|Java|JavaScript|Go|Rust|React|Vue|Angular|"
            r"Node\.js|Django|Flask|Spring|TensorFlow|PyTorch|"
            r"Docker|K8s|Kubernetes|MySQL|Redis|MongoDB)",
            text, re.I
        )
        if techs:
            unique = list(dict.fromkeys([t.lower() for t in techs]))[:5]
            info.append(f"技术栈：{'、'.join(unique)}")
        return info

    # ── 用户画像提取 ────────────────────────────────

    def extract_user_profile(self, history: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        从对话历史中抽取用户画像。
        返回结构化数据，可保存到 users 表。
        """
        profile = {
            "background": None,       # 零基础/有经验/转行
            "learning_goal": None,    # 学习目标
            "preferred_tech": [],     # 偏好技术方向
            "time_budget": None,      # 时间预算
            "money_budget": None,     # 费用预算
            "location": None,         # 所在城市/地区
            "extracted_at": None,     # 提取时间
        }

        all_text = ""
        for msg in history:
            if msg.get("role") == "user":
                all_text += msg.get("content", "") + "\n"

        if not all_text:
            return profile

        # 1. 技术背景
        if re.search(r"零基础|没学过|小白|新手|入门|刚开始", all_text):
            profile["background"] = "零基础"
        elif re.search(r"转行|转岗|跨行|之前做", all_text):
            profile["background"] = "转行"
        elif re.search(r"有经验|工作\d+年|做过|熟悉|了解", all_text):
            profile["background"] = "有经验"

        # 2. 学习目标
        goals = []
        if re.search(r"转行|转岗|跨行", all_text):
            goals.append("转行")
        if re.search(r"就业|找工作|求职|offer", all_text):
            goals.append("就业")
        if re.search(r"提升|进阶|升职|加薪|深入", all_text):
            goals.append("提升")
        if re.search(r"兴趣|爱好|自学|了解", all_text):
            goals.append("兴趣")
        if goals:
            profile["learning_goal"] = "、".join(goals)

        # 3. 偏好技术方向
        tech_keywords = re.findall(
            r"(Python|Java|JavaScript|Go|前端|后端|全栈|"
            r"AI|人工智能|机器学习|深度学习|数据分析|大数据|"
            r"算法|云计算|DevOps|运维|测试|安全)",
            all_text, re.I
        )
        if tech_keywords:
            profile["preferred_tech"] = list(dict.fromkeys([t.lower() for t in tech_keywords]))[:5]

        # 4. 时间预算
        time_match = re.search(r"(\d+\s*个月|\d+\s*周|每天\s*\d+\s*小时|全职|兼职|周末)", all_text)
        if time_match:
            profile["time_budget"] = time_match.group(1)

        # 5. 费用预算
        money_match = re.search(r"(\d+\s*万以内|\d+\s*千以内|预算\s*\d+|便宜|贵)", all_text)
        if money_match:
            profile["money_budget"] = money_match.group(1)

        # 6. 所在城市
        city_match = re.search(r"(北京|上海|广州|深圳|杭州|成都|武汉|西安|南京|长沙|"
                               r"一线|二线|老家|家乡|本地|remote|远程)", all_text)
        if city_match:
            profile["location"] = city_match.group(1)

        return {k: v for k, v in profile.items() if v is not None}

    def build_profile_hint(self, profile: Dict[str, Any]) -> str:
        """根据用户画像生成系统提示词补充"""
        if not profile:
            return ""

        hints = []
        if profile.get("background"):
            hints.append(f"用户背景：{profile['background']}")
        if profile.get("learning_goal"):
            hints.append(f"学习目标：{profile['learning_goal']}")
        if profile.get("preferred_tech"):
            hints.append(f"关注方向：{'、'.join(profile['preferred_tech'])}")
        if profile.get("time_budget"):
            hints.append(f"时间情况：{profile['time_budget']}")
        if profile.get("money_budget"):
            hints.append(f"费用考量：{profile['money_budget']}")
        if profile.get("location"):
            hints.append(f"地区：{profile['location']}")

        if hints:
            return "【用户画像】\n" + "\n".join(hints) + "\n请在回答中适当参考以上信息。"
        return ""


# ── 便捷函数（模块级）─────────────────────────────

def build_context_aware_messages(
    system_prompt: str,
    history: List[Dict[str, str]],
    current_question: str,
    session_summary: Optional[str] = None,
    user_profile: Optional[Dict[str, Any]] = None,
    task_hint: Optional[str] = None,
    context_budget: int = DEFAULT_CONTEXT_BUDGET,
) -> List[Dict[str, str]]:
    """
    构建注入上下文的完整消息列表（智能压缩版）。
    
    这是 prompts.py 中 build_messages_with_context 的增强替代。
    """
    manager = ContextManager(context_budget)

    # 1. 压缩历史
    compressed_history = manager.compress_history(
        history, session_summary, user_profile
    )

    # 2. 组装消息
    messages = [{"role": "system", "content": system_prompt}]

    # 3. 注入用户画像（如果有）
    profile_hint = manager.build_profile_hint(user_profile) if user_profile else ""
    if profile_hint:
        messages[0]["content"] += f"\n\n{profile_hint}"

    # 4. 注入任务路由 hint（如果有）
    if task_hint:
        messages[0]["content"] += f"\n\n{task_hint}"

    # 5. 添加压缩后的历史
    for msg in compressed_history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # 6. 添加当前问题
    messages.append({"role": "user", "content": current_question})

    return messages


def generate_summary(history: List[Dict[str, str]], existing: Optional[str] = None) -> str:
    """便捷函数：生成会话摘要"""
    return ContextManager().generate_session_summary(history, existing)


def extract_profile(history: List[Dict[str, str]]) -> Dict[str, Any]:
    """便捷函数：提取用户画像"""
    return ContextManager().extract_user_profile(history)
