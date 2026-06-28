<template>
  <div class="travel-detail-page" v-loading="loading">
    <!-- 顶部操作栏 -->
    <div class="page-header">
      <el-button :icon="ArrowLeft" @click="goBack" class="back-btn">返回列表</el-button>
      <div class="header-actions">
        <el-button
          v-if="plan && plan.conversation_id"
          type="primary"
          :icon="ChatDotRound"
          @click="goConversation"
        >
          返回对话修改
        </el-button>
        <el-button
          v-if="plan"
          type="danger"
          :icon="Delete"
          :loading="deleting"
          @click="handleDelete"
        >
          删除攻略
        </el-button>
      </div>
    </div>

    <!-- 错误信息 -->
    <el-alert
      v-if="error"
      :title="error"
      type="error"
      show-icon
      :closable="false"
      class="detail-alert"
    />

    <!-- 详情内容 -->
    <div v-if="plan" class="detail-content">
      <div class="result-header">
        <h1 class="result-title">{{ plan.title || plan.destination }} 旅行攻略</h1>
      </div>

      <!-- 行程概要 -->
      <div class="plan-overview">
        <div class="overview-item" v-if="plan.destination">
          <span class="overview-label">目的地</span>
          <span class="overview-value">{{ plan.destination }}</span>
        </div>
        <div class="overview-item" v-if="plan.days">
          <span class="overview-label">天数</span>
          <span class="overview-value">{{ plan.days }} 天</span>
        </div>
        <div class="overview-item" v-if="plan.budget">
          <span class="overview-label">预算</span>
          <span class="overview-value">¥{{ plan.budget }}</span>
        </div>
        <div class="overview-item" v-if="plan.created_at">
          <span class="overview-label">创建时间</span>
          <span class="overview-value">{{ formatDate(plan.created_at) }}</span>
        </div>
      </div>

      <!-- 偏好标签 -->
      <div class="prefs-row" v-if="plan.preferences && plan.preferences.length">
        <span class="prefs-label">偏好：</span>
        <el-tag
          v-for="pref in plan.preferences"
          :key="pref"
          size="small"
          type="warning"
          effect="plain"
        >
          {{ pref }}
        </el-tag>
      </div>

      <!-- 每日行程 -->
      <h3 class="section-title">每日行程</h3>
      <div v-if="daysPlan.length" class="days-list">
        <el-card v-for="d in daysPlan" :key="d.day" class="day-card" shadow="never">
          <div class="day-head">
            <span class="day-tag">第 {{ d.day }} 天</span>
            <span class="day-title">{{ d.date_summary || d.title || '' }}</span>
          </div>

          <!-- 时段活动（新结构：morning/afternoon/evening） -->
          <template v-if="d.morning || d.afternoon || d.evening">
            <div class="period-block" v-if="d.morning">
              <div class="period-head">
                <span class="period-tag morning">上午</span>
                <span class="period-activity">{{ d.morning.activity }}</span>
              </div>
              <div class="period-meta" v-if="d.morning.location">
                地点：{{ d.morning.location }}
              </div>
              <div class="period-meta" v-if="d.morning.duration">
                时长：{{ d.morning.duration }}
              </div>
              <div class="period-desc" v-if="d.morning.description">{{ d.morning.description }}</div>
            </div>
            <div class="period-block" v-if="d.afternoon">
              <div class="period-head">
                <span class="period-tag afternoon">下午</span>
                <span class="period-activity">{{ d.afternoon.activity }}</span>
              </div>
              <div class="period-meta" v-if="d.afternoon.location">
                地点：{{ d.afternoon.location }}
              </div>
              <div class="period-meta" v-if="d.afternoon.duration">
                时长：{{ d.afternoon.duration }}
              </div>
              <div class="period-desc" v-if="d.afternoon.description">{{ d.afternoon.description }}</div>
            </div>
            <div class="period-block" v-if="d.evening">
              <div class="period-head">
                <span class="period-tag evening">晚上</span>
                <span class="period-activity">{{ d.evening.activity }}</span>
              </div>
              <div class="period-meta" v-if="d.evening.location">
                地点：{{ d.evening.location }}
              </div>
              <div class="period-meta" v-if="d.evening.duration">
                时长：{{ d.evening.duration }}
              </div>
              <div class="period-desc" v-if="d.evening.description">{{ d.evening.description }}</div>
            </div>
          </template>

          <!-- 兼容旧结构：activities 数组 -->
          <div v-if="d.activities && d.activities.length" class="day-section">
            <span class="label">活动</span>
            <ul class="bullet-list">
              <li v-for="(a, i) in d.activities" :key="i">{{ a }}</li>
            </ul>
          </div>

          <!-- 餐饮 -->
          <div v-if="d.meals" class="day-section">
            <span class="label">餐饮</span>
            <div class="meals-grid" v-if="typeof d.meals === 'object'">
              <div v-if="d.meals.breakfast"><strong>早：</strong>{{ d.meals.breakfast }}</div>
              <div v-if="d.meals.lunch"><strong>午：</strong>{{ d.meals.lunch }}</div>
              <div v-if="d.meals.dinner"><strong>晚：</strong>{{ d.meals.dinner }}</div>
            </div>
            <span class="text" v-else>{{ d.meals }}</span>
          </div>

          <!-- 交通 -->
          <div v-if="d.transportation" class="day-section">
            <span class="label">交通</span>
            <span class="text">{{ d.transportation }}</span>
          </div>

          <!-- 预估费用 -->
          <div v-if="d.estimated_cost" class="day-section">
            <span class="label">费用</span>
            <span class="text">约 ¥{{ d.estimated_cost }}</span>
          </div>

          <!-- 备注 -->
          <div v-if="d.notes" class="day-section">
            <span class="label">备注</span>
            <span class="text">{{ d.notes }}</span>
          </div>
        </el-card>
      </div>
      <el-empty v-else description="暂无每日行程" />

      <!-- 行李建议 -->
      <h3 class="section-title">行李建议</h3>
      <div v-if="luggage.length" class="luggage-list">
        <el-card v-for="(l, i) in luggage" :key="i" class="luggage-card" shadow="never">
          <div class="luggage-head">{{ l.category }}</div>
          <div v-if="l.items && l.items.length" class="day-section">
            <span class="label">物品</span>
            <ul class="bullet-list">
              <li v-for="(it, j) in l.items" :key="j">{{ it }}</li>
            </ul>
          </div>
          <div v-if="l.tips" class="day-section">
            <span class="label">提示</span>
            <span class="text">{{ l.tips }}</span>
          </div>
        </el-card>
      </div>
      <el-empty v-else description="暂无行李建议" />
    </div>

    <el-empty v-else-if="!loading && !error" description="攻略不存在或已被删除">
      <el-button type="primary" @click="goBack">返回列表</el-button>
    </el-empty>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useTravelStore } from '@/stores/travel'
import { useConversationStore } from '@/stores/conversation'
import { ArrowLeft, Delete, ChatDotRound } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const travelStore = useTravelStore()
const convStore = useConversationStore()
const { currentPlan: plan, loading, error } = storeToRefs(travelStore)

const deleting = ref(false)

/**
 * 每日行程列表（后端返回 days_plan 字段）
 */
const daysPlan = computed(() => {
  return plan.value?.days_plan || plan.value?.daysPlan || []
})

/**
 * 行李建议列表（后端返回 luggage 字段）
 */
const luggage = computed(() => {
  return plan.value?.luggage || []
})

/**
 * 格式化日期（仅保留日期部分）
 */
const formatDate = (value) => {
  if (!value) return ''
  return String(value).slice(0, 10)
}

/**
 * 返回列表页
 */
const goBack = () => {
  router.push('/travel/list')
}

/**
 * 返回关联会话进行迭代修改
 *
 * 通过 conversation_id 查找会话并选中，跳转到对话页。
 * 若会话列表未加载，先拉取一次。
 */
const goConversation = async () => {
  const convId = plan.value?.conversation_id
  if (!convId) {
    ElMessage.warning('该行程未关联会话，无法返回对话')
    return
  }
  try {
    // 确保会话列表已加载
    if (!convStore.conversations.length) {
      await convStore.fetchConversations()
    }
    const target = convStore.conversations.find((c) => c.id === convId)
    if (target) {
      await convStore.selectConversation(target)
    }
    router.push('/')
  } catch (err) {
    ElMessage.error(err.message || '跳转对话失败')
  }
}

/**
 * 删除当前攻略（二次确认）
 */
const handleDelete = () => {
  if (!plan.value) return
  ElMessageBox.confirm(
    `确认删除「${plan.value.destination}」的攻略？此操作不可恢复。`,
    '删除确认',
    {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )
    .then(async () => {
      deleting.value = true
      try {
        await travelStore.remove(route.params.id)
        ElMessage.success('删除成功')
        router.push('/travel/list')
      } catch (err) {
        ElMessage.error(err.message || '删除失败')
      } finally {
        deleting.value = false
      }
    })
    .catch(() => {})
}

onMounted(() => {
  const id = route.params.id
  if (!id) {
    ElMessage.error('攻略 ID 不存在')
    goBack()
    return
  }
  travelStore.fetchDetail(id).catch((err) => {
    ElMessage.error(err.message || '获取详情失败')
  })
})
</script>

<style scoped>
.travel-detail-page {
  max-width: 1000px;
  margin: 0 auto;
}

/* 顶部操作栏 */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-6);
}

.back-btn {
  height: 36px;
  border-radius: var(--radius-md);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.detail-alert {
  margin-bottom: var(--space-5);
}

/* 详情内容 */
.detail-content {
  margin-top: var(--space-2);
}

.result-header {
  display: flex;
  align-items: baseline;
  gap: 14px;
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}

.result-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
}

.result-date {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

/* 行程概要 */
.plan-overview {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  padding: 16px 20px;
  background-color: var(--color-border-light);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
}

.overview-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.overview-label {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.overview-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

/* 偏好标签行 */
.prefs-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: var(--space-4);
}

.prefs-label {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

/* 时段块 */
.period-block {
  padding: 10px 0;
  border-top: 1px dashed var(--color-border-light);
}

.period-block:first-of-type {
  border-top: none;
  padding-top: 0;
}

.period-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.period-tag {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  flex-shrink: 0;
}

.period-tag.morning {
  background-color: #fff3e0;
  color: #e65100;
}

.period-tag.afternoon {
  background-color: #e3f2fd;
  color: #1565c0;
}

.period-tag.evening {
  background-color: #f3e5f5;
  color: #7b1fa2;
}

.period-activity {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.period-meta {
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-left: 48px;
  margin-top: 2px;
}

.period-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-left: 48px;
  margin-top: 4px;
}

/* 餐饮网格 */
.meals-grid {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: var(--space-6) 0 var(--space-3);
  padding-left: 10px;
  border-left: 3px solid var(--color-primary);
}

/* 每日行程卡片 */
.days-list,
.luggage-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.day-card,
.luggage-card {
  border: 1px solid var(--color-border-light) !important;
}

.day-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.day-tag {
  background-color: var(--color-primary-bg);
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: var(--radius-sm);
}

.day-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.luggage-head {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-primary-dark);
  margin-bottom: 10px;
}

.day-section {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 13px;
  margin-top: 6px;
}

.day-section .label {
  color: var(--color-text-tertiary);
  flex-shrink: 0;
  width: 36px;
}

.day-section .text {
  color: var(--color-text-secondary);
}

.bullet-list {
  margin: 0;
  padding-left: 18px;
  color: var(--color-text-secondary);
}

.bullet-list li {
  line-height: 1.8;
}
</style>
