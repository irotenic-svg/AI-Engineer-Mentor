"""
意图识别评估脚本 — 验证 98%+ 准确率

用法: python scripts/eval_intents.py
"""
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_DIR = _PROJECT_ROOT / "backend"
sys.path.insert(0, str(_BACKEND_DIR))

from config import load_settings
from llm import create_llm
from assistant.intents import detect_intent, IntentCode, _keyword_intent

# ── 100 条标注测试集 ──
# expected: 0=CHAT, 1=RAG, 2=WEB_SEARCH

TEST_CASES = [
    # ===== RAG (课程知识库) — 35 条 =====
    {"query": "Python数据分析课程学什么？", "expected": 1},
    {"query": "这门课多少钱？", "expected": 1},
    {"query": "零基础能学会吗？", "expected": 1},
    {"query": "学完能找什么工作？", "expected": 1},
    {"query": "全日制和周末班什么区别？", "expected": 1},
    {"query": "课程大纲包含哪些内容？", "expected": 1},
    {"query": "上课时间是怎样的？", "expected": 1},
    {"query": "讲师是谁？有什么背景？", "expected": 1},
    {"query": "报名流程是怎么样的？", "expected": 1},
    {"query": "有没有优惠活动？", "expected": 1},
    {"query": "课程适合什么样的人学习？", "expected": 1},
    {"query": "需要什么前置知识？", "expected": 1},
    {"query": "结课后有证书吗？", "expected": 1},
    {"query": "学习周期多长？", "expected": 1},
    {"query": "Python课程和Java课程有什么区别？", "expected": 1},
    {"query": "数据分析课程的就业率怎么样？", "expected": 1},
    {"query": "有线上课程吗？", "expected": 1},
    {"query": "课程内容包括机器学习吗？", "expected": 1},
    {"query": "实操项目多不多？", "expected": 1},
    {"query": "老师教学经验丰富吗？", "expected": 1},
    {"query": "试听课在哪里可以看？", "expected": 1},
    {"query": "课程对比：前端和后端", "expected": 1},
    {"query": "学完课程能做数据分析师吗？", "expected": 1},
    {"query": "推荐一门适合我的课程", "expected": 1},
    {"query": "学费可以分期吗？", "expected": 1},
    {"query": "周末班的具体时间安排？", "expected": 1},
    {"query": "课程案例都是真实项目吗？", "expected": 1},
    {"query": "学完能达到什么水平？", "expected": 1},
    {"query": "这个课程和B站的免费教程有什么不同？", "expected": 1},
    {"query": "在校学生有优惠吗？", "expected": 1},
    {"query": "课程更新频率是怎样的？", "expected": 1},
    {"query": "有没有一对一辅导？", "expected": 1},
    {"query": "Python基础和进阶课程怎么衔接？", "expected": 1},
    {"query": "数据分析需要用到哪些工具？", "expected": 1},
    {"query": "学完有推荐就业吗？", "expected": 1},

    # ===== Web Search (网络搜索) — 30 条 =====
    {"query": "2025年AI行业最新趋势是什么？", "expected": 2},
    {"query": "React和Vue哪个好？", "expected": 2},
    {"query": "DeepSeek最新版本有什么新功能？", "expected": 2},
    {"query": "今天天气怎么样？", "expected": 2},
    {"query": "Python和Java哪个更适合新手？", "expected": 2},
    {"query": "最近有什么AI新闻？", "expected": 2},
    {"query": "当前数据分析师的薪资水平如何？", "expected": 2},
    {"query": "2024年最火的编程语言排名", "expected": 2},
    {"query": "最新的GPT模型有什么能力？", "expected": 2},
    {"query": "Vue 3和Vue 2的主要区别", "expected": 2},
    {"query": "现在学Python好还是Go好？", "expected": 2},
    {"query": "目前市场上AI工程师的需求量大吗？", "expected": 2},
    {"query": "Claude和ChatGPT对比", "expected": 2},
    {"query": "今年前端开发的技术趋势", "expected": 2},
    {"query": "哪些公司在招聘AI工程师？", "expected": 2},
    {"query": "最新的Python版本有什么更新？", "expected": 2},
    {"query": "现在大数据技术发展到什么阶段了？", "expected": 2},
    {"query": "2026年IT行业就业前景", "expected": 2},
    {"query": "Rust语言值得学吗？最新发展怎么样？", "expected": 2},
    {"query": "有哪些好用的AI编程工具？", "expected": 2},
    {"query": "最近有没有重要的技术大会？", "expected": 2},
    {"query": "Flutter和React Native怎么选？", "expected": 2},
    {"query": "当前WebAssembly的发展状况", "expected": 2},
    {"query": "人工智能行业的最新政策法规", "expected": 2},
    {"query": "有哪些免费的AI课程推荐？", "expected": 2},
    {"query": "现在区块链技术还火吗？", "expected": 2},
    {"query": "edge computing最新进展", "expected": 2},
    {"query": "TypeScript和JavaScript发展趋势对比", "expected": 2},
    {"query": "GitHub上最近热门的开源项目", "expected": 2},
    {"query": "2025年最佳的编程学习路线", "expected": 2},

    # ===== Chat (直接对话) — 25 条 =====
    {"query": "你好", "expected": 0},
    {"query": "谢谢你的帮助", "expected": 0},
    {"query": "什么是Python？", "expected": 0},
    {"query": "1+1等于几？", "expected": 0},
    {"query": "帮我写一段排序代码", "expected": 0},
    {"query": "今天心情不错", "expected": 0},
    {"query": "你能做什么？", "expected": 0},
    {"query": "再见", "expected": 0},
    {"query": "你是谁？", "expected": 0},
    {"query": "讲个笑话吧", "expected": 0},
    {"query": "什么是机器学习？", "expected": 0},
    {"query": "Python中list和tuple的区别", "expected": 0},
    {"query": "你好吗？", "expected": 0},
    {"query": "谢谢", "expected": 0},
    {"query": "怎么学编程？", "expected": 0},
    {"query": "HTTP和HTTPS的区别", "expected": 0},
    {"query": "什么是API？", "expected": 0},
    {"query": "MySQL和MongoDB的区别", "expected": 0},
    {"query": "解释一下递归", "expected": 0},
    {"query": "推荐几本编程书籍", "expected": 0},
    {"query": "什么是Docker？", "expected": 0},
    {"query": "怎么提高编程能力？", "expected": 0},
    {"query": "git常用命令有哪些", "expected": 0},
    {"query": "如何调试Python代码", "expected": 0},
    {"query": "写代码时如何保持专注", "expected": 0},

    # ===== 边界 Case — 10 条 =====
    {"query": "Python怎么样？", "expected": 1},            # 偏向课程咨询语境
    {"query": "课程里学的Python和网上自学有什么区别？", "expected": 1},  # 主意图是课程
    {"query": "学完Python能找到工作吗？最近市场怎么样？", "expected": 2},  # 后半句需实时数据
    {"query": "帮我写一段Python代码", "expected": 0},       # 编程辅助，无需检索
    {"query": "最近有什么新课吗？", "expected": 1},         # 课程相关，查内部资料
    {"query": "能推荐一个AI框架吗？", "expected": 2},       # 需要外部对比信息
    {"query": "这门课学完工资能涨多少？", "expected": 1},   # 关于课程就业效果
    {"query": "你觉得报班学习和自学哪个好？", "expected": 1},  # 课程咨询场景
    {"query": "好的，那先这样吧，88", "expected": 0},       # 结束语
    {"query": "学Python还是JavaScript对找工作更有帮助？", "expected": 2},  # 就业市场需真实数据
]


def evaluate(llm=None, use_llm: bool = True):
    """
    运行评估。

    Args:
        llm: LLM 客户端（None 则自动创建）
        use_llm: 是否使用 LLM 分类（False 则只用关键词 fallback）
    """
    if llm is None and use_llm:
        settings = load_settings()
        llm = create_llm(settings)
        model = settings.llm_model
    else:
        model = "unknown"

    correct = 0
    total = 0
    errors = []
    confusion = {"RAG": {"RAG": 0, "WEB": 0, "CHAT": 0},
                 "WEB": {"RAG": 0, "WEB": 0, "CHAT": 0},
                 "CHAT": {"RAG": 0, "WEB": 0, "CHAT": 0}}

    label_map = {0: "CHAT", 1: "RAG", 2: "WEB"}
    for tc in TEST_CASES:
        total += 1
        if use_llm and llm:
            intent, source = detect_intent(llm, tc["query"], model, enabled=True)
        else:
            intent = _keyword_intent(tc["query"])
            source = "keyword"

        expected = tc["expected"]
        got = int(intent)
        exp_label = label_map[expected]
        got_label = label_map[got]

        if got == expected:
            correct += 1
        else:
            errors.append({
                "query": tc["query"],
                "expected": expected,
                "got": got,
                "exp_label": exp_label,
                "got_label": got_label,
                "source": source,
            })
            confusion[exp_label][got_label] += 1

    accuracy = correct / total if total > 0 else 0

    # Print results
    print(f"\n{'='*60}")
    print(f"Intent Recognition Evaluation")
    print(f"{'='*60}")
    print(f"Method: {'LLM function calling' if use_llm else 'Keyword fallback'}")
    print(f"Total: {total}, Correct: {correct}, Accuracy: {accuracy:.2%}")
    print(f"Target: 98.00% — {'PASS' if accuracy >= 0.98 else 'FAIL'}")

    # Confusion matrix
    print(f"\nConfusion Matrix (expected → got):")
    for exp_cat in ["RAG", "WEB", "CHAT"]:
        row = confusion[exp_cat]
        total_row = sum(row.values())
        detail = "  ".join(f"{k}: {v}" for k, v in row.items() if v > 0)
        print(f"  {exp_cat} ({total_row}): {detail}")

    # Errors
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors[:20]:
            print(f"  [{e['source']}] '{e['query'][:50]}' → got {e['got_label']}, expected {e['exp_label']}")

    return {"accuracy": accuracy, "errors": errors, "total": total, "correct": correct}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate intent recognition accuracy")
    parser.add_argument("--keyword-only", action="store_true", help="Only use keyword fallback (skip LLM)")
    args = parser.parse_args()

    use_llm = not args.keyword_only
    evaluate(use_llm=use_llm)
