<template>
  <div class="admin-knowledge">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h2>系统知识库</h2>
        <p class="page-desc">管理系统级知识条目，所有用户可见</p>
      </div>
      <el-button type="primary" @click="showGenerateDialog = true">
        <el-icon><Plus /></el-icon>
        生成知识
      </el-button>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-input
        v-model="filterDestination"
        placeholder="按目的地筛选"
        clearable
        style="width: 200px"
        @clear="fetchEntries"
        @keyup.enter="fetchEntries"
      />
      <el-select v-model="filterType" placeholder="类型" clearable style="width: 140px" @change="fetchEntries">
        <el-option label="景点" value="attraction" />
        <el-option label="美食" value="food" />
        <el-option label="避坑指南" value="tip" />
      </el-select>
      <el-button @click="fetchEntries">查询</el-button>
    </div>

    <!-- 知识列表 -->
    <el-table
      :data="entries"
      v-loading="loading"
      class="knowledge-table"
      stripe
    >
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="destination" label="目的地" width="100" />
      <el-table-column prop="type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="typeTagMap[row.type]" size="small">{{ typeLabelMap[row.type] || row.type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
      <el-table-column prop="summary" label="摘要" min-width="250" show-overflow-tooltip />
      <el-table-column prop="enabled" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
            {{ row.enabled ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="source" label="来源" width="80">
        <template #default="{ row }">
          {{ row.source === 'ai' ? 'AI' : '手动' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button
            :type="row.enabled ? 'warning' : 'success'"
            link
            size="small"
            @click="handleToggleEnabled(row)"
          >
            {{ row.enabled ? '禁用' : '启用' }}
          </el-button>
          <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination-wrapper">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchEntries"
        @current-change="fetchEntries"
      />
    </div>

    <!-- 生成知识弹窗 -->
    <el-dialog v-model="showGenerateDialog" title="生成系统知识" width="460px" :close-on-click-modal="false">
      <el-form :model="generateForm" label-width="80px">
        <el-form-item label="目的地">
          <el-input v-model="generateForm.destination" placeholder="如：东京" />
        </el-form-item>
        <el-form-item label="类型">
          <el-checkbox-group v-model="generateForm.types">
            <el-checkbox label="attraction">景点</el-checkbox>
            <el-checkbox label="food">美食</el-checkbox>
            <el-checkbox label="tip">避坑指南</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGenerateDialog = false">取消</el-button>
        <el-button type="primary" :loading="generating" @click="handleGenerate">开始生成</el-button>
      </template>
    </el-dialog>

    <!-- 编辑条目弹窗 -->
    <el-dialog v-model="editDialogVisible" title="编辑知识条目" width="560px" :close-on-click-modal="false">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="标题">
          <el-input v-model="editForm.title" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="editForm.summary" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="editForm.content" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="editForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSaveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  listSystemKnowledge,
  updateSystemKnowledge,
  deleteSystemKnowledge,
  generateSystemKnowledge,
  getSystemTask
} from '@/api/admin'

const entries = ref([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const filterDestination = ref('')
const filterType = ref('')

const typeLabelMap = { attraction: '景点', food: '美食', tip: '避坑指南' }
const typeTagMap = { attraction: 'primary', food: 'success', tip: 'warning' }

// 生成知识
const showGenerateDialog = ref(false)
const generating = ref(false)
const generateForm = reactive({
  destination: '',
  types: ['attraction', 'food', 'tip']
})

// 编辑条目
const editDialogVisible = ref(false)
const saving = ref(false)
const editForm = reactive({
  id: null,
  title: '',
  summary: '',
  content: '',
  enabled: true
})

/**
 * 获取系统知识列表
 */
const fetchEntries = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      pageSize: pageSize.value
    }
    if (filterDestination.value) params.destination = filterDestination.value
    if (filterType.value) params.type = filterType.value
    const res = await listSystemKnowledge(params)
    entries.value = res.list || []
    total.value = res.total || 0
  } catch (error) {
    ElMessage.error(error.message || '获取知识列表失败')
  } finally {
    loading.value = false
  }
}

/**
 * 触发生成知识
 */
const handleGenerate = async () => {
  if (!generateForm.destination.trim()) {
    ElMessage.warning('请输入目的地')
    return
  }
  generating.value = true
  try {
    const res = await generateSystemKnowledge({
      destination: generateForm.destination.trim(),
      types: generateForm.types.length > 0 ? generateForm.types : undefined
    })
    const taskId = res.taskId
    ElMessage.success('生成任务已创建，正在后台执行...')
    showGenerateDialog.value = false
    generateForm.destination = ''

    // 轮询任务状态
    if (taskId) {
      pollTask(taskId)
    }
  } catch (error) {
    ElMessage.error(error.message || '创建生成任务失败')
  } finally {
    generating.value = false
  }
}

/**
 * 轮询生成任务状态
 */
const pollTask = async (taskId) => {
  const poll = async () => {
    try {
      const res = await getSystemTask(taskId)
      if (res.status === 'completed' || res.status === 'failed') {
        if (res.status === 'completed') {
          ElMessage.success(`知识生成完成：成功 ${res.success} 条，失败 ${res.failed} 条`)
        } else {
          ElMessage.error(`知识生成失败：${res.errorMsg || '未知错误'}`)
        }
        fetchEntries()
        return
      }
      // 继续轮询
      setTimeout(poll, 3000)
    } catch {
      // 轮询异常，停止
    }
  }
  setTimeout(poll, 3000)
}

/**
 * 编辑条目
 */
const handleEdit = (row) => {
  editForm.id = row.id
  editForm.title = row.title
  editForm.summary = row.summary || ''
  editForm.content = row.content
  editForm.enabled = row.enabled
  editDialogVisible.value = true
}

/**
 * 保存编辑
 */
const handleSaveEdit = async () => {
  saving.value = true
  try {
    const data = {
      title: editForm.title,
      summary: editForm.summary,
      content: editForm.content,
      enabled: editForm.enabled
    }
    await updateSystemKnowledge(editForm.id, data)
    ElMessage.success('保存成功')
    editDialogVisible.value = false
    fetchEntries()
  } catch (error) {
    ElMessage.error(error.message || '保存失败')
  } finally {
    saving.value = false
  }
}

/**
 * 切换启用/禁用
 */
const handleToggleEnabled = async (row) => {
  const action = row.enabled ? '禁用' : '启用'
  try {
    await updateSystemKnowledge(row.id, { enabled: !row.enabled })
    ElMessage.success(`${action}成功`)
    fetchEntries()
  } catch (error) {
    ElMessage.error(error.message || '操作失败')
  }
}

/**
 * 删除条目（软删除）
 */
const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除「${row.title}」？此操作为软删除，可恢复。`, '确认删除', { type: 'warning' })
    await deleteSystemKnowledge(row.id)
    ElMessage.success('删除成功')
    fetchEntries()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

onMounted(() => {
  fetchEntries()
})
</script>

<style scoped>
.admin-knowledge {
  max-width: 1200px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 4px;
}

.page-desc {
  font-size: 13px;
  color: var(--color-text-tertiary);
  margin: 0;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}

.knowledge-table {
  border-radius: 8px;
  overflow: hidden;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
