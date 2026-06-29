import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

function getAuthHeaders() {
  const user = localStorage.getItem('course_assistant_user')
  return user ? { 'X-Username': user } : {}
}

/**
 * 发送问题，流式获取 AI 回答 (Server-Sent Events)
 *
 * 用法:
 *   for await (const event of sendMessageStream(question, sessionId)) {
 *     switch (event.type) {
 *       case 'token': ...   // { type: 'token', data: '...' }
 *       case 'done':  ...   // { type: 'done' }
 *       case 'error': ...   // { type: 'error', data: '...' }
 *     }
 *   }
 */
export async function* sendMessageStream(question, sessionId = 'default') {
  const authHeaders = getAuthHeaders()
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify({ question, session_id: sessionId }),
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({ error: 'Network error' }))
    throw new Error(err.error || `HTTP ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''

    for (const part of parts) {
      const lines = part.split('\n')
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6))
            yield event
          } catch {
            // skip malformed JSON
          }
        }
      }
    }
  }

  // Flush remaining buffer
  if (buffer.trim()) {
    const lines = buffer.split('\n')
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const event = JSON.parse(line.slice(6))
          yield event
        } catch {
          // skip
        }
      }
    }
  }
}

/**
 * 上传文件到后端，获取提取的文本内容
 * 返回 { file_id, filename, content_text }
 */
export async function uploadFile(file) {
  const formData = new FormData()
  formData.append('file', file)

  const authHeaders = {}
  const user = localStorage.getItem('course_assistant_user')
  if (user) {
    authHeaders['X-Username'] = user
  }

  const response = await fetch('/api/upload', {
    method: 'POST',
    headers: authHeaders,
    body: formData,
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({ error: '上传失败' }))
    throw new Error(err.error || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * 健康检查
 */
export function healthCheck() {
  return api.get('/health').then((res) => res.data)
}

export default api
