<template>
  <div class="chat-container">
    <!-- Messages -->
    <div class="chat-body" ref="chatBodyRef">
      <div class="message-list">
        <!-- Empty State -->
        <WelcomeState
          v-if="messages.length === 0"
          welcome-title="欢迎使用AI课程咨询助手"
          greeting="您好！很高兴为你服务！"
        />

        <!-- Messages -->
        <div
          v-for="(msg, index) in messages"
          :key="index"
          :class="['message-item', msg.role]"
        >
          <div v-if="msg.role === 'assistant'" class="message-avatar">📚</div>
          <div class="message-content">
            <div class="message-bubble" v-html="renderMarkdown(msg.content)"></div>
            <!-- Show attached files on user messages -->
            <div v-if="msg.files && msg.files.length > 0" class="msg-files">
              <div v-for="(f, fi) in msg.files" :key="fi" class="msg-file-tag">
                📎 {{ f.name }}
              </div>
            </div>
          </div>
          <div v-if="msg.role === 'user'" class="message-avatar">👤</div>
        </div>

        <!-- Streaming cursor -->
        <div v-if="loading && messages.length && messages[messages.length-1].role === 'assistant'" class="stream-cursor">
          <span class="cursor-blink">▍</span>
          {{ thinking ? '思考中…' : '生成中…' }}
        </div>
      </div>
    </div>

    <!-- Input -->
    <div class="chat-footer">
      <div class="footer-threshold"></div>
      <div class="chat-input-wrapper">
        <ChatInput
          v-model="inputText"
          :files="uploadedFiles"
          :placeholder="loading ? (thinking ? '正在思考…' : '正在生成…') : defaultPlaceholder"
          :disabled="loading || fileUploading"
          :loading="loading || fileUploading"
          @send="handleSend"
          @file-upload="handleFileUpload"
          @remove-file="handleRemoveFile"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, inject, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import WelcomeState from '@/components/WelcomeState.vue'
import ChatInput from '@/components/ChatInput.vue'
import { sendMessageStream, uploadFile } from '@/api/chat'
import { getSessionMessages, createSession } from '@/api/session'

const activeSessionId = inject('activeSessionId')
const refreshSessions = inject('refreshSessions')

const messages = ref([])
const inputText = ref('')
const uploadedFiles = ref([])
const loading = ref(false)
const thinking = ref(false)
const chatBodyRef = ref(null)

const defaultPlaceholder = "上传的文档不超过32M，文件格式限制为：'pdf', 'docx', 'txt', 'pptx', 'html', 'ipynb'"

const suggestions = [
  'Python数据分析课程适合零基础吗？',
  '人工智能工程师需要学哪些技能？',
  '前端开发和后端开发哪个更容易入门？',
  '全日制课程和周末班有什么区别？',
  '课程学完后有就业推荐吗？',
]

// ── Helpers ──────────────────────────────────────

function cleanDisplayContent(content) {
  // 移除嵌入的文件内容块，只保留文件名标记
  return content.replace(/\n--- 文件: (.+?) ---\n[\s\S]*?\n--- 文件结束 ---/g, '\n\n[已上传文件: $1]')
}

function scrollToBottom() {
  nextTick(() => {
    if (chatBodyRef.value) {
      chatBodyRef.value.scrollTo({
        top: chatBodyRef.value.scrollHeight,
        behavior: 'smooth',
      })
    }
  })
}

function renderMarkdown(text) {
  if (!text) return ''

  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) =>
    `<pre><code>${code.trim()}</code></pre>`
  )

  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')

  html = html.replace(/`(.+?)`/g, '<code>$1</code>')

  html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>')

  html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')

  html = html.replace(/^[-*] (.+)$/gm, '<li>$1</li>')
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')

  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>')

  html = html.replace(/^---$/gm, '<hr>')

  html = html.replace(/\n\n+/g, '</p><p>')
  html = html.replace(/\n/g, '<br>')

  html = html.replace(/<p>\s*<\/p>/g, '')
  html = html.replace(/<p>(<[ou]l>)/g, '$1')
  html = html.replace(/(<\/[ou]l>)<\/p>/g, '$1')

  return `<p>${html}</p>`
}

// ── Session helper ───────────────────────────────

async function ensureSession(firstMessage = '') {
  if (activeSessionId.value) return activeSessionId.value
  try {
    // 延迟创建：发送第一条消息时才真正持久化会话，并将用户首条消息传给后端用于智能标题
    const data = await createSession('新对话', firstMessage)
    if (data.session) {
      activeSessionId.value = data.session.id
      refreshSessions?.()
      return data.session.id
    }
  } catch (e) {
    // 静默失败
  }
  // 如果 API 失败，生成一个本地 ID
  const fallback = 'local_' + Date.now()
  activeSessionId.value = fallback
  return fallback
}

// ── Actions ──────────────────────────────────────

async function handleSend() {
  const question = inputText.value.trim()
  const hasFiles = uploadedFiles.value.length > 0
  if ((!question && !hasFiles) || loading.value) return

  // 尽早设置 loading，防止 ensureSession 触发的 watch 回调
  // 在异步完成后覆盖 messages
  loading.value = true
  thinking.value = false

  // 构建带文件内容的消息（先构建，以便传给 ensureSession 生成智能标题）
  let fullContent = question
  if (hasFiles) {
    const fileParts = uploadedFiles.value.map((f) => {
      if (f.contentText) {
        return `\n\n--- 文件: ${f.name} ---\n${f.contentText}\n--- 文件结束 ---`
      }
      return `\n\n[已上传文件: ${f.name}]`
    })
    const fileBlock = fileParts.join('\n')
    fullContent = question ? question + fileBlock : `请帮我分析以下上传的文件内容:\n${fileBlock}`
    // DEBUG: 确认文件内容是否已包含在发送的消息中
    console.log('[handleSend] fullContent length:', fullContent.length, 'hasContent:', uploadedFiles.value.map(f => !!f.contentText))
  }

  // 自动创建会话（仅在真正发送消息时才持久化），并将首条消息内容传给后端生成标题
  const sid = await ensureSession(fullContent)
  if (!sid) {
    loading.value = false
    return
  }

  // 暂存文件列表用于显示
  const attachedFiles = [...uploadedFiles.value]

  // User message（显示给用户看的不包含文件内容，用简短标记）
  let displayContent = question
  if (hasFiles) {
    const fileNames = uploadedFiles.value.map((f) => f.name).join('、')
    displayContent = question ? question + `\n\n[已上传文件: ${fileNames}]` : `请帮我分析上传的文件: ${fileNames}`
  }

  messages.value.push({
    role: 'user',
    content: displayContent,
    files: attachedFiles,
  })
  inputText.value = ''
  uploadedFiles.value = []

  // Placeholder AI message
  messages.value.push({ role: 'assistant', content: '', sources: [] })
  const aiIdx = messages.value.length - 1

  // 确保 DOM 渲染后再开始流式更新
  await nextTick()
  scrollToBottom()

  // 用局部变量累积内容，通过数组元素替换确保 Vue 响应式
  let streamContent = ''
  let rafPending = false

  function flushContent() {
    if (messages.value[aiIdx]) {
      // 直接替换数组元素，确保 Vue Proxy 能追踪变化
      messages.value[aiIdx] = {
        ...messages.value[aiIdx],
        content: streamContent,
      }
    }
  }

  function scheduleRender() {
    if (!rafPending) {
      rafPending = true
      requestAnimationFrame(() => {
        rafPending = false
        flushContent()
        scrollToBottom()
      })
    }
  }

  try {
    for await (const event of sendMessageStream(fullContent, sid)) {
      switch (event.type) {
        case 'sources':
          if (event.data && event.data.length > 0 && messages.value[aiIdx]) {
            messages.value[aiIdx] = {
              ...messages.value[aiIdx],
              sources: event.data,
            }
          }
          break

        case 'thinking':
          thinking.value = true
          scheduleRender()
          break

        case 'token':
          thinking.value = false
          streamContent += event.data
          scheduleRender()
          break

        case 'error':
          thinking.value = false
          if (!streamContent) {
            streamContent = `处理错误: ${event.data}`
            flushContent()
          }
          ElMessage.warning(event.data)
          break

        case 'done':
          thinking.value = false
          if (!streamContent) {
            streamContent = '抱歉，未能生成回答。'
            flushContent()
          }
          break
      }
    }
  } catch (err) {
    thinking.value = false
    if (!streamContent) {
      streamContent = `请求失败: ${err.message}。请检查后端服务是否正常运行。`
      flushContent()
    }
    ElMessage.error('无法连接到后端服务')
  } finally {
    // 确保最终内容已刷新
    flushContent()
    loading.value = false
    refreshSessions?.()
    scrollToBottom()
  }
}

// 首条 AI 回复后，用用户问题自动命名会话
// async function renameSessionIfNew(sid, title) { ... }
// —— 已由后端在创建会话时根据首条消息智能生成标题，前端不再需要此逻辑。

function handleSuggestion(q) {
  inputText.value = q
  handleSend()
}

const TEXT_EXTS = ['txt', 'html', 'ipynb', 'md', 'csv', 'json', 'xml', 'css', 'js', 'py']
const MAX_FILE_CHARS = 8000

const fileUploading = ref(false)

async function handleFileUpload(file) {
  fileUploading.value = true
  try {
    const ext = file.name.split('.').pop()?.toLowerCase() || ''

    let contentText = ''

    if (TEXT_EXTS.includes(ext)) {
      // 文本文件直接在前端读取，更快且避免代理问题
      contentText = await new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result)
        reader.onerror = () => reject(new Error('文件读取失败'))
        reader.readAsText(file)
      })
    } else {
      // 二进制文件（pdf, docx, pptx）上传到后端提取
      const result = await uploadFile(file)
      contentText = result.content_text || ''
    }

    // 截断过长内容
    if (contentText.length > MAX_FILE_CHARS) {
      contentText = contentText.slice(0, MAX_FILE_CHARS) + '\n\n[... 内容已截断，仅展示前 ' + MAX_FILE_CHARS + ' 字符 ...]'
    }

    uploadedFiles.value.push({
      name: file.name,
      size: file.size,
      contentText: contentText,
    })

    const lenInfo = contentText ? ` (${contentText.length}字符)` : ' ⚠️未提取到内容'
    ElMessage.success(`已添加文件: ${file.name}${lenInfo}`)
  } catch (err) {
    ElMessage.error(`文件处理失败: ${err.message}`)
  } finally {
    fileUploading.value = false
  }
}

function handleRemoveFile(index) {
  uploadedFiles.value.splice(index, 1)
}

// ── Load history on session change ────────────────

watch(activeSessionId, async (newId) => {
  if (!newId) {
    messages.value = []
    return
  }
  try {
    const data = await getSessionMessages(newId)
    // 防止竞态：如果会话已切换或正在流式生成中，不覆盖 messages
    if (activeSessionId.value !== newId || loading.value) return
    messages.value = (data.messages || []).map((m) => ({
      role: m.role === 'assistant' ? 'assistant' : 'user',
      content: m.role === 'user' ? cleanDisplayContent(m.content) : m.content,
    }))
    scrollToBottom()
  } catch {
    if (activeSessionId.value !== newId || loading.value) return
    messages.value = []
  }
}, { immediate: true })
</script>

<style scoped>
.chat-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-root);
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 32px 0 16px;
  scroll-behavior: smooth;
}

.message-list {
  max-width: 760px;
  margin: 0 auto;
  padding: 0 28px;
}

/* ── Message Items ─────────────────────────────────── */
.message-item {
  display: flex;
  margin-bottom: 32px;
  animation: messageIn 0.4s var(--ease-out);
}

@keyframes messageIn {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-item.user {
  justify-content: flex-end;
}

.message-item.assistant {
  justify-content: flex-start;
}

/* ── Avatars ───────────────────────────────────────── */
.message-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 16px;
}

.message-item.assistant .message-avatar {
  margin-right: 16px;
  background: linear-gradient(145deg, #1b2a2e, #162028);
  border: 1px solid rgba(59, 130, 196, 0.2);
}

.message-item.user .message-avatar {
  margin-left: 16px;
  order: 2;
  background: linear-gradient(145deg, #1e2430, #1a1f28);
  border: 1px solid var(--border-subtle);
}

/* ── Message Content ───────────────────────────────── */
.message-content {
  flex: 0 1 auto;
  min-width: 0;
  max-width: 82%;
}

.message-item.user .message-content {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

/* ── Attached files on user messages ───────────────── */
.msg-files {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.msg-file-tag {
  font-size: 11px;
  color: var(--accent);
  background: var(--accent-glow);
  border: 1px solid rgba(59, 130, 196, 0.2);
  border-radius: 4px;
  padding: 2px 8px;
}

/* ── Message Bubbles ───────────────────────────────── */
.message-bubble {
  padding: 14px 20px;
  border-radius: var(--radius-lg);
  line-height: 1.8;
  font-size: 14.5px;
  word-break: break-word;
  color: var(--text-primary);
  letter-spacing: 0.01em;
}

.message-item.user .message-bubble {
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-bottom-right-radius: var(--radius-sm);
}

.message-item.assistant .message-bubble {
  background: var(--bg-secondary);
  border: 1px solid var(--border-subtle);
  border-bottom-left-radius: var(--radius-sm);
}

/* ── Markdown Content ──────────────────────────────── */
.message-bubble p { margin: 0 0 10px 0; line-height: 1.8; }
.message-bubble p:last-child { margin-bottom: 0; }

.message-bubble strong { color: var(--text-primary); font-weight: 650; }
.message-bubble em { color: var(--text-secondary); }

.message-bubble h2, .message-bubble h3, .message-bubble h4 {
  font-family: var(--font-display);
  color: var(--text-primary);
  margin: 16px 0 8px 0;
  font-weight: 600;
}

.message-bubble h2 { font-size: 1.2em; }
.message-bubble h3 { font-size: 1.1em; }
.message-bubble h4 { font-size: 1em; }

.message-bubble code {
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: 4px;
  padding: 2px 7px;
  font-size: 13px;
  font-family: var(--font-mono);
  color: var(--accent);
}

.message-bubble pre {
  background: #0d1116;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: 16px 20px;
  overflow-x: auto;
  margin: 12px 0;
}

.message-bubble pre code {
  background: transparent;
  border: none;
  color: #c8c0b4;
  padding: 0;
  font-size: 13px;
}

.message-bubble ul, .message-bubble ol {
  margin: 10px 0;
  padding-left: 24px;
}

.message-bubble li { margin-bottom: 5px; }
.message-bubble li::marker { color: var(--text-muted); }

.message-bubble blockquote {
  border-left: 2px solid var(--accent);
  margin: 10px 0;
  padding: 6px 16px;
  color: var(--text-secondary);
  background: rgba(59, 130, 196, 0.04);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.message-bubble hr {
  border: none;
  border-top: 1px solid var(--border-subtle);
  margin: 14px 0;
}

/* ── Input Footer ──────────────────────────────────── */
.chat-footer {
  padding: 0;
  background: var(--bg-primary);
  flex-shrink: 0;
  position: relative;
}

.footer-threshold {
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    var(--accent) 20%,
    var(--accent) 80%,
    transparent 100%
  );
  opacity: 0.3;
  margin: 0 28px;
}

.chat-input-wrapper {
  max-width: 760px;
  margin: 0 auto;
  padding: 20px 28px 24px;
}

/* ── Streaming Cursor ──────────────────────────────── */
.stream-cursor {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0 4px 66px;
  font-size: 0.78rem;
  color: var(--text-muted);
  user-select: none;
}

.cursor-blink {
  display: inline-block;
  color: var(--accent);
  animation: cursorBlink 0.7s step-end infinite;
}

@keyframes cursorBlink {
  50% { opacity: 0; }
}

/* ── Responsive ────────────────────────────────────── */
@media (max-width: 640px) {
  .chat-input-wrapper { padding: 14px 14px 18px; }
  .footer-threshold { margin: 0 14px; }
  .message-list { padding: 0 14px; }
  .message-content { max-width: 90%; }
  .message-bubble { padding: 12px 16px; font-size: 14px; }
}
</style>
