import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

/**
 * 登录
 * @param {string} username
 * @returns {Promise<{username: string, token: string}>}
 */
export function login(username) {
  return api.post('/login', { username }).then((res) => res.data)
}

/**
 * 登出
 */
export function logout() {
  return api.post('/logout').then((res) => res.data)
}

/**
 * 获取请求头（含当前用户信息）
 */
export function getAuthHeaders() {
  const user = localStorage.getItem('course_assistant_user')
  return user ? { 'X-Username': user } : {}
}

export default api
