<template>
  <div class="admin-users">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h2>用户管理</h2>
        <p class="page-desc">查看与管理系统中的所有用户</p>
      </div>
    </div>

    <!-- 用户/管理员标签页 -->
    <el-tabs v-model="activeTab" class="user-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="用户" name="user" />
      <el-tab-pane label="管理员" name="admin" />
    </el-tabs>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-input
        v-model="filterKeyword"
        placeholder="搜索用户名/姓名/手机号"
        clearable
        style="width: 240px"
        @clear="handleSearch"
        @keyup.enter="handleSearch"
      />
      <el-select
        v-model="filterStatus"
        placeholder="状态"
        clearable
        style="width: 120px"
        @change="handleSearch"
      >
        <el-option label="正常" :value="true" />
        <el-option label="已禁用" :value="false" />
      </el-select>
      <el-button type="primary" @click="handleSearch">查询</el-button>
      <el-button @click="handleResetFilter">重置</el-button>
    </div>

    <!-- 用户列表 -->
    <el-table
      :data="users"
      v-loading="loading"
      class="user-table"
      stripe
    >
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="name" label="姓名" width="120" />
      <el-table-column prop="phone" label="手机号" width="140" />
      <el-table-column prop="role" label="角色" width="110">
        <template #default="{ row }">
          <el-tag :type="roleTagType(row.role)" size="small">
            {{ roleLabel(row.role) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="isActive" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.isActive ? 'success' : 'warning'" size="small">
            {{ row.isActive ? '正常' : '已禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" label="注册时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.createdAt) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="340" fixed="right">
        <template #default="{ row }">
          <div class="action-cell">
            <!-- 角色操作组（仅可管理时显示） -->
            <span v-if="canManageRow(row)" class="action-group">
              <el-button
                v-if="row.role === 'user'"
                type="primary"
                link
                size="small"
                @click="handleSetAdmin(row)"
              >
                设为管理员
              </el-button>
              <el-button
                v-if="row.role === 'admin'"
                type="info"
                link
                size="small"
                @click="handleSetUser(row)"
              >
                设为用户
              </el-button>
            </span>
            <!-- 状态操作组（仅可管理时显示） -->
            <span v-if="canManageRow(row)" class="action-group">
              <el-button
                v-if="row.isActive"
                type="warning"
                link
                size="small"
                @click="handleToggleStatus(row, false)"
              >
                禁用
              </el-button>
              <el-button
                v-if="!row.isActive"
                type="success"
                link
                size="small"
                @click="handleToggleStatus(row, true)"
              >
                启用
              </el-button>
            </span>
            <!-- 管理操作组 -->
            <span class="action-group">
              <el-button
                type="primary"
                link
                size="small"
                @click="handleViewDetail(row)"
              >
                详情
              </el-button>
              <el-button
                v-if="canManageRow(row)"
                type="warning"
                link
                size="small"
                @click="handleResetPassword(row)"
              >
                重置密码
              </el-button>
              <el-button
                v-if="canManageRow(row)"
                type="danger"
                link
                size="small"
                @click="handleDelete(row)"
              >
                删除
              </el-button>
            </span>
          </div>
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
        @size-change="fetchUsers"
        @current-change="fetchUsers"
      />
    </div>

    <!-- 用户详情弹窗 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="用户详情"
      width="520px"
      :close-on-click-modal="true"
    >
      <div v-if="detailData" class="detail-container">
        <!-- 基本信息 -->
        <div class="detail-section">
          <div class="detail-section-title">基本信息</div>
          <div class="detail-grid">
            <div class="detail-item">
              <span class="detail-label">ID</span>
              <span class="detail-value">{{ detailData.user.id }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">用户名</span>
              <span class="detail-value">{{ detailData.user.username }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">姓名</span>
              <span class="detail-value">{{ detailData.user.name }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">手机号</span>
              <span class="detail-value">{{ detailData.user.phone }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">角色</span>
              <el-tag :type="roleTagType(detailData.user.role)" size="small">
                {{ roleLabel(detailData.user.role) }}
              </el-tag>
            </div>
            <div class="detail-item">
              <span class="detail-label">状态</span>
              <el-tag :type="detailData.user.isActive ? 'success' : 'warning'" size="small">
                {{ detailData.user.isActive ? '正常' : '已禁用' }}
              </el-tag>
            </div>
            <div class="detail-item">
              <span class="detail-label">注册时间</span>
              <span class="detail-value">{{ formatDate(detailData.user.createdAt) }}</span>
            </div>
          </div>
        </div>

        <!-- 资源统计 -->
        <div class="detail-section">
          <div class="detail-section-title">资源统计</div>
          <div class="stats-grid">
            <div class="stat-card">
              <div class="stat-value">{{ detailData.stats.knowledgeCount }}</div>
              <div class="stat-label">知识条目</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{{ detailData.stats.conversationCount }}</div>
              <div class="stat-label">会话数</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{{ detailData.stats.travelPlanCount }}</div>
              <div class="stat-label">行程数</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{{ detailData.stats.messageCount }}</div>
              <div class="stat-label">消息数</div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 重置密码弹窗 -->
    <el-dialog
      v-model="resetPwdDialogVisible"
      title="重置用户密码"
      width="420px"
      :close-on-click-modal="false"
    >
      <div class="reset-pwd-tip">
        将重置用户「<strong>{{ resetPwdTarget?.name }}</strong>」的密码，重置后该用户需使用新密码重新登录。
      </div>
      <el-form :model="resetPwdForm" label-width="80px" style="margin-top: 16px">
        <el-form-item label="新密码">
          <el-input
            v-model="resetPwdForm.newPassword"
            type="password"
            show-password
            placeholder="请输入新密码（至少 6 位）"
          />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input
            v-model="resetPwdForm.confirmPassword"
            type="password"
            show-password
            placeholder="请再次输入新密码"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPwdDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetting" @click="handleSaveResetPassword">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listUsers, updateUserRole, updateUserStatus, deleteUser, getUserStats, resetUserPassword } from '@/api/admin'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const users = ref([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 标签页：默认展示用户
const activeTab = ref('user')
// 筛选
const filterKeyword = ref('')
const filterRole = ref('user')
const filterStatus = ref('')

/**
 * 角色标签文本
 */
const roleLabel = (role) => {
  if (role === 'super_admin') return '系统管理员'
  if (role === 'admin') return '管理员'
  return '用户'
}

/**
 * 角色标签类型
 */
const roleTagType = (role) => {
  if (role === 'super_admin') return 'danger'
  if (role === 'admin') return 'warning'
  return 'info'
}

/**
 * 判断当前登录用户是否可管理该行用户
 * super_admin 不可管理 super_admin；admin 仅可管理 user
 */
const canManageRow = (row) => {
  // 系统管理员不可被任何人通过界面操作（含自己）
  if (row.role === 'super_admin') return false
  // 系统管理员可管理 admin 与 user
  if (authStore.isSuperAdmin) return true
  // 普通管理员仅可管理 user
  if (authStore.isAdmin) return row.role === 'user'
  return false
}

// 用户详情
const detailDialogVisible = ref(false)
const detailData = ref(null)

// 重置密码
const resetPwdDialogVisible = ref(false)
const resetPwdTarget = ref(null)
const resetting = ref(false)
const resetPwdForm = reactive({
  newPassword: '',
  confirmPassword: ''
})

/**
 * 获取用户列表
 */
const fetchUsers = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      pageSize: pageSize.value
    }
    if (filterKeyword.value) params.keyword = filterKeyword.value
    if (filterRole.value) params.role = filterRole.value
    if (filterStatus.value !== '' && filterStatus.value !== null) params.isActive = filterStatus.value
    const res = await listUsers(params)
    users.value = res.list || []
    total.value = res.total || 0
  } catch (error) {
    ElMessage.error(error.message || '获取用户列表失败')
  } finally {
    loading.value = false
  }
}

/**
 * 格式化日期
 */
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

/**
 * 点击查询
 */
const handleSearch = () => {
  currentPage.value = 1
  fetchUsers()
}

/**
 * 切换用户/管理员标签页
 */
const handleTabChange = (tabName) => {
  activeTab.value = tabName
  filterRole.value = tabName
  currentPage.value = 1
  fetchUsers()
}

/**
 * 重置筛选条件
 */
const handleResetFilter = () => {
  filterKeyword.value = ''
  filterStatus.value = ''
  activeTab.value = 'user'
  filterRole.value = 'user'
  currentPage.value = 1
  fetchUsers()
}

/**
 * 设为管理员
 */
const handleSetAdmin = async (row) => {
  try {
    await ElMessageBox.confirm(`确定将用户「${row.name}」设为管理员？`, '确认', { type: 'warning' })
    await updateUserRole(row.id, { role: 'admin' })
    ElMessage.success('角色修改成功')
    fetchUsers()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '修改失败')
  }
}

/**
 * 设为普通用户
 */
const handleSetUser = async (row) => {
  try {
    await ElMessageBox.confirm(`确定将管理员「${row.name}」降级为普通用户？`, '确认', { type: 'warning' })
    await updateUserRole(row.id, { role: 'user' })
    ElMessage.success('角色修改成功')
    fetchUsers()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '修改失败')
  }
}

/**
 * 启用/禁用用户
 */
const handleToggleStatus = async (row, isActive) => {
  const action = isActive ? '启用' : '禁用'
  const tip = isActive
    ? `确定启用用户「${row.name}」？`
    : `确定禁用用户「${row.name}」？禁用后该用户将立即失去访问权限，无法登录和使用系统。`
  try {
    await ElMessageBox.confirm(tip, '确认', { type: 'warning' })
    await updateUserStatus(row.id, { isActive })
    ElMessage.success(`${action}成功`)
    fetchUsers()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '操作失败')
  }
}

/**
 * 查看用户详情（含统计）
 */
const handleViewDetail = async (row) => {
  try {
    const stats = await getUserStats(row.id)
    detailData.value = {
      user: row,
      stats
    }
    detailDialogVisible.value = true
  } catch (error) {
    ElMessage.error(error.message || '获取详情失败')
  }
}

/**
 * 打开重置密码弹窗
 */
const handleResetPassword = (row) => {
  resetPwdTarget.value = row
  resetPwdForm.newPassword = ''
  resetPwdForm.confirmPassword = ''
  resetPwdDialogVisible.value = true
}

/**
 * 确认重置密码
 */
const handleSaveResetPassword = async () => {
  if (!resetPwdForm.newPassword) {
    ElMessage.warning('请输入新密码')
    return
  }
  if (resetPwdForm.newPassword.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }
  if (resetPwdForm.newPassword !== resetPwdForm.confirmPassword) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  resetting.value = true
  try {
    await resetUserPassword(resetPwdTarget.value.id, { newPassword: resetPwdForm.newPassword })
    ElMessage.success('密码重置成功，用户需使用新密码重新登录')
    resetPwdDialogVisible.value = false
  } catch (error) {
    ElMessage.error(error.message || '重置失败')
  } finally {
    resetting.value = false
  }
}

/**
 * 删除用户（硬删除 + 级联清理）
 */
const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${row.name}」？该操作不可恢复，将同时删除其所有会话、行程、消息和个人知识库。`,
      '危险操作',
      { type: 'error', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
    await deleteUser(row.id)
    ElMessage.success('用户已删除')
    fetchUsers()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

onMounted(() => {
  fetchUsers()
})
</script>

<style scoped>
.admin-users {
  max-width: 1200px;
}

.page-header {
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

.user-table {
  border-radius: 8px;
  overflow: hidden;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

/* 详情弹窗 */
.detail-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.detail-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border-light);
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 24px;
}

.detail-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.detail-label {
  font-size: 13px;
  color: var(--color-text-tertiary);
  min-width: 60px;
}

.detail-value {
  font-size: 13px;
  color: var(--color-text-primary);
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.stat-card {
  background: var(--color-bg);
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  border: 1px solid var(--color-border-light);
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-primary);
  margin-bottom: 4px;
}

.stat-label {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

/* 用户/管理员标签页 */
.user-tabs {
  margin-bottom: 16px;
}

.user-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}

/* 操作列按钮分组 */
.action-cell {
  display: flex;
  align-items: center;
  gap: 16px;
}

.action-group {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 重置密码提示 */
.reset-pwd-tip {
  font-size: 14px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  background: var(--color-bg);
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid var(--color-border-light);
}
</style>
