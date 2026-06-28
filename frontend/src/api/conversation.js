import api from './request'
import { getAccessToken } from '@/utils/tokenStorage'

/**
 * 对话模块 API
 * 包含会话 CRUD 与 SSE 流式消息发送
 */

/**
 * 获取会话列表（分页）
 * @param {Object} params - { page, pageSize }
 */
export const getConversationList = (params) => {
  return api.get('/conversations', { params })
}

/**
 * 创建新会话
 * @param {Object} data - { title? }
 */
export const createConversation = (data = {}) => {
  return api.post('/conversations', data)
}

/**
 * 获取会话详情（含消息列表）
 * @param {Number} id - 会话 ID
 */
export const getConversationDetail = (id) => {
  return api.get(`/conversations/${id}`)
}

/**
 * 删除会话（软删除）
 * @param {Number} id - 会话 ID
 */
export const deleteConversation = (id) => {
  return api.delete(`/conversations/${id}`)
}

/**
 * 设置会话的当前行程（用于在多个历史行程间切换"当前编辑"的行程）
 * @param {Number} conversationId - 会话 ID
 * @param {Number} planId - 行程 ID
 */
export const setCurrentPlan = (conversationId, planId) => {
  return api.put(`/conversations/${conversationId}/current-plan`, { plan_id: planId })
}

/**
 * 确认行程变更保存方式
 * @param {Number} conversationId - 会话 ID
 * @param {String} action - "update" 或 "create"
 */
export const confirmPlanAction = (conversationId, action) => {
  return api.post(`/conversations/${conversationId}/plan-action`, { action })
}

/**
 * 发送消息（SSE 流式响应）
 *
 * 使用 fetch + ReadableStream 消费 SSE，不用 EventSource
 * （因需携带 Authorization 请求头）。
 *
 * @param {Object} options
 * @param {Number} options.conversationId - 会话 ID
 * @param {String} options.content - 消息内容
 * @param {Function} [options.onContent] - 文本片段回调 (chunk: string) => void
 * @param {Function} [options.onDone] - 流结束回调 (planId: number|null) => void
 * @param {Function} [options.onError] - 错误回调 (message: string, code: number) => void
 * @param {Function} [options.onActionRequired] - 需要确认行程变更回调 (event: object) => void
 * @param {AbortSignal} [options.signal] - 可中止信号
 * @returns {Promise<void>}
 */
export const sendMessageStream = async ({
  conversationId,
  content,
  onContent,
  onDone,
  onError,
  onActionRequired,
  signal
}) => {
  const token = getAccessToken()
  const url = `/api/conversations/${conversationId}/messages`

  let response
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : ''
      },
      body: JSON.stringify({ content }),
      signal
    })
  } catch (err) {
    if (err.name === 'AbortError') return
    onError && onError('网络连接失败', 50000)
    return
  }

  if (!response.ok) {
    // 非 2xx：尝试解析错误响应体
    let message = `请求失败 (${response.status})`
    try {
      const body = await response.json()
      message = body.message || message
    } catch (_) {
      // 忽略 JSON 解析失败
    }
    onError && onError(message, 50000)
    return
  }

  // 读取 SSE 流
  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    // SSE 按双换行分割事件，按单换行分割行
    const lines = buffer.split('\n')
    // 保留最后一个可能不完整的行
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed || !trimmed.startsWith('data:')) continue

      const dataStr = trimmed.slice(5).trim()
      if (!dataStr) continue

      let event
      try {
        event = JSON.parse(dataStr)
      } catch (_) {
        continue
      }

      // 分发事件
      if (event.error) {
        onError && onError(event.message || 'LLM 调用失败', event.code || 20007)
        return
      }
      if (event.done) {
        onDone && onDone(event.planId ?? null)
        return
      }
      if (event.actionRequired) {
        onActionRequired && onActionRequired(event)
        return
      }
      if (event.content !== undefined) {
        onContent && onContent(event.content)
      }
    }
  }
}
