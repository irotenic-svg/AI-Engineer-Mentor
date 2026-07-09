<template>
  <div class="chat-input-comp">
    <!-- Writing surface -->
    <div class="input-writing-surface">
      <div class="input-accent-strip"></div>

      <!-- Attached files display -->
      <div v-if="files.length > 0" class="file-chips">
        <div v-for="(f, i) in files" :key="i" class="file-chip">
          <span class="file-chip-icon">📎</span>
          <span class="file-chip-name" :title="f.name">{{ f.name }}</span>
          <el-button
            :icon="Close"
            circle
            size="small"
            class="file-chip-remove"
            :disabled="disabled"
            @click="$emit('remove-file', i)"
          />
        </div>
      </div>

      <!-- File upload button -->
      <div class="input-toolbar">
        <el-upload
          :auto-upload="false"
          :show-file-list="false"
          :accept="acceptTypes"
          :before-upload="handleBeforeUpload"
          @change="handleFileChange"
        >
          <el-button
            :icon="UploadIcon"
            circle
            size="small"
            :disabled="disabled"
            title="上传文件"
            class="upload-btn"
          />
        </el-upload>
      </div>

      <textarea
        ref="taRef"
        :value="modelValue"
        class="input-textarea"
        :placeholder="placeholder"
        :disabled="disabled"
        rows="2"
        @input="onInput"
        @keydown="handleKeydown"
      ></textarea>
    </div>

    <!-- Action bar -->
    <div class="input-action-bar">
      <span class="input-keyhint">
        <kbd>Enter</kbd> 发送 · <kbd>Shift</kbd> + <kbd>Enter</kbd> 换行
      </span>
      <button
        class="send-btn"
        :class="{ loading: loading, active: hasContent && !disabled }"
        :disabled="!hasContent || disabled"
        @click="$emit('send')"
        :title="loading ? '发送中…' : '发送'"
      >
        <span class="send-btn-icon">{{ loading ? '⏳' : '↑' }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Upload as UploadIcon, Close } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: {
    type: String,
    default: "上传的文档不超过32M，文件格式限制为：'pdf', 'docx', 'txt', 'pptx', 'html', 'ipynb'",
  },
  disabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  files: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'send', 'file-upload', 'remove-file'])
const taRef = ref(null)

const acceptTypes = '.pdf,.docx,.txt,.pptx,.html,.ipynb,.xlsx,.md'
const allowedExts = ['pdf', 'docx', 'txt', 'pptx', 'html', 'ipynb', 'xlsx', 'md']
const maxSize = 32 * 1024 * 1024 // 32MB

const hasContent = computed(() => props.modelValue?.trim() || props.files.length > 0)

function onInput(e) {
  emit('update:modelValue', e.target.value)
  const el = taRef.value
  if (el) {
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 180) + 'px'
  }
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    emit('send')
  }
}

function handleBeforeUpload(file) {
  if (file.size > maxSize) {
    ElMessage.error('文件大小不能超过 32M')
    return false
  }
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (!ext || !allowedExts.includes(ext)) {
    ElMessage.error(`不支持的文件格式 '.${ext || 'unknown'}'，允许的格式: ${allowedExts.join(', ')}`)
    return false
  }
  return true
}

function handleFileChange(uploadFile) {
  if (uploadFile && uploadFile.raw) {
    emit('file-upload', uploadFile.raw)
  }
}
</script>

<style scoped>
.chat-input-comp {
  /* max-width inherited from parent .chat-input-wrapper */
}

.input-writing-surface {
  position: relative;
  background: var(--bg-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  transition: border-color var(--duration-normal) var(--ease-out),
    box-shadow var(--duration-normal) var(--ease-out);
}

.input-writing-surface:focus-within {
  border-color: rgba(59, 130, 196, 0.4);
  box-shadow: 0 0 0 3px var(--accent-glow),
    inset 0 0 40px rgba(59, 130, 196, 0.02);
}

.input-accent-strip {
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  background: linear-gradient(
    180deg, transparent 0%, var(--accent) 15%, var(--accent) 85%, transparent 100%
  );
  border-radius: 0 2px 2px 0;
  opacity: 0.35;
  transition: opacity var(--duration-normal) var(--ease-out);
}

.input-writing-surface:focus-within .input-accent-strip {
  opacity: 0.7;
}

/* ── File chips ────────────────────────────────────── */
.file-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 10px 16px 0 22px;
}

.file-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px 2px 8px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  max-width: 220px;
}

.file-chip-icon {
  flex-shrink: 0;
  font-size: 12px;
}

.file-chip-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-chip-remove {
  padding: 2px !important;
  width: 18px !important;
  height: 18px !important;
  min-height: 18px !important;
  color: var(--text-muted) !important;
  flex-shrink: 0;
}

.file-chip-remove:hover {
  color: var(--danger) !important;
}

/* ── Toolbar (file upload) ─────────────────────────── */
.input-toolbar {
  display: flex;
  padding: 8px 16px 0 22px;
}

.upload-btn {
  color: var(--text-muted);
  transition: color var(--duration-fast);
}

.upload-btn:hover:not(:disabled) {
  color: var(--accent);
}

.input-textarea {
  display: block;
  width: 100%;
  min-height: 52px;
  max-height: 180px;
  padding: 10px 18px 14px 22px;
  font-family: var(--font-body);
  font-size: 14.5px;
  line-height: 1.7;
  color: var(--text-primary);
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  caret-color: var(--accent);
  letter-spacing: 0.01em;
}

.input-textarea::placeholder {
  color: var(--text-muted);
  opacity: 0.45;
  font-style: italic;
}

.input-textarea:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
}

.input-keyhint {
  font-size: 11px;
  color: var(--text-muted);
  opacity: 0.55;
  letter-spacing: 0.02em;
}

.input-keyhint kbd {
  display: inline-block;
  padding: 2px 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-muted);
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: 3px;
  line-height: 1.4;
  vertical-align: 1px;
}

/* ── Send Button (circular) ────────────────────────── */
.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  padding: 0;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: 50%;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  flex-shrink: 0;
}

.send-btn:active:not(:disabled) { transform: scale(0.92); }
.send-btn:disabled { cursor: not-allowed; opacity: 0.3; }

.send-btn.active {
  background: var(--accent);
  border-color: var(--accent);
}

.send-btn.active:hover {
  background: #4a94d4;
  border-color: #4a94d4;
  box-shadow: 0 0 28px var(--accent-glow-strong);
  transform: scale(1.08);
}

.send-btn.loading {
  background: var(--accent);
  border-color: var(--accent);
  animation: sendPulse 1.8s ease-in-out infinite;
}

.send-btn-icon {
  font-size: 15px;
  color: var(--text-muted);
  line-height: 1;
  transition: color var(--duration-fast) var(--ease-out);
}

.send-btn.active .send-btn-icon,
.send-btn.loading .send-btn-icon { color: #fff; }

@keyframes sendPulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--accent-glow); }
  50% { box-shadow: 0 0 0 14px transparent; }
}

@media (max-width: 640px) {
  .input-textarea {
    padding: 10px 14px 10px 18px;
    font-size: 14px;
    min-height: 46px;
  }
  .send-btn { width: 36px; height: 36px; }
  .file-chip { max-width: 160px; }
}
</style>
