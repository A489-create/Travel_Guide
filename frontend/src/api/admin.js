import api from './request'

/**
 * 管理后台相关 API（需管理员权限）
 */

// ===== 用户管理 =====

/**
 * 分页查询用户列表（支持筛选）
 * @param {Object} params - { page, pageSize, keyword?, role?, isActive? }
 */
export const listUsers = (params) => {
  return api.get('/admin/users', { params })
}

/**
 * 修改用户角色
 * @param {number} userId - 目标用户 ID
 * @param {Object} data - { role: 'admin' | 'user' }
 */
export const updateUserRole = (userId, data) => {
  return api.patch(`/admin/users/${userId}/role`, data)
}

/**
 * 启用/禁用用户
 * @param {number} userId - 目标用户 ID
 * @param {Object} data - { isActive: boolean }
 */
export const updateUserStatus = (userId, data) => {
  return api.patch(`/admin/users/${userId}/status`, data)
}

/**
 * 删除用户（硬删除 + 级联清理个人数据）
 * @param {number} userId - 目标用户 ID
 */
export const deleteUser = (userId) => {
  return api.delete(`/admin/users/${userId}`)
}

/**
 * 查询用户统计信息
 * @param {number} userId - 目标用户 ID
 */
export const getUserStats = (userId) => {
  return api.get(`/admin/users/${userId}/stats`)
}

/**
 * 重置用户密码
 * @param {number} userId - 目标用户 ID
 * @param {Object} data - { newPassword: string }
 */
export const resetUserPassword = (userId, data) => {
  return api.post(`/admin/users/${userId}/reset-password`, data)
}

// ===== 系统知识库管理 =====

/**
 * 生成系统知识
 * @param {Object} data - { destination, types? }
 */
export const generateSystemKnowledge = (data) => {
  return api.post('/admin/knowledge/generate', data)
}

/**
 * 系统知识列表（含已禁用）
 * @param {Object} params - { destination?, type?, page, pageSize }
 */
export const listSystemKnowledge = (params) => {
  return api.get('/admin/knowledge', { params })
}

/**
 * 系统知识详情
 * @param {number} entryId - 条目 ID
 */
export const getSystemKnowledge = (entryId) => {
  return api.get(`/admin/knowledge/${entryId}`)
}

/**
 * 修改系统知识条目
 * @param {number} entryId - 条目 ID
 * @param {Object} data - { title?, content?, summary?, metadata?, enabled? }
 */
export const updateSystemKnowledge = (entryId, data) => {
  return api.patch(`/admin/knowledge/${entryId}`, data)
}

/**
 * 删除系统知识条目（软删除）
 * @param {number} entryId - 条目 ID
 */
export const deleteSystemKnowledge = (entryId) => {
  return api.delete(`/admin/knowledge/${entryId}`)
}

/**
 * 查询系统生成任务状态
 * @param {number} taskId - 任务 ID
 */
export const getSystemTask = (taskId) => {
  return api.get(`/admin/knowledge/tasks/${taskId}`)
}
