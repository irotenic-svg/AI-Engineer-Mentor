<template>
  <div class="app-shell" v-if="isLoggedIn">
    <TopBar :username="username" @logout="handleLogout" />
    <div class="main-layout">
      <Sidebar
        :sessions="sessions"
        :active-session-id="activeSessionId"
        @new-session="handleNewSession"
        @select-session="handleSelectSession"
        @rename-session="handleRenameSession"
        @delete-session="handleDeleteSession"
      />
      <div class="content-area">
        <router-view />
      </div>
    </div>
  </div>
  <router-view v-else />
</template>

<script setup>
import { ref, computed, provide, watch } from 'vue'
import { useRouter } from 'vue-router'
import TopBar from '@/components/TopBar.vue'
import Sidebar from '@/components/Sidebar.vue'
import { listSessions, renameSession, deleteSession } from '@/api/session'

const router = useRouter()

const username = ref(localStorage.getItem('course_assistant_user') || '')
const sessions = ref([])
const activeSessionId = ref('')

const isLoggedIn = computed(() => !!username.value)

// 注入给子组件
provide('username', username)
provide('activeSessionId', activeSessionId)
provide('refreshSessions', loadSessions)

async function loadSessions() {
  if (!username.value) return
  try {
    const data = await listSessions()
    sessions.value = data.sessions || []
  } catch {
    sessions.value = []
  }
}

async function handleNewSession() {
  // 优雅的"新对话"：仅清空前端状态，不立即创建后端空会话。
  // 真正发送第一条消息时，再由 ChatView 延迟创建持久化会话。
  activeSessionId.value = ''
  router.push('/chat')
}

function handleSelectSession(id) {
  activeSessionId.value = id
  router.push('/chat')
}

async function handleRenameSession({ id, title }) {
  try {
    await renameSession(id, title)
    const s = sessions.value.find((x) => x.id === id)
    if (s) s.title = title
  } catch {
    // 静默失败
  }
}

async function handleDeleteSession(id) {
  try {
    await deleteSession(id)
    sessions.value = sessions.value.filter((x) => x.id !== id)
    if (activeSessionId.value === id) {
      activeSessionId.value = sessions.value[0]?.id || ''
    }
  } catch {
    // 静默失败
  }
}

function handleLogout() {
  localStorage.removeItem('course_assistant_user')
  username.value = ''
  activeSessionId.value = ''
  sessions.value = []
  router.push('/login')
}

// 初始加载：如果已登录则立即加载会话
if (username.value) {
  loadSessions()
}

// 路由变化时同步登录状态（LoginView 登录后触发）
watch(() => router.currentRoute.value.name, () => {
  const stored = localStorage.getItem('course_assistant_user')
  if (stored && stored !== username.value) {
    username.value = stored
    loadSessions()
  }
})
</script>

<style>
/* ================================================================
   AI 课程咨询助手 — Education Blue Design System
   ================================================================ */

:root {
  /* ── Surfaces ───────────────────── */
  --bg-root: #0a0f14;
  --bg-primary: #0e141c;
  --bg-secondary: #151c26;
  --bg-elevated: #1a2330;
  --bg-hover: #1e2736;

  /* ── Text ───────────────────────── */
  --text-primary: #e4ded4;
  --text-secondary: #a8a298;
  --text-muted: #6e6860;
  --text-disabled: #4a4540;

  /* ── Accent — Education Blue ────── */
  --accent: #3b82c4;
  --accent-soft: #2563eb;
  --accent-glow: rgba(59, 130, 196, 0.12);
  --accent-glow-strong: rgba(59, 130, 196, 0.22);

  /* ── Semantic ───────────────────── */
  --success: #5a9e6f;
  --warning: #c48a40;
  --danger: #c45a4e;
  --info: #5a8aae;

  /* ── Borders ────────────────────── */
  --border-subtle: #1a2330;
  --border-default: #222d3a;
  --border-strong: #2a3646;

  /* ── Shadows ────────────────────── */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.4);
  --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.5);
  --shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.6);

  /* ── Radii ──────────────────────── */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-xl: 20px;

  /* ── Typography ─────────────────── */
  --font-body: "PingFang SC", "Microsoft YaHei", "Hiragino Sans GB",
    "Noto Sans SC", -apple-system, BlinkMacSystemFont, sans-serif;
  --font-display: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
  --font-mono: "JetBrains Mono", "Fira Code", "SF Mono", "Cascadia Code",
    "Consolas", "Monaco", monospace;

  /* ── Transitions ────────────────── */
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --duration-fast: 150ms;
  --duration-normal: 250ms;
  --duration-slow: 400ms;
}

/* ── Global Reset ─────────────────────────────────── */
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  height: 100%;
  font-size: 16px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color-scheme: dark;
}

body {
  height: 100%;
  font-family: var(--font-body);
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-primary);
  background: var(--bg-root);
  overflow: hidden;
}

#app {
  height: 100%;
}

/* ── Scrollbar ───────────────────────────────────── */
::-webkit-scrollbar {
  width: 4px;
  height: 4px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: var(--border-strong);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

/* ── Selection ───────────────────────────────────── */
::selection {
  background: var(--accent-glow-strong);
  color: var(--text-primary);
}

/* ── Focus ring ──────────────────────────────────── */
:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 2px;
}

/* ── Layout ──────────────────────────────────────── */
.app-shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.main-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-root);
}
</style>
