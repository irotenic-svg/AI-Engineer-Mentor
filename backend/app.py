"""
Flask API 入口 - AI 课程咨询助手后端
支持 SSE 流式问答、会话管理、文件上传
"""
import json
import uuid
from pathlib import Path

from flask import Flask, request, jsonify, Response
from flask_cors import CORS

from config import load_settings
from db import connect, ensure_schema, ensure_user, create_session, \
    list_sessions, rename_session, delete_session, add_message, fetch_messages

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


# ── 辅助函数 ────────────────────────────────────────


def _get_username():
    """从请求头获取当前用户名"""
    return request.headers.get("X-Username", "")


# ── API 路由 ────────────────────────────────────────


@app.route("/api/health", methods=["GET"])
def health_check():
    """健康检查"""
    return jsonify({"status": "ok"})


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
    SSE 流式聊天接口
    接收 {"session_id": "...", "question": "..."}
    事件流: token → done / error
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
        """SSE 事件生成器"""
        full_answer = ""

        try:
            llm = get_llm()
            from prompts import SYSTEM_PROMPT

            # 获取历史消息作为上下文
            history = fetch_messages(conn, session_id)
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for msg in history[-20:]:  # 最近 20 条
                messages.append({"role": msg["role"], "content": msg["content"]})

            # 流式调用 LLM
            stream = llm.chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                stream=True,
                temperature=0.7,
                max_tokens=2048,
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_answer += token
                    yield f"data: {json.dumps({'type': 'token', 'data': token}, ensure_ascii=False)}\n\n"

            # 保存 AI 回答
            if full_answer:
                add_message(conn, session_id, "assistant", full_answer)

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
    allowed_exts = {"pdf", "docx", "txt", "pptx", "html", "ipynb"}
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
    )
