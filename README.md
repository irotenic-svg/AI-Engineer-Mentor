# AI 课程咨询助手

基于 Vue 3 + Element Plus + Python Flask 的智能课程咨询聊天应用，支持流式对话、多会话管理、文件上传、RAG 知识库检索、网络搜索、多轮任务路由，以及智能追问推荐。

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
| 网络搜索 | Tavily Search API |
| 意图识别 | LLM Function Calling (DeepSeek) + 关键词 Fallback |

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
│       │   └── ChatInput.vue        # 输入区（文件上传 + 发送）
│       └── styles/
│           └── chat.css             # Element Plus 暗色主题覆盖
│
├── backend/                         # Python Flask 后端
│   ├── app.py                       # API 入口 + RAG/WebSearch/TaskRouter/Suggestions 集成
│   ├── config.py                    # 配置管理（.env 加载）
│   ├── db.py                        # SQLite 数据库 + 会话/消息/任务状态/用户画像 CRUD
│   ├── file_utils.py                # 文件解析（8 种格式）
│   ├── llm.py                       # DeepSeek LLM 客户端（OpenAI 兼容）
│   ├── requirements.txt
│   ├── assistant/                   # 智能助手模块
│   │   ├── embeddings.py            # BGE-M3 嵌入模型
│   │   ├── vectorstore.py           # ChromaDB 向量存储管理器
│   │   ├── prompts.py               # 系统提示词（意图感知 + 智能上下文压缩）
│   │   ├── intents.py               # 意图识别（LLM function calling + 关键词 fallback，准确率提高）
│   │   ├── websearch.py             # Tavily 网络搜索 + citation 清洗
│   │   ├── context_manager.py       # 上下文压缩 + 会话摘要 + 用户画像提取
│   │   ├── task_router.py           # 多轮任务路由（复杂度评估 + 槽位填充 + 状态机）
│   │   └── suggestions.py           # 后续问题推荐引擎（6 类模板 + 个性化排序）
│   ├── scripts/
│   │   ├── build_kb.py              # 知识库构建 CLI
│   │   ├── verify_phase2.py         # RAG 管道验证
│   │   ├── verify_phase3.py         # 意图 + Web Search 集成验证
│   │   └── eval_intents.py          # 意图分类准确率评估（102 条测试集）
│   └── data/
│       ├── knowledge/               # 知识库源文档（6 份课程文档）
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
# 已内置 6 份课程文档可直接使用

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
- **前端来源展示**：回答附带引用来源面板（文件名 + 相关度评分）

### 意图识别

- **三级分类**：RAG 课程检索 / 网络搜索 / 直接对话，LLM function calling 主路径 + 关键词 fallback 兜底
- **多轮上下文感知**：意图分类时传入对话历史和上一轮意图，防止省略追问（如"Java的呢？"）被误判
- **测试准确率**：100%（102 条标注测试集，`python scripts/eval_intents.py`）
- **前端可视化**：消息气泡显示当前使用的工具标签（📚 课程资料 / 🌐 网络搜索）

### 网络搜索

- **实时搜索**：基于 Tavily Search API，`advanced` 深度搜索
- **结果清洗**：自动清除搜索结果中的 AI 搜索引擎 citation 标记（`【5†L9-L18】` 等）
- **结果过滤**：相关度 >= 0.5 阈值过滤，最多返回 5 条
- **上下文注入**：搜索结果格式化后注入 System Prompt，AI 回答标注来源 URL
- **优雅降级**：API key 未配置或超时时，自动回退为直接对话

### 多轮对话上下文管理

- **智能压缩**：基于 token 估算的动态上下文窗口，保留最近完整对话 + 远期摘要替代
- **会话摘要**：规则提取课程信息、技术栈等关键信息，8+ 条消息后自动生成
- **用户画像**：自动提取用户背景（零基础/转行/有经验）、学习目标、偏好技术方向等，跨会话持久化
- **上下文注入**：画像 + 摘要 + 任务路由信息自动注入 System Prompt

### 多轮任务路由

- **复杂度评估**：简单（直接回答）/ 中等（需少量澄清）/ 复杂（多轮信息收集），规则 + LLM 混合判定
- **任务类型识别**：直接回答 / 课程咨询 / 技术问题 / 对比分析 / 职业规划 / 学习规划
- **槽位填充**：自动检测缺失信息维度，必要时生成澄清追问
- **状态机管理**：analyzing → clarifying → gathering → reasoning → answering → done，持久化到 SQLite

### 后续问题推荐

- **智能追问**：每次回答后自动生成 3 条相关追问，前端以胶囊按钮展示
- **场景适配**：6 套模板库（课程咨询/学习规划/职业规划/技术问题/对比分析/通用）
- **个性化排序**：根据用户画像（零基础→优先基础问题、转行→优先就业问题）调整推荐顺序
- **去重过滤**：自动排除用户已问过的问题

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
| `GET` | `/api/health` | 健康检查（含 RAG/Web Search/Intent 状态） |
| `GET` | `/api/sessions` | 获取会话列表（含 `time_group`） |
| `POST` | `/api/sessions` | 创建新会话 `{title}` |
| `PATCH` | `/api/sessions/<id>` | 重命名会话 `{title}` |
| `DELETE` | `/api/sessions/<id>` | 删除会话及消息 |
| `GET` | `/api/sessions/<id>/messages` | 获取会话历史 |
| `POST` | `/api/chat/stream` | SSE 流式聊天 `{session_id, question}` |
| `POST` | `/api/upload` | 文件上传（multipart） |

### SSE 事件格式

完整事件序列：

```
data: {"type":"intent","data":{"code":1,"source":"llm"}}
data: {"type":"web_search","data":{"status":"ok","result_count":5}}    # 仅 Web Search 意图
data: {"type":"sources","data":[{"content":"...","source":"python_data.md","score":0.731}]}
data: {"type":"thinking"}
data: {"type":"token","data":"你好"}
data: {"type":"token","data":"！"}
data: {"type":"suggestions","data":["追问1","追问2","追问3"]}
data: {"type":"done"}
```

| 事件 | 说明 |
|------|------|
| `intent` | 意图分类结果：`code`=0/1/2 (CHAT/RAG/WEB_SEARCH)，`source`=llm/keyword |
| `web_search` | 网络搜索状态（仅 Web Search 意图时发送） |
| `sources` | 检索/搜索来源列表，空数组 `[]` 表示无工具或未匹配 |
| `thinking` | LLM 开始生成，前端显示"思考中…" |
| `token` | 流式输出 token |
| `suggestions` | 后续问题推荐列表（3 条），前端渲染为可点击追问胶囊 |
| `done` | 生成完成 |

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

# Tavily Web Search
TAVILY_API_KEY=tvly-xxx               # Tavily API 密钥 (https://tavily.com)
WEB_SEARCH_ENABLED=true               # 是否启用网络搜索
WEB_SEARCH_MAX_RESULTS=5              # 搜索结果数量

# Intent Recognition
INTENT_ENABLED=true                   # 是否启用意图识别
```

## 构建部署

```bash
cd frontend
npm run build        # 输出到 dist/
npm run preview      # 预览构建结果
```

生产环境下将 `dist/` 部署到静态文件服务器，后端使用 `waitress` 或 `gunicorn` 运行。
