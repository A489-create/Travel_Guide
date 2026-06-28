import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as conversationApi from '@/api/conversation'

/**
 * 对话状态管理
 *
 * 管理：
 *   - 会话列表（conversations）
 *   - 当前会话（currentConversation）与其消息列表（messages）
 *   - SSE 流式状态（streaming / streamingContent / lastPlanId）
 */
export const useConversationStore = defineStore('conversation', () => {
  // 会话列表
  const conversations = ref([])
  const conversationTotal = ref(0)
  // 当前会话对象
  const currentConversation = ref(null)
  // 当前会话消息列表
  const messages = ref([])
  // 列表/详情加载状态
  const loading = ref(false)
  const error = ref(null)

  // ===== SSE 流式状态 =====
  // 是否正在流式接收回复
  const streaming = ref(false)
  // 正在累积的流式文本
  const streamingContent = ref('')
  // 最近一次生成行程的 ID（done 事件携带）
  const lastPlanId = ref(null)
  // 待确认的行程变更动作（actionRequired 事件触发）
  const pendingAction = ref(null)
  // 用于中止请求的控制器
  let abortController = null

  /**
   * 获取会话列表（分页）
   * @param {Number} page - 页码
   * @param {Number} pageSize - 每页条数
   */
  const fetchConversations = async (page = 1, pageSize = 20) => {
    loading.value = true
    error.value = null
    try {
      const result = await conversationApi.getConversationList({ page, page_size: pageSize })
      conversations.value = result.list || []
      conversationTotal.value = result.total || 0
      return result
    } catch (err) {
      error.value = err.message || '获取会话列表失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 创建新会话
   * @param {String} [title] - 可选标题
   */
  const createConversation = async (title) => {
    loading.value = true
    error.value = null
    try {
      const data = title ? { title } : {}
      const conv = await conversationApi.createConversation(data)
      // 新会话插入列表头部
      conversations.value.unshift(conv)
      // 切换到新会话
      await selectConversation(conv)
      return conv
    } catch (err) {
      error.value = err.message || '创建会话失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 选中某个会话：设置当前会话并加载消息
   * @param {Object} conv - 会话对象（需含 id）
   */
  const selectConversation = async (conv) => {
    if (!conv) {
      currentConversation.value = null
      messages.value = []
      return
    }
    loading.value = true
    error.value = null
    try {
      const detail = await conversationApi.getConversationDetail(conv.id)
      currentConversation.value = detail
      messages.value = detail.messages || []
      lastPlanId.value = null
      return detail
    } catch (err) {
      error.value = err.message || '加载会话详情失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 删除会话（软删除）
   * @param {Number} id - 会话 ID
   */
  const removeConversation = async (id) => {
    loading.value = true
    error.value = null
    try {
      await conversationApi.deleteConversation(id)
      conversations.value = conversations.value.filter((c) => c.id !== id)
      // 若删除的是当前会话，清空选中状态
      if (currentConversation.value?.id === id) {
        currentConversation.value = null
        messages.value = []
      }
    } catch (err) {
      error.value = err.message || '删除会话失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 发送消息（SSE 流式）
   *
   * 流程：
   *   1. 先把 user 消息追加到 messages
   *   2. 创建一个占位 assistant 消息，streamingContent 实时填充
   *   3. 流结束后把完整文本写入占位消息，并记录 planId
   *
   * 区分"新建"与"更新"：若发送前 currentConversation.current_plan_id 已存在，
   * 则本次为迭代修改（后端会更新该 plan 而非新建）。
   *
   * @param {String} content - 消息内容
   * @returns {Promise<Number|null>} 生成的行程 ID（无则 null）
   */
  const sendMessage = async (content) => {
    if (!currentConversation.value) {
      throw new Error('请先创建或选择一个会话')
    }
    if (streaming.value) {
      throw new Error('正在生成回复，请稍候')
    }

    const conversationId = currentConversation.value.id
    // 记录发送前的 current_plan_id，用于判断本次是新建还是更新
    const hadPlanBefore = !!currentConversation.value.current_plan_id
    // 1. 追加用户消息
    messages.value.push({
      role: 'user',
      content,
      created_at: new Date().toISOString()
    })

    // 2. 准备流式占位 assistant 消息
    streaming.value = true
    streamingContent.value = ''
    lastPlanId.value = null
    abortController = new AbortController()

    let planId = null
    let isUpdate = false
    let actionRequired = false
    try {
      await conversationApi.sendMessageStream({
        conversationId,
        content,
        signal: abortController.signal,
        onContent: (chunk) => {
          streamingContent.value += chunk
        },
        onDone: (pid) => {
          planId = pid
          lastPlanId.value = pid
          // 若发送前已有 plan 且后端返回了 planId，则判定为更新
          isUpdate = hadPlanBefore && !!pid
        },
        onActionRequired: (event) => {
          actionRequired = true
          pendingAction.value = {
            conversationId,
            changes: event.changes || {},
            pendingParams: event.pendingParams || {}
          }
        },
        onError: (message, code) => {
          // 错误也作为一条 assistant 消息展示
          streamingContent.value = `[错误] ${message}`
        }
      })
    } finally {
      // 3. 把流式内容写入消息列表（仅非确认流程）
      const fullText = streamingContent.value
      if (fullText && !actionRequired) {
        messages.value.push({
          role: 'assistant',
          content: fullText,
          created_at: new Date().toISOString()
        })
      }
      // 刷新当前会话的解析参数（destination/days/current_plan_id 等）
      // 简单实现：重新拉取会话详情以同步参数
      try {
        const detail = await conversationApi.getConversationDetail(conversationId)
        currentConversation.value = detail
      } catch (_) {
        // 同步失败不影响主流程
      }
      // 同步刷新会话列表，确保侧边栏和攻略列表不展示旧数据
      try {
        await fetchConversations()
      } catch (_) {
        // 同步失败不影响主流程
      }
      // 同步刷新攻略列表 store，保证"我的攻略"页面实时一致
      try {
        const { useTravelStore } = await import('@/stores/travel')
        const travelStore = useTravelStore()
        await travelStore.fetchList()
      } catch (_) {
        // 同步失败不影响主流程
      }
      streaming.value = false
      streamingContent.value = ''
      abortController = null
    }

    // 返回对象，包含 planId 和是否为更新，供调用方区分文案
    return { planId, isUpdate, actionRequired }
  }

  /**
   * 确认行程变更保存方式并触发后端生成
   * @param {String} action - "update" 或 "create"
   */
  const confirmPlanAction = async (action) => {
    if (!pendingAction.value) return null

    const { conversationId } = pendingAction.value
    streaming.value = true
    streamingContent.value = ''
    error.value = null

    try {
      const result = await conversationApi.confirmPlanAction(conversationId, action)
      pendingAction.value = null
      lastPlanId.value = result?.data?.plan_id || null
      // 刷新当前会话详情和列表
      await selectConversation({ id: conversationId })
      await fetchConversations()
      // 同步刷新攻略列表 store，保证"我的攻略"页面实时一致
      try {
        const { useTravelStore } = await import('@/stores/travel')
        const travelStore = useTravelStore()
        await travelStore.fetchList()
      } catch (_) {
        // 同步失败不影响主流程
      }
      return result
    } catch (err) {
      error.value = err.message || '确认行程变更失败'
      throw err
    } finally {
      streaming.value = false
      streamingContent.value = ''
    }
  }

  /**
   * 中止当前流式请求
   */
  const abortStream = () => {
    if (abortController) {
      abortController.abort()
      abortController = null
      streaming.value = false
    }
  }

  /**
   * 重置 store 状态
   */
  const reset = () => {
    conversations.value = []
    conversationTotal.value = 0
    currentConversation.value = null
    messages.value = []
    streaming.value = false
    streamingContent.value = ''
    lastPlanId.value = null
    pendingAction.value = null
    error.value = null
  }

  return {
    // 状态
    conversations,
    conversationTotal,
    currentConversation,
    messages,
    loading,
    error,
    streaming,
    streamingContent,
    lastPlanId,
    pendingAction,
    // 动作
    fetchConversations,
    createConversation,
    selectConversation,
    removeConversation,
    sendMessage,
    confirmPlanAction,
    abortStream,
    reset
  }
})
