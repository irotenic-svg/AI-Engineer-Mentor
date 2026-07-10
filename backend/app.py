"""
Flask API 入口 - AI 课程咨询助手后端
支持 SSE 流式问答、会话管理、文件上传、多轮任务路由
"""
import json
import uuid
from pathlib import Path

from flask import Flask, request, jsonify, Response
from flask_cors import CORS

from config import load_settings
from db import connect, ensure_schema, ensure_user, create_session, \
    list_sessions, rename_session, delete_session, add_message, fetch_messages, \
    get_task_state, update_task_state, get_session_summary, update_session_summary, \
    get_user_profile, update_user_profile

# ── 初始化 ──────────────────────────────────────────

app = Flask(__name__)
CORS(app, origins=["http://localhost:5173", "http://127.0.0.1:5173"])

settings = load_settings()
db_path = __import__("db").get_db_path(settings)

# 初始化数据库
conn = connect(db_path)
ensure_schema(conn)
print(f"[Init] Database ready at: {db_path}")

# 延迟导入 LLM（避免启动时没有 API key 就报错）
_llm_client = None


def get_llm():
    """懒加载 LLM 客户端"""
    global _llm_client
    if _llm_client is None:
        from llm import create_llm
        _llm_client = create_llm(settings)
        print(f"[Init] LLM ready: model={settings.llm_model}")
    return _llm_client


# ── RAG 初始化（延迟加载） ──
_rag_embedder = None
_rag_vectorstore = None
_rag_ready = None  # None = 未初始化, True/False = 已检查


def _init_rag():
    """懒加载 RAG 流水线。返回 Retriever 或 None（知识库为空/禁用/失败）"""
    global _rag_embedder, _rag_vectorstore, _rag_ready
    if _rag_ready is not None:
        return _rag_vectorstore  # 已初始化，直接返回（None 表示不可用）

    if not settings.rag_enabled:
        print("[Init] RAG 已禁用 (RAG_ENABLED=false)")
        _rag_ready = False
        return None

    try:
        from assistant.embeddings import get_embedder
        from assistant.vectorstore import VectorStoreManager

        _rag_embedder = get_embedder(settings.embedding_model, settings.embedding_device)
        _rag_vectorstore = VectorStoreManager(
            settings.chroma_absolute_dir, _rag_embedder, "course_knowledge"
        )
        count = _rag_vectorstore.count()
        if count > 0:
            print(f"[Init] RAG ready. 知识库: {count} 个文档块")
            _rag_ready = True
            return _rag_vectorstore
        else:
            print("[Init] RAG 已启用但知识库为空。运行 scripts/build_kb.py 构建。")
            _rag_ready = False
            _rag_vectorstore = None
            return None
    except Exception as e:
        print(f"[Init] RAG 初始化失败（非致命）: {e}")
        _rag_ready = False
        return None


# ── Web Search 初始化（延迟加载） ──
_web_search_manager = None
_web_search_ready = None


# ── Task Router 初始化（延迟加载） ──
_task_router = None
_task_router_ready = False


def _init_task_router():
    """懒加载 TaskRouter"""
    global _task_router, _task_router_ready
    if _task_router_ready:
        return _task_router
    try:
        from assistant.task_router import TaskRouter
        llm = get_llm()
        _task_router = TaskRouter(
            llm=llm,
            model=settings.llm_model,
            use_llm=True,
        )
        _task_router_ready = True
        print("[Init] Task Router ready")
        return _task_router
    except Exception as e:
        print(f"[Init] Task Router 初始化失败（非致命）: {e}")
        _task_router_ready = True  # 标记已尝试，避免重复
        _task_router = None
        return None


def _init_web_search():
    """懒加载 WebSearchManager。返回实例或 None（禁用/未配置/失败）"""
    global _web_search_manager, _web_search_ready
    if _web_search_ready is not None:
        return _web_search_manager

    if not settings.web_search_enabled:
        print("[Init] Web Search 已禁用 (WEB_SEARCH_ENABLED=false)")
        _web_search_ready = False
        return None

    if not settings.tavily_api_key:
        print("[Init] Web Search TAVILY_API_KEY 未配置，已禁用")
        _web_search_ready = False
        return None

    try:
        from assistant.websearch import WebSearchManager
        _web_search_manager = WebSearchManager(
            api_key=settings.tavily_api_key,
            enabled=settings.web_search_enabled,
        )
        if _web_search_manager.enabled:
            print("[Init] Web Search ready (Tavily)")
            _web_search_ready = True
            return _web_search_manager
        _web_search_ready = False
        return None
    except Exception as e:
        print(f"[Init] Web Search 初始化失败（非致命）: {e}")
        _web_search_ready = False
        return None


# ── 辅助函数 ────────────────────────────────────────


def _get_username():
    """从请求头获取当前用户名"""
    return request.headers.get("X-Username", "")


# ── API 路由 ────────────────────────────────────────


@app.route("/api/health", methods=["GET"])
def health_check():
    """健康检查（含 RAG 状态，不触发模型加载）"""
    kb_count = 0
    rag_available = False
    if settings.rag_enabled and _rag_ready is True and _rag_vectorstore:
        try:
            kb_count = _rag_vectorstore.count()
            rag_available = True
        except Exception:
            pass
    # Web Search 状态
    web_search_available = False
    if settings.web_search_enabled and settings.tavily_api_key:
        web_search_available = True

    return jsonify({
        "status": "ok",
        "rag_available": rag_available,
        "knowledge_base_docs": kb_count,
        "web_search_available": web_search_available,
        "intent_enabled": settings.intent_enabled,
    })


# ── Auth ────────────────────────────────────────────


@app.route("/api/login", methods=["POST"])
def login():
    """简易登录"""
    data = request.get_json()
    if not data or "username" not in data:
        return jsonify({"error": "缺少 username 参数"}), 400

    username = data["username"].strip()
    if not username:
        return jsonify({"error": "用户名不能为空"}), 400

    ensure_user(conn, username)
    return jsonify({
        "username": username,
        "token": f"mock-token-{username}",
    })


@app.route("/api/logout", methods=["POST"])
def logout():
    """登出"""
    return jsonify({"status": "ok"})


# ── Sessions ────────────────────────────────────────


@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    """获取用户的所有会话"""
    username = _get_username()
    if not username:
        return jsonify({"error": "未登录"}), 401

    sessions = list_sessions(conn, username)
    return jsonify({"sessions": sessions})


@app.route("/api/sessions", methods=["POST"])
def post_session():
    """创建新会话"""
    username = _get_username()
    if not username:
        return jsonify({"error": "未登录"}), 401

    data = request.get_json() or {}
    title = data.get("title", "新对话")
    first_message = data.get("first_message", "")
    session = create_session(conn, username, title, first_message)
    return jsonify({"session": session})


@app.route("/api/sessions/<session_id>", methods=["PATCH"])
def patch_session(session_id):
    """重命名会话"""
    username = _get_username()
    if not username:
        return jsonify({"error": "未登录"}), 401

    data = request.get_json()
    if not data or "title" not in data:
        return jsonify({"error": "缺少 title 参数"}), 400

    session = rename_session(conn, session_id, data["title"])
    if session is None:
        return jsonify({"error": "会话不存在"}), 404
    return jsonify({"session": session})


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session_route(session_id):
    """删除会话"""
    username = _get_username()
    if not username:
        return jsonify({"error": "未登录"}), 401

    delete_session(conn, session_id)
    return jsonify({"status": "ok"})


@app.route("/api/sessions/<session_id>/messages", methods=["GET"])
def get_session_messages(session_id):
    """获取会话历史消息"""
    username = _get_username()
    if not username:
        return jsonify({"error": "未登录"}), 401

    messages = fetch_messages(conn, session_id)
    return jsonify({
        "session_id": session_id,
        "messages": messages,
    })


# ── Chat ────────────────────────────────────────────


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """
    SSE 流式聊天接口（多轮任务路由增强版）
    接收 {"session_id": "...", "question": "..."}
    事件流: plan → stage → intent → (web_search) → sources → thinking → token* → done / error
    """
    data = request.get_json()
    if not data or "question" not in data:
        return jsonify({"error": "缺少 question 参数"}), 400

    question = data["question"].strip()
    if not question:
        return jsonify({"error": "问题不能为空"}), 400

    session_id = data.get("session_id", str(uuid.uuid4())[:8])

    # 保存用户消息
    try:
        add_message(conn, session_id, "user", question)
    except Exception:
        pass  # session 可能还不存在

    def generate():
        """SSE 事件生成器 — 任务路由 → 意图识别 → 工具路由 → 上下文 → LLM 流式"""
        full_answer = ""
        intent_code = None
        intent_source = None
        task_state = None

        try:
            llm = get_llm()

            # ── Step 0: 加载历史与任务状态 ──
            history = fetch_messages(conn, session_id)
            session_summary = None
            user_profile = None
            try:
                from assistant.task_router import TaskState as TRState
                state_dict = get_task_state(conn, session_id)
                task_state = TRState.from_dict(state_dict) if state_dict else None
            except Exception as te:
                print(f"[TaskRouter] 加载状态失败: {te}")
                task_state = None
            
            # 加载会话摘要
            try:
                session_summary = get_session_summary(conn, session_id)
            except Exception as se:
                print(f"[ContextManager] 加载会话摘要失败: {se}")
            
            # 加载用户画像
            try:
                username = _get_username()
                if username:
                    user_profile = get_user_profile(conn, username)
            except Exception as ue:
                print(f"[ContextManager] 加载用户画像失败: {ue}")

            # ── Step 1: 意图识别（多轮上下文感知）──
            from assistant.intents import detect_intent, IntentCode

            # 获取上一轮意图，用于多轮追问判断
            prev_intent = task_state.original_intent if task_state and task_state.round_count > 0 else None

            if settings.intent_enabled:
                try:
                    intent_code, intent_source = detect_intent(
                        llm=llm,
                        query=question,
                        model=settings.llm_model,
                        enabled=settings.intent_enabled,
                        history=history,
                        previous_intent=prev_intent,
                    )
                except Exception as ie:
                    print(f"[Intent] 分类异常: {ie}")
                    intent_code = IntentCode.CHAT
                    intent_source = "error"
            else:
                intent_code = IntentCode.CHAT
                intent_source = "disabled"

            # ── Step 2: 多轮任务路由分析 ──
            analysis = None
            should_clarify = False
            clarifying_answer = ""
            task_hint = ""

            router = _init_task_router()
            if router:
                try:
                    analysis, task_state = router.analyze(
                        query=question,
                        current_state=task_state,
                        history=history,
                        intent_code=int(intent_code) if intent_code else 0,
                    )
                    should_clarify = analysis.should_clarify

                    # 发送 plan 事件（如果有计划）
                    if analysis.plan:
                        yield f"data: {json.dumps({'type': 'plan', 'data': {'steps': analysis.plan, 'reason': analysis.reason}}, ensure_ascii=False)}\n\n"

                    # 发送 stage 事件
                    yield f"data: {json.dumps({'type': 'stage', 'data': {'stage': task_state.stage.value, 'complexity': task_state.complexity.value, 'task_type': task_state.task_type.value}}, ensure_ascii=False)}\n\n"

                    # 如果需要澄清，生成追问回答
                    if should_clarify and analysis.suggested_questions:
                        # 构建自然的追问文本
                        questions_text = "\n".join(
                            f"{i+1}. {q}" for i, q in enumerate(analysis.suggested_questions)
                        )
                        clarifying_answer = (
                            f"为了更好地帮您解答，我想再了解一些情况：\n\n"
                            f"{questions_text}\n\n"
                            f"您可以挑选其中几点回复，我会根据您的情况给出更精准的建议。"
                        )
                        task_state.stage = task_state.stage  # 保持 clarifying

                    # 构建 task hint（用于注入系统提示词）
                    task_hint = router.build_system_hint(task_state)

                except Exception as te:
                    print(f"[TaskRouter] 分析失败: {te}")
                    # 失败时回退到原有流程
                    should_clarify = False

            # 保存更新后的任务状态
            if task_state:
                try:
                    update_task_state(conn, session_id, task_state.to_dict())
                except Exception as se:
                    print(f"[TaskRouter] 保存状态失败: {se}")

            # 发送 intent 事件（向后兼容）
            yield f"data: {json.dumps({'type': 'intent', 'data': {'code': int(intent_code), 'source': intent_source}}, ensure_ascii=False)}\n\n"

            # ── Step 3: 如果需要澄清，直接输出追问 ──
            if should_clarify and clarifying_answer:
                # 模拟流式输出追问
                for chunk in clarifying_answer:
                    full_answer += chunk
                    yield f"data: {json.dumps({'type': 'token', 'data': chunk}, ensure_ascii=False)}\n\n"

                # 保存 AI 追问
                if full_answer:
                    try:
                        add_message(conn, session_id, "assistant", full_answer)
                    except Exception:
                        pass

                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                return  # 提前结束，不走LLM主流程

            # ── Step 4: 工具路由（原有逻辑）──
            sources = []
            context_str = ""
            rag_scores = None

            if intent_code == IntentCode.RAG:
                # ── RAG 检索 ──
                vs = _init_rag()
                if vs is not None:
                    try:
                        from assistant.prompts import format_context, format_sources

                        results = vs.similarity_search_with_relevance_scores(
                            question, k=settings.retrieval_top_k
                        )
                        filtered = [
                            (doc, score)
                            for doc, score in results
                            if score >= settings.retrieval_score_threshold
                        ]
                        if filtered:
                            sources = format_sources(filtered)
                            context_str, rag_scores = format_context(filtered)
                    except Exception as rag_err:
                        print(f"[RAG] 检索失败: {rag_err}")

            elif intent_code == IntentCode.WEB_SEARCH:
                # ── Web Search ──
                ws = _init_web_search()
                if ws is not None and ws.enabled:
                    try:
                        from assistant.websearch import format_web_context

                        result = ws.search(
                            query=question,
                            max_results=settings.web_search_max_results,
                            search_depth="advanced",
                        )
                        if result["error"]:
                            yield f"data: {json.dumps({'type': 'web_search', 'data': {'status': 'error', 'message': result['error']}}, ensure_ascii=False)}\n\n"
                        else:
                            sources = ws.format_sources(result["results"])
                            context_str = format_web_context(result["results"])
                            yield f"data: {json.dumps({'type': 'web_search', 'data': {'status': 'ok', 'result_count': len(result['results'])}}, ensure_ascii=False)}\n\n"
                    except Exception as ws_err:
                        print(f"[WebSearch] 搜索失败: {ws_err}")
                        yield f"data: {json.dumps({'type': 'web_search', 'data': {'status': 'error', 'message': str(ws_err)}}, ensure_ascii=False)}\n\n"

            # 发送 sources 事件
            yield f"data: {json.dumps({'type': 'sources', 'data': sources}, ensure_ascii=False)}\n\n"

            # ── Step 5: 构建消息（意图感知 + 智能上下文 + 任务路由 hint）──
            from assistant.prompts import build_messages_with_context_v2

            messages = build_messages_with_context_v2(
                context_str=context_str,
                history=history,
                question=question,
                intent=int(intent_code) if intent_code else 0,
                rag_scores=rag_scores,
                session_summary=session_summary,
                user_profile=user_profile,
                task_hint=task_hint,
            )

            # 更新任务状态为 answering
            if task_state and task_state.stage.value in ("gathering", "reasoning"):
                try:
                    update_task_state(conn, session_id, task_state.to_dict())
                except Exception:
                    pass

            # ── Step 6: 发送 thinking 事件 + LLM 流式 ──
            yield f"data: {json.dumps({'type': 'thinking'}, ensure_ascii=False)}\n\n"

            stream = llm.chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                stream=True,
                temperature=0.7,
                max_tokens=4096,
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_answer += token
                    yield f"data: {json.dumps({'type': 'token', 'data': token}, ensure_ascii=False)}\n\n"

            # 保存 AI 回答
            if full_answer:
                try:
                    add_message(conn, session_id, "assistant", full_answer)
                except Exception:
                    pass
            
            # ── 智能上下文维护：摘要生成 & 用户画像更新 ──
            try:
                from assistant.context_manager import (
                    generate_summary, extract_profile, estimate_messages_tokens
                )
                
                # 重新获取完整历史（刚保存了最新消息）
                full_history = fetch_messages(conn, session_id)
                
                # 1. 当消息足够多时，生成/更新会话摘要
                if len(full_history) >= 8:
                    try:
                        existing_summary = get_session_summary(conn, session_id)
                        new_summary = generate_summary(full_history, existing_summary)
                        if new_summary and len(new_summary) > 10:
                            update_session_summary(conn, session_id, new_summary)
                            print(f"[ContextManager] 会话摘要已更新: {len(new_summary)} chars")
                    except Exception as sum_err:
                        print(f"[ContextManager] 摘要生成失败: {sum_err}")
                
                # 2. 提取/更新用户画像（从当前对话中）
                username = _get_username()
                if username and len(full_history) >= 4:
                    try:
                        new_profile = extract_profile(full_history)
                        if new_profile:
                            update_user_profile(conn, username, new_profile)
                            print(f"[ContextManager] 用户画像已更新: {list(new_profile.keys())}")
                    except Exception as prof_err:
                        print(f"[ContextManager] 画像更新失败: {prof_err}")
                
                # 3. 日志：压缩前后对比
                raw_tokens = estimate_messages_tokens(full_history)
                if raw_tokens > 3500:
                    print(f"[ContextManager] 历史消息 token 估算: {raw_tokens}，已触发压缩")
            except Exception as cm_err:
                print(f"[ContextManager] 维护失败: {cm_err}")

            # 标记任务完成
            if task_state:
                from assistant.task_router import TaskStage
                task_state.stage = TaskStage.DONE
                try:
                    update_task_state(conn, session_id, task_state.to_dict())
                except Exception:
                    pass

            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_msg = str(e)
            yield f"data: {json.dumps({'type': 'error', 'data': error_msg}, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Accel-Buffering": "no",
            "Pragma": "no-cache",
        },
    )


# ── File Upload ─────────────────────────────────────

# 内存缓存：存储最近上传文件的提取文本（file_id → {filename, content}）
_file_cache: dict[str, dict] = {}


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """文件上传接口 — 保存文件并提取文本内容"""
    if "file" not in request.files:
        return jsonify({"error": "未选择文件"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "文件名为空"}), 400

    # 校验文件大小（32MB）
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 32 * 1024 * 1024:
        return jsonify({"error": "文件大小不能超过 32M"}), 400

    # 校验文件格式
    allowed_exts = {"pdf", "docx", "txt", "pptx", "html", "ipynb", "xlsx", "md"}
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in allowed_exts:
        return jsonify({
            "error": f"不支持的文件格式 '.{ext}'，允许的格式: {', '.join(sorted(allowed_exts))}"
        }), 400

    # 保存文件到临时目录
    import tempfile
    import os as _os

    upload_dir = Path(db_path).parent / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    save_path = upload_dir / safe_name
    file.save(str(save_path))

    # 提取文本内容
    from file_utils import extract_text

    try:
        extracted = extract_text(str(save_path), file.filename)
    except Exception as exc:
        extracted = f"[文件提取失败: {str(exc)}]"

    # 缓存提取结果
    file_id = uuid.uuid4().hex
    _file_cache[file_id] = {
        "filename": file.filename,
        "content": extracted,
    }

    # 清理旧缓存（保留最近 20 个）
    if len(_file_cache) > 20:
        oldest = list(_file_cache.keys())[0]
        del _file_cache[oldest]

    return jsonify({
        "file_id": file_id,
        "filename": file.filename,
        "size": size,
        "content_text": extracted,
        "status": "extracted",
    })


# ── 错误处理 ────────────────────────────────────────


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "接口不存在"}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "服务器内部错误"}), 500


# ── 启动入口 ────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(f"  AI 课程咨询助手 - Backend API")
    print(f"  http://{settings.flask_host}:{settings.flask_port}")
    print(f"{'='*50}\n")
    app.run(
        host=settings.flask_host,
        port=settings.flask_port,
        debug=settings.flask_env == "development",
        use_reloader=False,  # watchdog 误报 transformers 库文件变更导致无限重载
    )
