<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">📚</div>
      <h1 class="login-title">AI 课程咨询助手</h1>
      <p class="login-subtitle">智能课程顾问，为您答疑解惑</p>

      <el-form @submit.prevent="handleLogin" class="login-form">
        <el-form-item>
          <el-input
            v-model="username"
            placeholder="请输入用户名"
            size="large"
            :prefix-icon="User"
            clearable
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleLogin"
            class="login-btn"
            :disabled="!username.trim()"
          >
            登 录
          </el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { login } from '@/api/auth'

const router = useRouter()
const route = useRoute()

const username = ref('')
const loading = ref(false)

async function handleLogin() {
  const name = username.value.trim()
  if (!name) return

  loading.value = true
  try {
    await login(name)
    localStorage.setItem('course_assistant_user', name)
    ElMessage.success(`欢迎，${name}！`)
    const redirect = route.query.redirect || '/chat'
    router.push(redirect)
  } catch (err) {
    ElMessage.error('登录失败，请稍后重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: var(--bg-root);
}

.login-card {
  width: 400px;
  padding: 48px 40px;
  background: var(--bg-primary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  text-align: center;
}

.login-logo {
  font-size: 48px;
  margin-bottom: 16px;
}

.login-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
  letter-spacing: 0.02em;
}

.login-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 32px;
}

.login-form {
  text-align: left;
}

.login-btn {
  width: 100%;
}

.login-btn :deep(.el-button) {
  font-size: 15px;
  letter-spacing: 0.05em;
}
</style>
