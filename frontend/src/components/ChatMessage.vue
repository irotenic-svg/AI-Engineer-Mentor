<template>
  <div :class="['message-item', role]">
    <div v-if="role === 'ai'" class="message-avatar">📚</div>
    <div class="message-content">
      <div class="message-bubble" v-html="renderedContent"></div>
      <div v-if="sources && sources.length > 0" class="source-panel">
        <el-popover
          placement="right"
          :width="420"
          trigger="click"
          popper-class="source-detail-popover"
        >
          <template #reference>
            <div class="source-toggle-btn">
              <span class="icon">▦</span>
              <span>引用来源 ({{ sources.length }})</span>
            </div>
          </template>
          <div class="source-popover-content">
            <div v-for="(src, i) in sources" :key="i" class="source-popover-item">
              <div class="source-header">
                <el-tag
                  size="small"
                  :type="src.source === 'PubMedQA' ? 'primary' : 'success'"
                  effect="light"
                >
                  {{ src.source }}
                </el-tag>
                <span class="source-index">{{ String(i + 1).padStart(2, '0') }}</span>
              </div>
              <div v-if="src.question" class="source-question">{{ src.question }}</div>
              <div class="source-content">{{ src.content }}</div>
            </div>
          </div>
        </el-popover>
      </div>
    </div>
    <div v-if="role === 'user'" class="message-avatar">👤</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  role: { type: String, required: true },
  content: { type: String, default: '' },
  sources: { type: Array, default: () => [] },
})

const renderedContent = computed(() => {
  if (!props.content) return ''
  let html = props.content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
  return `<p>${html}</p>`
})
</script>
