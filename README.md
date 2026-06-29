# AI 课程咨询助手

基于 Vue 3 + Element Plus + Python Flask 的智能课程咨询聊天应用，支持流式对话、多会话管理和文件上传。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端框架 | Vue 3 (Composition API) |
| UI 组件库 | Element Plus |
| 构建工具 | Vite 8 |
| 后端框架 | Python Flask |
| LLM | DeepSeek API (OpenAI 兼容) |
| 数据持久化 | SQLite |

## 项目结构

```
AI-Engineer-Mentor/
├── frontend/                        # Vue 3 前端
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js               # Vite 配置 (/api → :5000)
│   └── src/
│       ├── App.vue                  # 根组件：三区域布局 + CSS 主题
│       ├── main.js                  # 入口：注册 Element Plus + Router
│       ├── router/index.js          # /login + /chat 路由 + 导航守卫
│       ├── api/
│       │   ├── auth.js              # 登录/登出
│       │   ├── session.js           # 会话 CRUD
│       │   └── chat.js              # SSE 流式聊天
│       ├── views/
│       │   ├── LoginView.vue        # 登录页
│       │   └── ChatView.vue         # 主聊天页
│       ├── components/
│       │   ├── TopBar.vue           # 顶栏（用户名 + 登出）
│       │   ├── Sidebar.vue          # 侧栏（时间分组会话列表）
│       │   ├── WelcomeState.vue     # 空状态欢迎页
│       │   ├── ChatInput.vue        # 输入区（文件上传 + 发送）
│       │   └── ChatMessage.vue      # 消息气泡
│       └── styles/
│           └── chat.css             # Element Plus 暗色主题覆盖
│
├── backend/                         # Python Flask 后端
│   ├── app.py                       # API 入口
│   ├── config.py                    # 配置管理（.env 加载）
│   ├── db.py                        # SQLite 数据库 + CRUD
│   ├── llm.py                       # DeepSeek LLM 客户端
│   ├── prompts.py                   # 系统提示词
│   └── requirements.txt
│
├── .env                             # 环境变量（API Key 等）
├── .env.example                     # 环境变量模板
└── .gitignore
```

## 快速开始

### 1. 环境准备

- Node.js >= 18
- Python >= 3.10

### 2. 后端启动

```bash
cd backend
pip install -r requirements.txt
python app.py
```

后端默认运行在 `http://localhost:5000`。

### 3. 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`，开发环境下 `/api` 请求自动代理到后端。

### 4. 访问应用

浏览器打开 `http://localhost:5173`，输入任意用户名即可登录使用。

## 功能特性

### 界面布局

- **三区域布局**：顶栏 + 侧栏 + 主聊天区
- **暗色主题**：教育蓝（`#3b82c4`）强调色，深色背景护眼
- **响应式适配**：桌面端 / 移动端自适应

### 会话管理

- 侧栏按时间分组显示历史会话（今天 / 昨天 / 前7天 / 更早）
- 支持新建、切换、重命名、删除会话
- 每个会话独立存储消息历史

### 聊天功能

- SSE 流式输出，实时显示 AI 回复
- Markdown 渲染（代码块、列表、粗斜体、引用等）
- 空状态展示欢迎语 + 建议问题快捷发送
- 打字光标动画 + 思考状态提示

### 文件上传

- 支持格式：`pdf`, `docx`, `txt`, `pptx`, `html`, `ipynb`
- 文件大小限制：32MB
- 前端格式校验 + 后端接收端点

### 登录认证

- 简易用户名登录，无需密码
- 路由守卫，未登录自动跳转登录页
- 登出清除状态，返回登录页

## 后端 API

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/login` | 登录 `{username}` → `{username, token}` |
| `POST` | `/api/logout` | 登出 |
| `GET` | `/api/health` | 健康检查 |
| `GET` | `/api/sessions` | 获取会话列表（含 `time_group`） |
| `POST` | `/api/sessions` | 创建新会话 `{title}` |
| `PATCH` | `/api/sessions/<id>` | 重命名会话 `{title}` |
| `DELETE` | `/api/sessions/<id>` | 删除会话及消息 |
| `GET` | `/api/sessions/<id>/messages` | 获取会话历史 |
| `POST` | `/api/chat/stream` | SSE 流式聊天 `{session_id, question}` |
| `POST` | `/api/upload` | 文件上传（multipart） |

### SSE 事件格式

```
data: {"type":"token","data":"你好"}
data: {"type":"token","data":"！"}
data: {"type":"done"}
```

## 配置说明

编辑 `.env` 文件：

```env
# DeepSeek API
DEEPSEEK_API_KEY=sk-xxx          # API 密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash # 或 deepseek-chat

# Flask
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# Database
DB_PATH=./backend/data/mentor.db
```

## 构建部署

```bash
cd frontend
npm run build        # 输出到 dist/
npm run preview      # 预览构建结果
```

生产环境下将 `dist/` 部署到静态文件服务器，后端使用 `waitress` 或 `gunicorn` 运行。
