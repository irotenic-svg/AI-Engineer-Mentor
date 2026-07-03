# AI 课程咨询助手

基于 Vue 3 + Element Plus + Python Flask 的智能课程咨询聊天应用，支持流式对话、多会话管理、文件上传，以及基于 RAG 的知识库检索增强。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端框架 | Vue 3 (Composition API) |
| UI 组件库 | Element Plus |
| 构建工具 | Vite 8 |
| 后端框架 | Python Flask |
| LLM | DeepSeek API (OpenAI 兼容) |
| 数据持久化 | SQLite |
| 嵌入模型 | BAAI/bge-m3 (1024 维, 中英双语) |
| 向量数据库 | ChromaDB (via langchain-chroma) |
| RAG 框架 | LangChain (langchain-core + langchain-text-splitters) |

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
│   ├── app.py                       # API 入口 + RAG 集成
│   ├── config.py                    # 配置管理（.env 加载 + RAG 配置）
│   ├── db.py                        # SQLite 数据库 + CRUD
│   ├── file_utils.py                # 文件解析（txt/docx/pdf/xlsx/md/html/pptx/ipynb）
│   ├── llm.py                       # DeepSeek LLM 客户端
│   ├── prompts.py                   # 系统提示词
│   ├── requirements.txt
│   ├── assistant/                   # RAG 流水线
│   │   ├── embeddings.py            # BGE-M3 嵌入模型（LangChain Embeddings）
│   │   ├── vectorstore.py           # ChromaDB 向量存储管理器
│   │   └── prompts.py               # RAG 提示词模板 + 上下文构建
│   ├── scripts/
│   │   ├── build_kb.py              # 知识库构建 CLI
│   │   └── verify_phase2.py         # Phase 2 验证脚本
│   └── data/
│       ├── knowledge/               # 知识库源文档（用户自行放置）
│       ├── chroma/                  # ChromaDB 持久化（gitignore）
│       └── uploads/                 # 上传文件临时存储（gitignore）
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

> **注意**：首次启动时 RAG 功能不会触发模型加载。BGE-M3 模型（约 2.2GB）会在第一次聊天请求时懒加载，首次加载约需 30-60 秒。

### 3. 构建知识库（可选，启用 RAG 必需）

```bash
cd backend

# 将课程文档放入 data/knowledge/ 目录（支持 txt/md/docx/pdf/xlsx/html/pptx/ipynb）
# 已有示例文件 data/knowledge/sample_course.md 可直接测试

python scripts/build_kb.py
```

首次运行会自动下载 BGE-M3 模型（约 2.2GB）。如果网络受限，可设置镜像：

```bash
set HF_ENDPOINT=https://hf-mirror.com
python scripts/build_kb.py
```

### 4. 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`，开发环境下 `/api` 请求自动代理到后端。

### 5. 访问应用

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

- 支持格式：`pdf`, `docx`, `txt`, `pptx`, `html`, `ipynb`, `xlsx`, `md`
- 文件大小限制：32MB
- 前端格式校验 + 后端解析提取文本内容

### RAG 知识库检索

- **嵌入模型**：BAAI/bge-m3（1024 维，中英双语），首次聊天请求懒加载
- **文档分块**：RecursiveCharacterTextSplitter（chunk_size=500, overlap=50）
- **相似度检索**：基于 ChromaDB + cosine similarity，默认阈值 0.45
- **上下文注入**：检索结果自动注入 System Prompt，AI 回答引用课程资料
- **优雅降级**：知识库为空时自动切换为普通对话模式，不影响正常聊天
- **前端来源展示**：回答附带引用来源面板（文件名 + 相关度评分）

### 知识库管理

- CLI 构建脚本：`python scripts/build_kb.py`
- 支持 8 种文档格式自动解析
- 构建进度显示 + 来源分布统计

### 登录认证

- 简易用户名登录，无需密码
- 路由守卫，未登录自动跳转登录页
- 登出清除状态，返回登录页

## 后端 API

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/login` | 登录 `{username}` → `{username, token}` |
| `POST` | `/api/logout` | 登出 |
| `GET` | `/api/health` | 健康检查（含 `rag_available`, `knowledge_base_docs`） |
| `GET` | `/api/sessions` | 获取会话列表（含 `time_group`） |
| `POST` | `/api/sessions` | 创建新会话 `{title}` |
| `PATCH` | `/api/sessions/<id>` | 重命名会话 `{title}` |
| `DELETE` | `/api/sessions/<id>` | 删除会话及消息 |
| `GET` | `/api/sessions/<id>/messages` | 获取会话历史 |
| `POST` | `/api/chat/stream` | SSE 流式聊天 `{session_id, question}` |
| `POST` | `/api/upload` | 文件上传（multipart） |

### SSE 事件格式

RAG 启用时，`sources` 事件在所有 `token` 事件之前发送：

```
data: {"type":"sources","data":[{"content":"课程内容预览...","source":"sample_course.md","score":0.731}]}
data: {"type":"token","data":"你好"}
data: {"type":"token","data":"！"}
data: {"type":"done"}
```

知识库为空或无匹配时，`sources` 事件返回空数组 `[]`。

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

# RAG
RAG_ENABLED=true                      # 是否启用知识库检索
CHROMA_DIR=./backend/data/chroma      # ChromaDB 持久化目录
KNOWLEDGE_DIR=./backend/data/knowledge # 知识库源文档目录
EMBEDDING_MODEL=BAAI/bge-m3           # 嵌入模型
EMBEDDING_DEVICE=auto                 # 推理设备（auto/cpu/cuda）
RETRIEVAL_TOP_K=5                     # 检索返回数量
RETRIEVAL_SCORE_THRESHOLD=0.45        # 相似度阈值
CHUNK_SIZE=500                        # 文档分块大小
CHUNK_OVERLAP=50                      # 分块重叠大小
```

## 构建部署

```bash
cd frontend
npm run build        # 输出到 dist/
npm run preview      # 预览构建结果
```

生产环境下将 `dist/` 部署到静态文件服务器，后端使用 `waitress` 或 `gunicorn` 运行。
