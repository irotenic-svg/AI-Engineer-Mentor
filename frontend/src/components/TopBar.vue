<template>
  <header class="topbar">
    <div class="topbar-left">
      <span class="topbar-logo">📚</span>
      <span class="topbar-title">AI 课程咨询助手</span>
    </div>
    <div class="topbar-right">
      <el-tag size="small" type="info" effect="light">{{ username }}</el-tag>
      <el-button text size="small" @click="$emit('logout')">
        <el-icon style="margin-right:4px"><SwitchButton /></el-icon>
        登出
      </el-button>
    </div>
  </header>
</template>

<script setup>
import { SwitchButton } from '@element-plus/icons-vue'

defineProps({
  username: { type: String, default: '' },
})

defineEmits(['logout'])
</script>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 24px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
  z-index: 20;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.topbar-logo {
  font-size: 20px;
}

.topbar-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.02em;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
