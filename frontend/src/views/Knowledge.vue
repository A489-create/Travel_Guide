<template>
  <div class="knowledge-page">
    <!-- 页面标题区 -->
    <div class="page-header">
      <h1 class="page-title">知识库</h1>
      <el-button type="primary" :icon="MagicStick" @click="showGenerateDialog = true">
        生成知识
      </el-button>
    </div>

    <!-- 筛选 + 搜索 -->
    <el-card class="filter-card" shadow="never">
      <div class="filter-row">
        <el-input
          v-model="filters.destination"
          placeholder="目的地（如：东京）"
          :prefix-icon="Location"
          clearable
          class="filter-input"
          @keyup.enter="handleSearch"
        />
        <el-select v-model="filters.type" placeholder="全部类型" clearable class="filter-type">
          <el-option label="景点" value="attraction" />
          <el-option label="美食" value="food" />
          <el-option label="避坑" value="tip" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="handleSearch">筛选</el-button>
      </div>

      <el-divider class="divider" />

      <!-- 语义检索区 -->
      <div class="search-row">
        <el-input
          v-model="searchQuery"
          placeholder="语义检索：输入问题，如「东京有什么好玩的」"
          :prefix-icon="Search"
          clearable
          class="search-input"
          @keyup.enter="handleSemanticSearch"
        />
        <el-button type="success" :loading="searching" @click="handleSemanticSearch">
          语义检索
        </el-button>
      </div>
    </el-card>

    <!-- 列表区域 -->
    <div v-loading="loading" class="list-wrapper">
      <div v-if="entries.length" class="entry-grid">
        <el-card
          v-for="entry in entries"
          :key="entry.id"
          class="entry-card"
          shadow="hover"
          @click="showDetail(entry)"
        >
          <div class="card-top">
            <el-tag :type="typeTagType(entry.type)" size="small" effect="light">
              {{ typeLabel(entry.type) }}
            </el-tag>
            <span class="card-dest">{{ entry.destination }}</span>
          </div>
          <h3 class="card-title">{{ entry.title }}</h3>
          <p class="card-summary" v-if="entry.summary">{{ entry.summary }}</p>
          <p class="card-content">{{ entry.content }}</p>
        </el-card>
      </div>
      <el-empty v-else-if="!loading" description="暂无知识条目，点击「生成知识」添加" />
    </div>

    <!-- 分页 -->
    <div class="pagination-wrapper" v-if="total > 0 && !searchMode">
      <span class="pagination-info">共 {{ total }} 条</span>
      <el-pagination
        background
        layout="prev, pager, next"
        :current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        @current-change="changePage"
      />
    </div>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="知识详情" width="640px" top="6vh">
      <div v-if="currentEntry" class="detail-body">
        <div class="detail-meta">
          <el-tag :type="typeTagType(currentEntry.type)" size="small">
            {{ typeLabel(currentEntry.type) }}
          </el-tag>
          <span class="detail-dest">{{ currentEntry.destination }}</span>
        </div>
        <h2 class="detail-title">{{ currentEntry.title }}</h2>
        <p class="detail-summary" v-if="currentEntry.summary">{{ currentEntry.summary }}</p>
        <div class="detail-content">{{ currentEntry.content }}</div>
        <div v-if="currentEntry.metadata" class="detail-extra">
          <h4>附加信息</h4>
          <ul>
            <li v-for="(val, key) in currentEntry.metadata" :key="key">
              <span class="extra-key">{{ key }}</span>：{{ val }}
            </li>
          </ul>
        </div>
      </div>
    </el-dialog>

    <!-- 生成对话框 -->
    <el-dialog v-model="showGenerateDialog" title="生成知识库" width="480px">
      <el-form label-width="80px">
        <el-form-item label="目的地">
          <el-input v-model="generateForm.destination" placeholder="如：东京" />
        </el-form-item>
        <el-form-item label="类型">
          <el-checkbox-group v-model="generateForm.types">
            <el-checkbox label="attraction">景点</el-checkbox>
            <el-checkbox label="food">美食</el-checkbox>
            <el-checkbox label="tip">避坑</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGenerateDialog = false">取消</el-button>
        <el-button type="primary" :loading="generating" @click="handleGenerate">开始生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Location, Search, MagicStick } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as knowledgeApi from '@/api/knowledge'

const loading = ref(false)
const searching = ref(false)
const generating = ref(false)
const entries = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(12)
const searchMode = ref(false)

// 筛选条件
const filters = reactive({ destination: '', type: '' })
// 语义检索
const searchQuery = ref('')
// 详情弹窗
const detailVisible = ref(false)
const currentEntry = ref(null)
// 生成对话框
const showGenerateDialog = ref(false)
const generateForm = reactive({
  destination: '',
  types: ['attraction', 'food', 'tip']
})

/**
 * 加载知识库列表
 */
const loadList = async (page = 1) => {
  searchMode.value = false
  loading.value = true
  try {
    const result = await knowledgeApi.getKnowledgeList({
      destination: filters.destination || undefined,
      type: filters.type || undefined,
      page,
      page_size: pageSize.value
    })
    entries.value = result.list || []
    total.value = result.total || 0
    currentPage.value = page
  } catch (err) {
    ElMessage.error(err.message || '加载列表失败')
  } finally {
    loading.value = false
  }
}

/**
 * 筛选搜索
 */
const handleSearch = () => {
  loadList(1)
}

/**
 * 语义检索
 */
const handleSemanticSearch = async () => {
  if (!searchQuery.value.trim()) {
    ElMessage.warning('请输入检索内容')
    return
  }
  if (!filters.destination) {
    ElMessage.warning('语义检索需指定目的地')
    return
  }
  searching.value = true
  searchMode.value = true
  try {
    const result = await knowledgeApi.searchKnowledge({
      query: searchQuery.value,
      destination: filters.destination,
      type: filters.type || undefined,
      topK: 10
    })
    entries.value = result || []
    total.value = entries.value.length
  } catch (err) {
    ElMessage.error(err.message || '检索失败')
  } finally {
    searching.value = false
  }
}

/**
 * 切换页码
 */
const changePage = (page) => {
  loadList(page)
}

/**
 * 显示详情
 */
const showDetail = (entry) => {
  currentEntry.value = entry
  detailVisible.value = true
}

/**
 * 触发生成
 */
const handleGenerate = async () => {
  if (!generateForm.destination.trim()) {
    ElMessage.warning('请输入目的地')
    return
  }
  if (!generateForm.types.length) {
    ElMessage.warning('请至少选择一个类型')
    return
  }
  generating.value = true
  try {
    const { taskId } = await knowledgeApi.generateKnowledge({
      destination: generateForm.destination.trim(),
      types: generateForm.types
    })
    ElMessage.success(`任务已创建（ID: ${taskId}），正在后台生成…`)
    showGenerateDialog.value = false
    // 轮询任务状态
    pollTask(taskId)
  } catch (err) {
    ElMessage.error(err.message || '生成失败')
  } finally {
    generating.value = false
  }
}

/**
 * 轮询任务状态，完成后刷新列表
 */
const pollTask = async (taskId) => {
  let times = 0
  const timer = setInterval(async () => {
    times += 1
    try {
      const task = await knowledgeApi.getTaskStatus(taskId)
      if (task.status === 'completed' || task.status === 'failed') {
        clearInterval(timer)
        if (task.status === 'completed') {
          ElMessage.success(`生成完成：成功 ${task.success} 条，失败 ${task.failed} 条`)
          loadList(1)
        } else {
          ElMessage.error(`生成失败：${task.error_msg || '未知错误'}`)
        }
      }
    } catch (_) {
      // 单次查询失败不中断轮询
    }
    // 超时保护：最多轮询 60 次（约 5 分钟）
    if (times >= 60) {
      clearInterval(timer)
      ElMessage.warning('生成超时，请稍后刷新列表查看')
    }
  }, 5000)
}

/**
 * 类型中文名
 */
const typeLabel = (type) => {
  return { attraction: '景点', food: '美食', tip: '避坑' }[type] || type
}

/**
 * 类型对应的标签颜色
 */
const typeTagType = (type) => {
  return { attraction: 'success', food: 'warning', tip: 'danger' }[type] || ''
}

onMounted(() => {
  loadList(1)
})
</script>

<style scoped>
.knowledge-page {
  max-width: 1100px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-5);
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
}

/* 筛选卡片 */
.filter-card {
  margin-bottom: var(--space-5);
  border: 1px solid var(--color-border-light) !important;
}

.filter-row,
.search-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.filter-input {
  max-width: 240px;
}

.filter-type {
  width: 140px;
}

.divider {
  margin: 16px 0;
}

.search-input {
  flex: 1;
}

/* 列表网格 */
.list-wrapper {
  min-height: 200px;
}

.entry-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-4);
}

.entry-card {
  cursor: pointer;
  border: 1px solid var(--color-border-light) !important;
  transition: transform var(--transition-base), box-shadow var(--transition-base);
}

.entry-card:hover {
  transform: translateY(-2px);
}

.card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.card-dest {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 6px;
}

.card-summary {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0 0 8px;
}

.card-content {
  font-size: 13px;
  color: var(--color-text-tertiary);
  line-height: 1.6;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 分页 */
.pagination-wrapper {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border-light);
}

.pagination-info {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

/* 详情弹窗 */
.detail-body {
  padding: 0 4px;
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.detail-dest {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

.detail-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 10px;
}

.detail-summary {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0 0 16px;
  padding-left: 10px;
  border-left: 3px solid var(--color-primary);
}

.detail-content {
  font-size: 14px;
  line-height: 1.8;
  color: var(--color-text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-extra {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border-light);
}

.detail-extra h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 8px;
}

.detail-extra ul {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.extra-key {
  font-weight: 600;
  color: var(--color-text-primary);
}
</style>
