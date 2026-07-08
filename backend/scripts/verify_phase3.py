"""
Phase 3 综合验证脚本
验证：意图识别 + 网络搜索 + 各模块协调 + 端到端 SSE 流程
"""
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_DIR = _PROJECT_ROOT / "backend"
sys.path.insert(0, str(_BACKEND_DIR))

import urllib.request
import urllib.error

BASE = "http://127.0.0.1:5000"


def safe_print(s):
    """安全打印，处理 GBK 编码问题"""
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("gbk", errors="replace").decode("gbk", errors="replace"))


USERNAME = "phase3_test"


def _headers():
    return {
        "Content-Type": "application/json",
        "X-Username": USERNAME,
    }


def http_post(path, data):
    """发送 POST 请求"""
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode("utf-8"),
        headers=_headers(),
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as e:
        return 0, str(e)


def http_get(path):
    """发送 GET 请求"""
    req = urllib.request.Request(f"{BASE}{path}", headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8")
    except Exception as e:
        return 0, str(e)


def sse_stream(path, data):
    """发送 SSE 流式请求，收集所有事件"""
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode("utf-8"),
        headers=_headers(),
    )
    events = []
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            buffer = ""
            for chunk in iter(lambda: resp.read(1), b""):
                try:
                    buffer += chunk.decode("utf-8")
                except UnicodeDecodeError:
                    continue
                while "\n\n" in buffer:
                    line, buffer = buffer.split("\n\n", 1)
                    line = line.strip()
                    if line.startswith("data: "):
                        try:
                            event = json.loads(line[6:])
                            events.append(event)
                        except json.JSONDecodeError:
                            pass
    except Exception as e:
        events.append({"type": "error", "data": str(e)})
    return events


def check(name, condition, detail=""):
    """检查并输出结果"""
    if condition:
        safe_print(f"  [PASS] {name}")
        return True
    else:
        safe_print(f"  [FAIL] {name} -- {detail}")
        return False


def main():
    safe_print("=" * 60)
    safe_print("Phase 3 综合验证")
    safe_print("=" * 60)

    passed = 0
    total = 0

    # ── 1. Health Check ──
    safe_print("\n[1] 健康检查")
    status, body = http_get("/api/health")
    total += 1
    if check("API 可达", status == 200, f"status={status}"):
        passed += 1
        health = json.loads(body)
        total += 1
        if check("status=ok", health.get("status") == "ok"):
            passed += 1
        total += 1
        if check("intent_enabled=true", health.get("intent_enabled") is True):
            passed += 1
        total += 1
        if check("web_search_available=true",
                 health.get("web_search_available") is True,
                 f"got: {health.get('web_search_available')}"):
            passed += 1

    # ── 2. Login ──
    safe_print("\n[2] 登录")
    status, body = http_post("/api/login", {"username": "phase3_test"})
    total += 1
    if check("登录成功", status == 200, f"status={status}"):
        passed += 1

    # ── 3. Create session ──
    safe_print("\n[3] 创建会话")
    status, body = http_post("/api/sessions", {"title": "Phase 3 集成测试"})
    total += 1
    session_id = None
    if check("创建会话成功", status == 200, f"status={status}"):
        passed += 1
        session_id = json.loads(body)["session"]["id"]
        safe_print(f"       session_id: {session_id}")

    if not session_id:
        safe_print("\n[FAIL] 无法创建会话，终止测试")
        return

    # ── 4. Intent: RAG 路径 ──
    safe_print("\n[4] RAG 意图路径 —— 'Python数据分析课程学什么？'")
    events = sse_stream("/api/chat/stream",
                        {"session_id": session_id, "question": "Python数据分析课程学什么？"})

    event_types = [e["type"] for e in events]
    safe_print(f"       事件序列: {event_types}")

    # intent 事件
    intent_events = [e for e in events if e["type"] == "intent"]
    total += 1
    if check("有 intent 事件", len(intent_events) > 0):
        passed += 1
        code = intent_events[0]["data"]["code"]
        total += 1
        if check("intent=RAG (code=1)", code == 1, f"got code={code}"):
            passed += 1

    # sources 事件
    sources_events = [e for e in events if e["type"] == "sources"]
    total += 1
    if check("有 sources 事件", len(sources_events) > 0):
        passed += 1

    # done 事件
    total += 1
    if check("有 done 事件", "done" in event_types):
        passed += 1

    # error 检查
    total += 1
    if check("无 error 事件", "error" not in event_types,
             f"errors: {[e for e in events if e['type'] == 'error']}"):
        passed += 1

    # ── 5. Intent: Web Search 路径 ──
    safe_print("\n[5] Web Search 意图路径 —— '2025年AI行业最新趋势是什么？'")
    events = sse_stream("/api/chat/stream",
                        {"session_id": session_id, "question": "2025年AI行业最新趋势是什么？"})

    event_types = [e["type"] for e in events]
    safe_print(f"       事件序列: {event_types}")

    # intent 事件
    intent_events = [e for e in events if e["type"] == "intent"]
    total += 1
    if check("有 intent 事件", len(intent_events) > 0):
        passed += 1
        code = intent_events[0]["data"]["code"]
        total += 1
        if check("intent=WEB_SEARCH (code=2)", code == 2, f"got code={code}"):
            passed += 1

    # web_search 事件
    ws_events = [e for e in events if e["type"] == "web_search"]
    total += 1
    if check("有 web_search 事件", len(ws_events) > 0,
             f"got {len(ws_events)} events"):
        passed += 1
        if ws_events:
            ws_data = ws_events[0]["data"]
            total += 1
            if check("web_search status=ok", ws_data.get("status") == "ok",
                     f"got: {ws_data}"):
                passed += 1
            total += 1
            if check("有搜索结果", ws_data.get("result_count", 0) > 0,
                     f"result_count={ws_data.get('result_count')}"):
                passed += 1

    # sources 事件
    sources_events = [e for e in events if e["type"] == "sources"]
    total += 1
    if check("有 sources 事件", len(sources_events) > 0):
        passed += 1
        web_sources = sources_events[0].get("data", [])
        if web_sources:
            total += 1
            has_url = any("url" in s for s in web_sources)
            if check("Web sources 包含 url 字段", has_url):
                passed += 1

    # done 事件
    total += 1
    if check("有 done 事件", "done" in event_types):
        passed += 1

    # ── 6. Intent: Chat 路径 ──
    safe_print("\n[6] Chat 意图路径 —— '你好，今天天气不错'")
    events = sse_stream("/api/chat/stream",
                        {"session_id": session_id, "question": "你好，今天天气不错"})

    event_types = [e["type"] for e in events]
    safe_print(f"       事件序列: {event_types}")

    # intent 事件
    intent_events = [e for e in events if e["type"] == "intent"]
    total += 1
    if check("有 intent 事件", len(intent_events) > 0):
        passed += 1
        code = intent_events[0]["data"]["code"]
        total += 1
        if check("intent=CHAT (code=0)", code == 0, f"got code={code}"):
            passed += 1

    # 无 web_search 事件
    total += 1
    if check("无 web_search 事件（Chat 不需要）", "web_search" not in event_types):
        passed += 1

    # sources 为空的
    sources_events = [e for e in events if e["type"] == "sources"]
    total += 1
    if check("sources 为空数组", len(sources_events) > 0 and sources_events[0].get("data") == []):
        passed += 1

    # done 事件
    total += 1
    if check("有 done 事件", "done" in event_types):
        passed += 1

    # ── 7. SSE 事件顺序检查 ──
    safe_print("\n[7] SSE 事件顺序验证")
    # 期望：intent → (web_search?) → sources → thinking → token* → done
    expected_order = ["intent"]
    # 检查所有三种路径的事件顺序
    all_paths_ok = True
    for label, question in [
        ("RAG", "Python课程费用是多少？"),
        ("Web Search", "最近AI行业有什么新闻？"),
        ("Chat", "谢谢"),
    ]:
        events = sse_stream("/api/chat/stream",
                            {"session_id": session_id, "question": question})
        types = [e["type"] for e in events]
        # 简单验证：intent 在 sources 之前，sources 在 done 之前
        idx_intent = types.index("intent") if "intent" in types else -1
        idx_sources = types.index("sources") if "sources" in types else -1
        idx_done = types.index("done") if "done" in types else -1
        order_ok = (-1 < idx_intent <= idx_sources <= idx_done) or \
                   (idx_intent >= 0 and idx_done >= 0 and idx_intent < idx_done)
        if not order_ok:
            safe_print(f"  [FAIL] {label} 事件顺序异常: {types}")
            all_paths_ok = False
        else:
            safe_print(f"  [PASS] {label} 顺序正确: {types}")

    total += 1
    if check("三种路径事件顺序全部正确", all_paths_ok):
        passed += 1

    # ── 8. Web Search 模块直接测试 ──
    safe_print("\n[8] Web Search 模块直接测试")
    try:
        from config import load_settings
        settings = load_settings()
        from assistant.websearch import WebSearchManager, format_web_context

        ws = WebSearchManager(api_key=settings.tavily_api_key, enabled=True)
        total += 1
        if check("WebSearchManager 初始化成功", ws.enabled):
            passed += 1

        result = ws.search("Python programming best practices 2025", max_results=3)
        total += 1
        if check("搜索无错误", result.get("error") is None, f"error={result.get('error')}"):
            passed += 1

        total += 1
        if check("有搜索结果", len(result.get("results", [])) > 0,
                 f"count={len(result.get('results', []))}"):
            passed += 1

        total += 1
        if check("响应时间 < 10s", result.get("response_time", 999) < 10,
                 f"response_time={result.get('response_time'):.2f}s"):
            passed += 1

        # Check result structure
        if result["results"]:
            r = result["results"][0]
            for field in ["content", "url", "title", "score"]:
                total += 1
                if check(f"结果包含 {field} 字段", field in r):
                    passed += 1

        # Test format_sources
        sources = ws.format_sources(result["results"])
        total += 1
        if check("format_sources 返回非空", len(sources) > 0):
            passed += 1

        # Test format_web_context
        ctx = format_web_context(result["results"])
        total += 1
        if check("format_web_context 返回非空字符串", len(ctx) > 0):
            passed += 1
        total += 1
        if check("context 包含 URL", "URL:" in ctx):
            passed += 1

        safe_print(f"       搜索结果示例: title='{result['results'][0].get('title', '')[:60]}'")
        safe_print(f"       score={result['results'][0].get('score')}, response_time={result.get('response_time'):.2f}s")
    except Exception as e:
        safe_print(f"  [FAIL] Web Search 模块测试异常: {e}")

    # ── Summary ──
    safe_print(f"\n{'='*60}")
    safe_print(f"结果: {passed}/{total} 通过")
    safe_print(f"{'='*60}")
    if passed == total:
        safe_print("状态: ALL PASS")
    else:
        safe_print(f"状态: {total - passed} FAILURES")


if __name__ == "__main__":
    main()
