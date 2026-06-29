<template>
  <div class="welcome-state">
    <div class="welcome-icon">
      <span class="inner-glyph">📚</span>
    </div>
    <div class="welcome-title">{{ welcomeTitle }}</div>
    <div class="greeting">{{ greeting }}</div>
    <div v-if="description" class="description">{{ description }}</div>
    <div v-if="suggestions.length > 0" class="suggestions">
      <div
        v-for="q in suggestions"
        :key="q"
        class="suggestion-chip"
        @click="$emit('select-suggestion', q)"
      >
        {{ q }}
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  welcomeTitle: { type: String, default: '欢迎使用AI课程咨询助手' },
  greeting: { type: String, default: '您好！很高兴为你服务！' },
  description: { type: String, default: '' },
  suggestions: { type: Array, default: () => [] },
})

defineEmits(['select-suggestion'])
</script>

<style scoped>
.welcome-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 55vh;
  text-align: center;
  padding: 40px 24px;
  animation: welcomeReveal 0.8s var(--ease-out);
}

@keyframes welcomeReveal {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.welcome-icon {
  width: 80px;
  height: 80px;
  margin-bottom: 28px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--accent);
  border-radius: 50%;
  opacity: 0.7;
}

.welcome-icon .inner-glyph {
  font-size: 32px;
  z-index: 1;
}

.welcome-title {
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
  letter-spacing: 0.01em;
}

.greeting {
  font-family: var(--font-display);
  font-size: 18px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.description {
  font-size: 14px;
  color: var(--text-secondary);
  max-width: 460px;
  line-height: 1.7;
  margin-bottom: 32px;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  max-width: 580px;
}

.suggestion-chip {
  padding: 10px 20px;
  font-size: 13.5px;
  font-family: var(--font-body);
  border-radius: 24px;
  border: 1px solid var(--border-default);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  white-space: nowrap;
  letter-spacing: 0.01em;
}

.suggestion-chip:hover {
  background: var(--bg-elevated);
  border-color: var(--accent);
  color: var(--accent);
  transform: translateY(-2px);
  box-shadow: 0 4px 20px var(--accent-glow);
}
</style>
