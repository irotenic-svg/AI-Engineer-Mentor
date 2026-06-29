<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <el-button type="primary" @click="$emit('new-session')" :icon="Plus" size="small">
        新对话
      </el-button>
    </div>

    <div class="sidebar-title">对话历史</div>

    <div class="sidebar-list" v-if="groupedSessions.length > 0">
      <div
        v-for="group in groupedSessions"
        :key="group.label"
        class="session-group"
      >
        <div class="group-label">{{ group.label }}</div>
        <div
          v-for="session in group.sessions"
          :key="session.id"
          :class="['session-item', { active: session.id === activeSessionId }]"
          @click="$emit('select-session', session.id)"
        >
          <div class="session-info" @dblclick="startRename(session)">
            <span v-if="editingId !== session.id" class="session-title">
              <el-icon class="session-icon"><ChatDotRound /></el-icon>
              {{ session.title }}
            </span>
            <el-input
              v-else
              v-model="editTitle"
              size="small"
              class="rename-input"
              @blur="finishRename(session)"
              @keydown.enter="finishRename(session)"
              @keydown.escape="cancelRename"
              :ref="(el) => { if (editingId === session.id) renameInput = el }"
            />
            <span class="session-count">{{ session.message_count || 0 }}</span>
          </div>
          <div class="session-actions">
            <el-button
              text
              size="small"
              :icon="Edit"
              @click.stop="startRename(session)"
              title="重命名"
            />
            <el-button
              text
              size="small"
              :icon="Delete"
              @click.stop="confirmDelete(session)"
              title="删除"
            />
          </div>
        </div>
      </div>
    </div>

    <div v-else class="sidebar-empty">
      暂无对话历史
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { Plus, ChatDotRound, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'

const props = defineProps({
  sessions: { type: Array, default: () => [] },
  activeSessionId: { type: String, default: '' },
})

const emit = defineEmits(['new-session', 'select-session', 'rename-session', 'delete-session'])

const editingId = ref('')
const editTitle = ref('')
const renameInput = ref(null)

const groupLabels = {
  today: '今天',
  yesterday: '昨天',
  week: '前7天',
  earlier: '更早',
}

const groupedSessions = computed(() => {
  const groups = { today: [], yesterday: [], week: [], earlier: [] }
  for (const s of props.sessions) {
    const g = s.time_group || 'earlier'
    if (groups[g]) {
      groups[g].push(s)
    } else {
      groups.earlier.push(s)
    }
  }
  return Object.entries(groups)
    .filter(([, sessions]) => sessions.length > 0)
    .map(([key, sessions]) => ({
      label: groupLabels[key] || key,
      sessions,
    }))
})

function startRename(session) {
  editingId.value = session.id
  editTitle.value = session.title
  nextTick(() => {
    if (renameInput.value) {
      const input = renameInput.value.$el?.querySelector('input') || renameInput.value
      input?.focus?.()
      input?.select?.()
    }
  })
}

function finishRename(session) {
  const title = editTitle.value.trim()
  if (title && title !== session.title) {
    emit('rename-session', { id: session.id, title })
  }
  editingId.value = ''
  editTitle.value = ''
}

function cancelRename() {
  editingId.value = ''
  editTitle.value = ''
}

async function confirmDelete(session) {
  try {
    await ElMessageBox.confirm(
      `确定删除会话「${session.title}」吗？删除后不可恢复。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    emit('delete-session', session.id)
  } catch {
    // 用户取消
  }
}
</script>

<style scoped>
.sidebar {
  width: 280px;
  height: 100%;
  background: var(--bg-primary);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 16px;
}

.sidebar-header .el-button {
  width: 100%;
}

.sidebar-title {
  padding: 8px 16px 4px;
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.session-group {
  margin-bottom: 2px;
}

.group-label {
  padding: 12px 16px 4px;
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
  letter-spacing: 0.03em;
}

.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px 8px 16px;
  margin: 1px 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
  color: var(--text-secondary);
  font-size: 13px;
}

.session-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.session-item.active {
  background: var(--bg-elevated);
  color: var(--accent);
}

.session-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.session-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.session-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
}

.session-count {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  padding: 0 6px;
  border-radius: 10px;
  flex-shrink: 0;
}

.session-actions {
  display: flex;
  opacity: 0;
  transition: opacity var(--duration-fast);
  flex-shrink: 0;
}

.session-item:hover .session-actions {
  opacity: 1;
}

.rename-input {
  flex: 1;
}

.sidebar-empty {
  padding: 24px 16px;
  text-align: center;
  font-size: 13px;
  color: var(--text-muted);
}
</style>
