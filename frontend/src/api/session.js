import axios from 'axios'
import { getAuthHeaders } from './auth'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

/**
 * 获取所有会话
 * @returns {Promise<{sessions: Array}>}
 */
export function listSessions() {
  return api
    .get('/sessions', { headers: getAuthHeaders() })
    .then((res) => res.data)
}

/**
 * 创建新会话
 * @param {string} title
 * @param {string} firstMessage 首条用户消息，后端据此生成智能标题
 * @returns {Promise<{session: Object}>}
 */
export function createSession(title = '新对话', firstMessage = '') {
  return api
    .post('/sessions', { title, first_message: firstMessage }, { headers: getAuthHeaders() })
    .then((res) => res.data)
}

/**
 * 重命名会话
 * @param {string} sessionId
 * @param {string} title
 */
export function renameSession(sessionId, title) {
  return api
    .patch(`/sessions/${sessionId}`, { title }, { headers: getAuthHeaders() })
    .then((res) => res.data)
}

/**
 * 删除会话
 * @param {string} sessionId
 */
export function deleteSession(sessionId) {
  return api
    .delete(`/sessions/${sessionId}`, { headers: getAuthHeaders() })
    .then((res) => res.data)
}

/**
 * 获取会话历史消息
 * @param {string} sessionId
 * @returns {Promise<{session_id: string, messages: Array}>}
 */
export function getSessionMessages(sessionId) {
  return api
    .get(`/sessions/${sessionId}/messages`, { headers: getAuthHeaders() })
    .then((res) => res.data)
}
