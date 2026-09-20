/**
 * 读取后端 AI 长耗时接口的 NDJSON 流。
 *
 * 这不是把 AI 结果拆成小块，而是接收处理中的探活消息，
 * 最终仍只返回原接口的 data，保持调用方原有的数据结构。
 */
const isAuthenticationFailure = (code, message) => {
  if (Number(code) === 401) return true
  return Number(code) === 403 && /未授权|重新登录|登录已过期|登录失效/.test(String(message || ''))
}

let isRedirectingToLogin = false

function redirectToLogin(message) {
  if (isRedirectingToLogin) return
  isRedirectingToLogin = true
  if (typeof localStorage !== 'undefined' && typeof localStorage.removeItem === 'function') {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_info')
  }
  if (typeof window !== 'undefined') {
    const baseUrl = import.meta.env?.BASE_URL || '/'
    window.setTimeout(() => {
      window.location.href = `${baseUrl}#/login`
    }, 1500)
  }
  // 保留后端原文给调用方，避免流式请求绕过 axios 后丢失登录原因。
  return message
}

export async function streamAiRequest(url, data, onEvent, signal) {
  const apiBase = import.meta.env?.VITE_API_BASE_URL || '/api/v1'
  const token = typeof localStorage !== 'undefined' && typeof localStorage.getItem === 'function'
    ? localStorage.getItem('access_token')
    : ''
  const response = await fetch(`${apiBase}${url}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(data || {}),
    signal,
  })

  if (!response.ok) {
    const raw = await response.text().catch(() => '')
    let detail = null
    try { detail = raw ? JSON.parse(raw) : null } catch { /* 非 JSON 错误响应 */ }
    const message = detail?.message || detail?.data?.message || `AI 请求失败（HTTP ${response.status}）`
    if (isAuthenticationFailure(response.status, message)) redirectToLogin(message)
    const error = new Error(message)
    error.data = detail || { code: response.status, message }
    throw error
  }

  if (!response.body) throw new Error('AI 未返回流式内容，请重试')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result = null
  let hasResult = false

  const handleLine = (line) => {
    const normalized = line.trim().replace(/^data:\s*/, '')
    if (!normalized || normalized === '[DONE]' || normalized.startsWith(':')) return

    let event
    try {
      event = JSON.parse(normalized)
    } catch {
      const error = new Error('AI 返回了无法解析的流式数据，请重试')
      error.data = { raw: normalized.slice(0, 200) }
      throw error
    }

    if ((event.code !== undefined && Number(event.code) !== 200) || event.type === 'error') {
      const error = new Error(event.message || 'AI 处理失败')
      if (isAuthenticationFailure(event.code, event.message)) {
        redirectToLogin(event.message)
      }
      error.data = event.data && typeof event.data === 'object'
        ? { ...event.data, ...event }
        : event
      throw error
    }
    if (event.type === 'complete') {
      result = event.data
      hasResult = true
    } else if (event.type) {
      onEvent?.(event.data ?? event)
    } else if (event.data !== undefined) {
      result = event.data
      hasResult = true
    }
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) handleLine(line)
      if (done) break
    }
    if (buffer.trim()) handleLine(buffer)
  } finally {
    reader.releaseLock()
  }

  if (!hasResult) throw new Error('AI 未返回最终结果，请重试')
  return result
}
