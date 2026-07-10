"""
数据库模块 - SQLite 会话与消息持久化
参考 AI-CRM seachat/db.py 的设计模式
"""
import re
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path


def get_db_path(config) -> str:
    """获取数据库路径（相对于项目根目录）"""
    db_path = config.db_path
    if not Path(db_path).is_absolute():
        project_root = Path(__file__).resolve().parent.parent
        db_path = str(project_root / db_path)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return db_path


def connect(db_path: str) -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_schema(conn: sqlite3.Connection):
    """创建表结构（支持增量迁移）"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            profile_json TEXT DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '新对话',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            task_state_json TEXT DEFAULT NULL,
            summary TEXT DEFAULT NULL,
            FOREIGN KEY(username) REFERENCES users(username)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_username
            ON sessions(username);
        CREATE INDEX IF NOT EXISTS idx_sessions_updated_at
            ON sessions(updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_messages_session_id
            ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_messages_created_at
            ON messages(created_at);
    """)
    # ── 增量迁移：兼容旧数据库 ──
    # 1. sessions.task_state_json
    try:
        conn.execute("SELECT task_state_json FROM sessions LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE sessions ADD COLUMN task_state_json TEXT DEFAULT NULL")
        conn.commit()
        print("[DB Migration] Added task_state_json column to sessions")
    
    # 2. sessions.summary
    try:
        conn.execute("SELECT summary FROM sessions LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE sessions ADD COLUMN summary TEXT DEFAULT NULL")
        conn.commit()
        print("[DB Migration] Added summary column to sessions")
    
    # 3. users.profile_json
    try:
        conn.execute("SELECT profile_json FROM users LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE users ADD COLUMN profile_json TEXT DEFAULT NULL")
        conn.commit()
        print("[DB Migration] Added profile_json column to users")




def now_iso() -> str:
    """返回当前 UTC 时间 ISO 字符串"""
    return datetime.now(timezone.utc).isoformat()


def get_time_group(iso_str: str) -> str:
    """
    根据 ISO 时间字符串返回时间分组标签
    返回: 'today' | 'yesterday' | 'week' | 'earlier'
    """
    try:
        dt = datetime.fromisoformat(iso_str)
    except (ValueError, TypeError):
        return "earlier"

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 计算天数差
    dt_date = dt.date()
    now_date = now.date()
    diff_days = (now_date - dt_date).days

    if diff_days == 0:
        return "today"
    elif diff_days == 1:
        return "yesterday"
    elif diff_days < 7:
        return "week"
    else:
        return "earlier"


# ── 智能标题生成 ───────────────────────────────────


def _generate_title(content: str, max_len: int = 20) -> str:
    """
    根据用户首条消息生成会话标题。
    清理文件标记、模板前缀，保留核心语义。
    """
    if not content or not content.strip():
        return "新对话"

    # 去除文件内容块（保留文件名作为引用）
    cleaned = re.sub(
        r"\n--- 文件: (.+?) ---\n[\s\S]*?\n--- 文件结束 ---",
        r"[\1]",
        content,
    )
    # 去除 [已上传文件: ...] 标记
    cleaned = re.sub(r"\[已上传文件:.*?\]", "", cleaned)
    # 去除常见模板前缀
    cleaned = re.sub(r"请帮我分析以下上传的文件内容[:：]?\s*", "", cleaned)
    cleaned = re.sub(r"请帮我分析上传的文件[:：]?\s*", "", cleaned)
    cleaned = cleaned.strip()

    if not cleaned:
        return "新对话"

    first_line = cleaned.split("\n")[0].strip()
    if len(first_line) <= max_len:
        return first_line

    return first_line[:max_len] + "…"


# ── User CRUD ──────────────────────────────────────


def ensure_user(conn: sqlite3.Connection, username: str):
    """确保用户存在"""
    conn.execute(
        "INSERT OR IGNORE INTO users (username, created_at) VALUES (?, ?)",
        (username, now_iso()),
    )
    conn.commit()


# ── Session CRUD ───────────────────────────────────


def create_session(conn: sqlite3.Connection, username: str,
                   title: str = "新对话", first_message: str = "") -> dict:
    """创建新会话，如有首条消息则自动生成智能标题"""
    if first_message and first_message.strip():
        title = _generate_title(first_message)

    session_id = str(uuid.uuid4())
    ts = now_iso()
    conn.execute(
        "INSERT INTO sessions (id, username, title, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (session_id, username, title, ts, ts),
    )
    conn.commit()
    return {
        "id": session_id,
        "title": title,
        "created_at": ts,
        "updated_at": ts,
        "message_count": 0,
        "time_group": get_time_group(ts),
    }


def list_sessions(conn: sqlite3.Connection, username: str) -> list[dict]:
    """列出用户的所有会话（按更新时间倒序）"""
    rows = conn.execute(
        """
        SELECT s.id, s.title, s.created_at, s.updated_at,
               COUNT(m.id) AS message_count
        FROM sessions s
        LEFT JOIN messages m ON m.session_id = s.id
        WHERE s.username = ?
        GROUP BY s.id
        ORDER BY s.updated_at DESC
        """,
        (username,),
    ).fetchall()

    result = []
    for row in rows:
        result.append({
            "id": row["id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "message_count": row["message_count"],
            "time_group": get_time_group(row["updated_at"]),
        })
    return result


def rename_session(conn: sqlite3.Connection, session_id: str,
                   title: str) -> dict | None:
    """重命名会话"""
    conn.execute(
        "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
        (title, now_iso(), session_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def delete_session(conn: sqlite3.Connection, session_id: str):
    """删除会话及其所有消息（CASCADE）"""
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()


# ── Message CRUD ───────────────────────────────────


def add_message(conn: sqlite3.Connection, session_id: str, role: str,
                content: str):
    """添加一条消息，同时更新会话的 updated_at"""
    ts = now_iso()
    conn.execute(
        "INSERT INTO messages (session_id, role, content, created_at) "
        "VALUES (?, ?, ?, ?)",
        (session_id, role, content, ts),
    )
    conn.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (ts, session_id),
    )
    conn.commit()


def fetch_messages(conn: sqlite3.Connection, session_id: str) -> list[dict]:
    """获取会话的所有消息（按时间正序）"""
    rows = conn.execute(
        "SELECT role, content, created_at FROM messages "
        "WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,),
    ).fetchall()
    return [
        {"role": row["role"], "content": row["content"],
         "created_at": row["created_at"]}
        for row in rows
    ]


# ── Task State CRUD ────────────────────────────────


def get_task_state(conn: sqlite3.Connection, session_id: str) -> dict | None:
    """获取会话的任务状态 JSON"""
    row = conn.execute(
        "SELECT task_state_json FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    if row and row["task_state_json"]:
        import json
        try:
            return json.loads(row["task_state_json"])
        except json.JSONDecodeError:
            return None
    return None


def update_task_state(conn: sqlite3.Connection, session_id: str, state_dict: dict):
    """更新会话的任务状态"""
    import json
    conn.execute(
        "UPDATE sessions SET task_state_json = ? WHERE id = ?",
        (json.dumps(state_dict, ensure_ascii=False), session_id),
    )
    conn.commit()


def clear_task_state(conn: sqlite3.Connection, session_id: str):
    """清除会话的任务状态（用于重置）"""
    conn.execute(
        "UPDATE sessions SET task_state_json = NULL WHERE id = ?",
        (session_id,),
    )
    conn.commit()


# ── Session Summary CRUD ───────────────────────────


def get_session_summary(conn: sqlite3.Connection, session_id: str) -> str | None:
    """获取会话摘要"""
    row = conn.execute(
        "SELECT summary FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    return row["summary"] if row and row["summary"] else None


def update_session_summary(conn: sqlite3.Connection, session_id: str, summary: str):
    """更新会话摘要"""
    conn.execute(
        "UPDATE sessions SET summary = ? WHERE id = ?",
        (summary, session_id),
    )
    conn.commit()


# ── User Profile CRUD ──────────────────────────────


def get_user_profile(conn: sqlite3.Connection, username: str) -> dict | None:
    """获取用户画像 JSON"""
    row = conn.execute(
        "SELECT profile_json FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if row and row["profile_json"]:
        import json
        try:
            return json.loads(row["profile_json"])
        except json.JSONDecodeError:
            return None
    return None


def update_user_profile(conn: sqlite3.Connection, username: str, profile: dict):
    """更新用户画像（合并模式）"""
    import json
    existing = get_user_profile(conn, username) or {}
    # 合并新数据到已有数据
    for k, v in profile.items():
        if v is not None:
            existing[k] = v
    conn.execute(
        "UPDATE users SET profile_json = ? WHERE username = ?",
        (json.dumps(existing, ensure_ascii=False), username),
    )
    conn.commit()


def clear_user_profile(conn: sqlite3.Connection, username: str):
    """清除用户画像"""
    conn.execute(
        "UPDATE users SET profile_json = NULL WHERE username = ?",
        (username,),
    )
    conn.commit()
