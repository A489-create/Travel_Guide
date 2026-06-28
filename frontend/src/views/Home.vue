<template>
  <div class="chat-page">
    <!-- 左侧：会话列表 -->
    <aside class="conv-sidebar">
      <div class="conv-sidebar-header">
        <span class="sidebar-title">会话列表</span>
        <el-button type="primary" size="small" :icon="Plus" @click="handleNewConversation" circle />
      </div>
      <div class="conv-list" v-loading="convStore.loading">
        <div
          v-for="conv in convStore.conversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: convStore.currentConversation?.id === conv.id }"
          @click="convStore.selectConversation(conv)"
        >
          <div class="conv-item-title">{{ conv.title || '新对话' }}</div>
          <div class="conv-item-meta" v-if="conv.destination">
            {{ conv.destination }}
            <span v-if="conv.days"> · {{ conv.days }}天</span>
          </div>
          <el-icon class="conv-item-delete" @click.stop="handleDelete(conv)">
            <Delete />
          </el-icon>
        </div>
        <el-empty v-if="!convStore.conversations.length && !convStore.loading" description="暂无会话" :image-size="60" />
      </div>
    </aside>

    <!-- 右侧：对话区 -->
    <section class="chat-main">
      <!-- 顶部：当前会话信息 -->
      <header class="chat-header" v-if="convStore.currentConversation">
        <div class="chat-title">{{ convStore.currentConversation.title }}</div>
        <div class="chat-params">
          <el-tag v-if="convStore.currentConversation.destination" size="small" type="primary">
            {{ convStore.currentConversation.destination }}
          </el-tag>
          <el-tag v-if="convStore.currentConversation.days" size="small">
            {{ convStore.currentConversation.days }} 天
          </el-tag>
          <el-tag v-if="convStore.currentConversation.budget" size="small" type="success">
            ¥{{ convStore.currentConversation.budget }}
          </el-tag>
          <el-tag
            v-for="pref in (convStore.currentConversation.preferences || [])"
            :key="pref"
            size="small"
            type="warning"
          >
            {{ pref }}
          </el-tag>
        </div>
      </header>
      <header class="chat-header" v-else>
        <div class="chat-title">智能行程规划</div>
        <div class="chat-hint">输入你的旅行想法，AI 为你定制专属行程</div>
      </header>

      <!-- 消息区 -->
      <div class="message-list" ref="messageListRef">
        <!-- 空状态引导 -->
        <div v-if="!convStore.currentConversation" class="empty-chat">
          <el-icon :size="48" color="var(--color-text-quaternary)"><ChatDotRound /></el-icon>
          <p class="empty-title">开始你的第一次对话</p>
          <p class="empty-desc">点击左上角 + 创建新会话</p>
        </div>

        <template v-else>
          <div
            v-for="(msg, idx) in convStore.messages"
            :key="idx"
            class="message-row"
            :class="msg.role"
          >
            <div class="message-avatar">
              <el-icon v-if="msg.role === 'user'"><UserFilled /></el-icon>
              <el-icon v-else><Promotion /></el-icon>
            </div>
            <div class="message-body">
              <div class="message-content" v-html="renderContent(msg.content)"></div>
            </div>
          </div>

          <!-- 流式输出中 -->
          <div v-if="convStore.streaming" class="message-row assistant">
            <div class="message-avatar">
              <el-icon><Promotion /></el-icon>
            </div>
            <div class="message-body">
              <div class="message-content streaming" v-html="renderContent(convStore.streamingContent)">
              </div>
              <span class="streaming-cursor" v-if="convStore.streamingContent">▌</span>
            </div>
          </div>
        </template>
      </div>

      <!-- 行程卡片（生成成功后展示） -->
      <transition name="slide-up">
        <div v-if="showPlanCard" class="plan-card">
          <el-icon class="plan-icon"><Ticket /></el-icon>
          <div class="plan-info">
            <div class="plan-title">{{ planCardTitle }}</div>
            <div class="plan-desc">点击查看完整行程规划</div>
          </div>
          <el-button type="primary" size="small" @click="goPlanDetail">查看行程</el-button>
        </div>
      </transition>

      <!-- 输入区 -->
      <footer class="chat-input-area">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          :disabled="!convStore.currentConversation || convStore.streaming"
          :placeholder="inputPlaceholder"
          resize="none"
          @keydown.enter.exact.prevent="handleSend"
          class="chat-input"
        />
        <div class="input-actions">
          <el-button
            v-if="convStore.streaming"
            type="danger"
            :icon="Close"
            @click="convStore.abortStream"
          >
            停止
          </el-button>
          <el-button
            v-else
            type="primary"
            :icon="Promotion"
            :disabled="!inputText.trim() || !convStore.currentConversation"
            @click="handleSend"
          >
            发送
          </el-button>
        </div>
      </footer>
    </section>

    <!-- 行程变更确认弹窗 -->
    <el-dialog
      v-model="planActionDialogVisible"
      title="检测到行程变更"
      width="420px"
      :close-on-click-modal="false"
      :show-close="false"
    >
      <p class="plan-action-tip">您的最新需求与当前攻略存在以下差异，请选择保存方式：</p>
      <div class="plan-action-changes">
        <div v-for="(item, key) in planActionChanges" :key="key" class="change-row">
          <span class="change-label">{{ item.label }}：</span>
          <span class="change-old">{{ item.oldText }}</span>
          <el-icon class="change-arrow"><ArrowRight /></el-icon>
          <span class="change-new">{{ item.newText }}</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="handlePlanAction('create')">创建新攻略</el-button>
        <el-button type="primary" @click="handlePlanAction('update')">更新当前攻略</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useConversationStore } from '@/stores/conversation'
import {
  Plus,
  Delete,
  UserFilled,
  Promotion,
  ChatDotRound,
  Ticket,
  Close,
  ArrowRight
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const convStore = useConversationStore()

const inputText = ref('')
const messageListRef = ref(null)
const showPlanCard = ref(false)
const planActionDialogVisible = ref(false)
// 最近一次行程保存操作：'create' | 'update' | null，用于卡片标题精准文案
const lastPlanAction = ref(null)

/**
 * 将 pendingAction.changes 格式化为弹窗展示数据
 */
const planActionChanges = computed(() => {
  const changes = convStore.pendingAction?.changes || {}
  const result = {}
  const labelMap = {
    destination: '目的地',
    days: '天数',
    budget: '预算',
    preferences: '偏好'
  }
  for (const [key, value] of Object.entries(changes)) {
    const label = labelMap[key] || key
    let oldText = value.old ?? '无'
    let newText = value.new ?? '无'
    if (key === 'preferences') {
      oldText = Array.isArray(value.old) ? value.old.join('、') : '无'
      newText = Array.isArray(value.new) ? value.new.join('、') : '无'
    }
    if (key === 'budget') {
      oldText = value.old !== null ? `¥${value.old}` : '未指定'
      newText = value.new !== null ? `¥${value.new}` : '未指定'
    }
    result[key] = { label, oldText, newText }
  }
  return result
})

/**
 * 行程卡片标题：根据最近一次操作与会话状态区分"已生成"/"已更新"/"新攻略已创建"
 */
const planCardTitle = computed(() => {
  if (lastPlanAction.value === 'create') {
    return '新攻略已创建'
  }
  if (lastPlanAction.value === 'update') {
    return '当前攻略已更新'
  }
  return '行程已生成'
})

/**
 * 输入框占位文本：已有 plan 时提示可迭代修改
 */
const inputPlaceholder = computed(() => {
  if (convStore.currentConversation?.current_plan_id) {
    return '如需修改行程，直接告诉我（例如：把第3天改成去迪士尼）'
  }
  return '输入你的旅行需求，例如：我想去东京玩3天，预算5000元，喜欢美食和文化'
})

/**
 * 发送消息
 */
const handleSend = async () => {
  const content = inputText.value.trim()
  if (!content) return
  if (!convStore.currentConversation) {
    ElMessage.warning('请先创建会话')
    return
  }
  if (convStore.streaming) return

  inputText.value = ''
  showPlanCard.value = false
  lastPlanAction.value = null

  try {
    const { planId, isUpdate, actionRequired } = await convStore.sendMessage(content)
    if (actionRequired) {
      planActionDialogVisible.value = true
    } else if (planId) {
      showPlanCard.value = true
      ElMessage.success(isUpdate ? '行程已更新' : '行程已生成')
    }
  } catch (err) {
    ElMessage.error(err.message || '发送失败')
  }
}

/**
 * 创建新会话
 */
const handleNewConversation = async () => {
  try {
    await convStore.createConversation()
    showPlanCard.value = false
  } catch (err) {
    ElMessage.error(err.message || '创建会话失败')
  }
}

/**
 * 删除会话
 */
const handleDelete = (conv) => {
  ElMessageBox.confirm(
    `确认删除会话「${conv.title || '新对话'}」？`,
    '删除确认',
    { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
  )
    .then(async () => {
      try {
        await convStore.removeConversation(conv.id)
        ElMessage.success('删除成功')
      } catch (err) {
        ElMessage.error(err.message || '删除失败')
      }
    })
    .catch(() => {})
}

/**
 * 处理行程变更保存方式选择
 * @param {String} action - "update" 或 "create"
 */
const handlePlanAction = async (action) => {
  planActionDialogVisible.value = false
  try {
    const result = await convStore.confirmPlanAction(action)
    if (result?.data?.plan_id) {
      lastPlanAction.value = action
      showPlanCard.value = true
      ElMessage.success(action === 'update' ? '当前攻略已更新' : '新攻略已创建')
    }
  } catch (err) {
    ElMessage.error(err.message || '确认失败')
  }
}

/**
 * 跳转到行程详情
 */
const goPlanDetail = () => {
  if (convStore.lastPlanId) {
    router.push(`/travel/${convStore.lastPlanId}`)
  }
}

/**
 * 渲染消息内容：
 *   - 剥离 <plan>...</plan> JSON 块（已单独存为 TravelPlan）
 *   - 转义 HTML 特殊字符
 *   - 保留换行
 *   - 加粗 **text**
 */
const renderContent = (raw) => {
  if (!raw) return ''
  // 剥离 plan 块
  let text = raw.replace(/<plan>[\s\S]*?<\/plan>/g, '').trim()
  // HTML 转义
  text = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  // 加粗 **text**
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // 换行
  text = text.replace(/\n/g, '<br>')
  return text
}

/**
 * 自动滚动到底部
 */
const scrollToBottom = () => {
  nextTick(() => {
    const el = messageListRef.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

// 消息变化时滚动到底部
watch(
  () => convStore.messages.length,
  () => scrollToBottom()
)
// 流式内容变化时滚动
watch(
  () => convStore.streamingContent,
  () => scrollToBottom()
)
// 切换会话时重置本地卡片状态，避免旧会话卡片残留
watch(
  () => convStore.currentConversation?.id,
  () => {
    showPlanCard.value = false
    lastPlanAction.value = null
  }
)

onMounted(() => {
  convStore.fetchConversations().catch(() => {
    // 静默失败，用户可手动重试
  })
})
</script>

<style scoped>
.chat-page {
  display: flex;
  height: 100%;
  gap: var(--space-4);
  max-width: 100%;
}

/* ===== 左侧会话列表 ===== */
.conv-sidebar {
  width: 240px;
  flex-shrink: 0;
  background-color: var(--color-surface);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.conv-sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-border-light);
}

.sidebar-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conv-item {
  position: relative;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background-color var(--transition-fast);
  margin-bottom: 4px;
}

.conv-item:hover {
  background-color: var(--color-border-light);
}

.conv-item.active {
  background-color: var(--color-primary-bg);
}

.conv-item-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-right: 20px;
}

.conv-item-meta {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

.conv-item-delete {
  position: absolute;
  top: 10px;
  right: 10px;
  font-size: 14px;
  color: var(--color-text-quaternary);
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.conv-item:hover .conv-item-delete {
  opacity: 1;
}

.conv-item-delete:hover {
  color: var(--color-danger);
}

/* ===== 右侧对话区 ===== */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: var(--color-surface);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  overflow: hidden;
  min-width: 0;
}

.chat-header {
  padding: 14px 20px;
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
}

.chat-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.chat-params {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.chat-hint {
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

/* 消息列表 */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-chat {
  margin: auto;
  text-align: center;
}

.empty-title {
  font-size: 15px;
  font-weight: 500;
  color: var(--color-text-secondary);
  margin-top: 12px;
}

.empty-desc {
  font-size: 13px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

/* 消息行 */
.message-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.message-row.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}

.message-row.user .message-avatar {
  background-color: var(--color-primary);
  color: #fff;
}

.message-row.assistant .message-avatar {
  background-color: var(--color-success-bg, #e8f5e9);
  color: var(--color-success, #2e7d32);
}

.message-body {
  max-width: 75%;
  position: relative;
}

.message-row.user .message-body {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.message-content {
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.message-row.user .message-content {
  background-color: var(--color-primary);
  color: #fff;
  border-top-right-radius: 4px;
}

.message-row.assistant .message-content {
  background-color: var(--color-border-light);
  color: var(--color-text-primary);
  border-top-left-radius: 4px;
}

.message-content.streaming {
  min-height: 20px;
}

.streaming-cursor {
  display: inline-block;
  color: var(--color-primary);
  animation: blink 1s infinite;
  font-size: 14px;
  margin-left: 2px;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

/* 行程卡片 */
.plan-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  margin: 0 20px 12px;
  background-color: var(--color-primary-bg);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-md);
}

.plan-icon {
  font-size: 24px;
  color: var(--color-primary);
}

.plan-info {
  flex: 1;
}

.plan-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-primary-dark);
}

.plan-desc {
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-top: 2px;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all var(--transition-base);
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

/* 输入区 */
.chat-input-area {
  padding: 12px 20px 16px;
  border-top: 1px solid var(--color-border-light);
  display: flex;
  gap: 12px;
  align-items: flex-end;
  flex-shrink: 0;
}

.chat-input {
  flex: 1;
}

:deep(.chat-input .el-textarea__inner) {
  border-radius: var(--radius-md);
  font-size: 14px;
  line-height: 1.5;
  resize: none;
}

.input-actions {
  flex-shrink: 0;
}

/* 行程变更确认弹窗 */
.plan-action-tip {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0 0 16px;
}

.plan-action-changes {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.change-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.change-label {
  color: var(--color-text-secondary);
  flex-shrink: 0;
  min-width: 48px;
}

.change-old {
  color: var(--color-text-tertiary);
  text-decoration: line-through;
}

.change-arrow {
  color: var(--color-text-quaternary);
}

.change-new {
  color: var(--color-primary);
  font-weight: 500;
}
</style>
