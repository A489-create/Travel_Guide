<template>
  <div class="travel-list-page">
    <!-- 页面标题区 -->
    <div class="page-header">
      <h1 class="page-title">我的攻略</h1>
      <el-button type="primary" :icon="Plus" @click="goCreate" class="create-btn">
        新建攻略
      </el-button>
    </div>

    <!-- 列表区域 -->
    <div v-loading="loading" class="list-wrapper">
      <div v-if="travelList.length" class="card-grid">
        <el-card
          v-for="item in travelList"
          :key="item.id"
          class="travel-card"
          shadow="hover"
        >
          <div class="card-top">
            <div class="card-icon">
              <el-icon :size="20"><Location /></el-icon>
            </div>
            <div class="card-info">
              <h3 class="card-title">{{ item.title || item.destination }}</h3>
              <div class="card-meta">
                <span class="meta-item">
                  <el-icon><Location /></el-icon>
                  {{ item.destination }}
                </span>
                <span class="meta-item" v-if="item.days">
                  <el-icon><Calendar /></el-icon>
                  {{ item.days }} 天
                </span>
                <span class="meta-item" v-if="item.budget">
                  <el-icon><Wallet /></el-icon>
                  ¥{{ item.budget }}
                </span>
              </div>
              <div class="card-prefs" v-if="item.preferences && item.preferences.length">
                <el-tag
                  v-for="pref in item.preferences"
                  :key="pref"
                  size="small"
                  type="info"
                  effect="plain"
                >
                  {{ pref }}
                </el-tag>
              </div>
            </div>
          </div>

          <div class="card-extra">
            <span class="created-time" v-if="item.created_at">
              创建于 {{ formatDate(item.created_at) }}
            </span>
          </div>

          <div class="card-actions">
            <el-button type="primary" size="small" :icon="View" @click="viewDetail(item.id)">
              查看详情
            </el-button>
            <el-button type="danger" size="small" :icon="Delete" @click="handleDelete(item)">
              删除
            </el-button>
          </div>
        </el-card>
      </div>

      <el-empty v-else-if="!loading" description="还没有攻略，快去生成第一个吧">
        <el-button type="primary" @click="goCreate">新建攻略</el-button>
      </el-empty>
    </div>

    <!-- 分页 -->
    <div class="pagination-wrapper" v-if="total > 0">
      <span class="pagination-info">共 {{ total }} 条记录</span>
      <el-pagination
        background
        layout="prev, pager, next"
        :current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        @current-change="changePage"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useTravelStore } from '@/stores/travel'
import { Location, Calendar, View, Delete, Plus, Wallet } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const travelStore = useTravelStore()
const { travelList, total, pageSize, loading } = storeToRefs(travelStore)

const currentPage = ref(1)

/**
 * 加载攻略列表
 */
const loadList = async (page = 1) => {
  currentPage.value = page
  try {
    await travelStore.fetchList(page, pageSize.value)
  } catch (err) {
    ElMessage.error(err.message || '加载列表失败')
  }
}

/**
 * 切换页码
 */
const changePage = (page) => {
  loadList(page)
}

/**
 * 查看详情
 */
const viewDetail = (id) => {
  router.push(`/travel/${id}`)
}

/**
 * 跳转到新建攻略（首页）
 */
const goCreate = () => {
  router.push('/home')
}

/**
 * 删除攻略（二次确认）
 */
const handleDelete = (item) => {
  ElMessageBox.confirm(
    `确认删除「${item.destination}」的攻略？此操作不可恢复。`,
    '删除确认',
    {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )
    .then(async () => {
      try {
        await travelStore.remove(item.id)
        ElMessage.success('删除成功')
        // 删除后若当前页已无数据且非第一页，回退一页
        if (travelList.value.length === 0 && currentPage.value > 1) {
          loadList(currentPage.value - 1)
        } else {
          loadList(currentPage.value)
        }
      } catch (err) {
        ElMessage.error(err.message || '删除失败')
      }
    })
    .catch(() => {})
}

/**
 * 格式化创建时间（仅保留日期部分）
 */
const formatDate = (value) => {
  if (!value) return ''
  return String(value).slice(0, 10)
}

onMounted(() => {
  loadList()
})

/**
 * 页面从其他页签切回时刷新列表，避免 stale 数据
 */
onActivated(() => {
  loadList(currentPage.value)
})
</script>

<style scoped>
.travel-list-page {
  max-width: 1100px;
  margin: 0 auto;
}

/* 页面标题区 */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-6);
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
}

.create-btn {
  height: 36px;
  padding: 0 20px;
  font-weight: 500;
  border-radius: var(--radius-md);
  flex-shrink: 0;
}

/* 卡片网格 */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--space-4);
}

.travel-card {
  border: 1px solid var(--color-border-light) !important;
  transition: transform var(--transition-base), box-shadow var(--transition-base);
}

.travel-card:hover {
  transform: translateY(-2px);
}

.card-top {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background-color: var(--color-primary-bg);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.card-info {
  flex: 1;
  min-width: 0;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.card-prefs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.card-extra {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--color-border-light);
}

.created-time {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.card-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

/* 分页 */
.pagination-wrapper {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--space-6);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border-light);
}

.pagination-info {
  font-size: 13px;
  color: var(--color-text-tertiary);
}
</style>
