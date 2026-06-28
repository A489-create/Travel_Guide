import api from './request'

/**
 * 知识库模块 API
 * 包含条目浏览、语义检索、触发生成、任务状态查询
 */

/**
 * 获取知识库条目列表（分页，可按目的地/类型过滤）
 * @param {Object} params - { destination?, type?, page, page_size }
 */
export const getKnowledgeList = (params) => {
  return api.get('/knowledge', { params })
}

/**
 * 获取知识条目详情
 * @param {Number} id - 条目 ID
 */
export const getKnowledgeDetail = (id) => {
  return api.get(`/knowledge/${id}`)
}

/**
 * 向量语义检索
 * @param {Object} data - { query, destination, type?, topK? }
 */
export const searchKnowledge = (data) => {
  return api.post('/knowledge/search', data)
}

/**
 * 触发 AI 生成知识库（异步任务）
 * @param {Object} data - { destination, types? }
 * @returns {Promise<{taskId: Number}>}
 */
export const generateKnowledge = (data) => {
  return api.post('/knowledge/generate', data)
}

/**
 * 查询生成任务状态
 * @param {Number} taskId - 任务 ID
 */
export const getTaskStatus = (taskId) => {
  return api.get(`/knowledge/tasks/${taskId}`)
}
