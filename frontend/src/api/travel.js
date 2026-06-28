import api from './request'

/**
 * 旅行攻略相关 API
 */

/**
 * 生成旅行攻略
 * @param {Object} data - 攻略数据 { destination, startDate, endDate }
 */
export const generateTravelPlan = (data) => {
  return api.post('/travel', data)
}

/**
 * 查询攻略列表（支持分页）
 * @param {Object} params - 查询参数 { page, pageSize }
 */
export const getTravelList = (params) => {
  return api.get('/travel', { params })
}

/**
 * 查询单条攻略详情
 * @param {String} id - 攻略 ID
 */
export const getTravelDetail = (id) => {
  return api.get(`/travel/${id}`)
}

/**
 * 删除一条攻略
 * @param {String} id - 攻略 ID
 */
export const deleteTravelPlan = (id) => {
  return api.delete(`/travel/${id}`)
}

/**
 * 更新攻略（全量覆盖可变字段，未传字段保留原值）
 * @param {Number} id - 攻略 ID
 * @param {Object} data - 待更新字段 { title?, days?, budget?, preferences?, days_plan?, luggage? }
 */
export const updateTravelPlan = (id, data) => {
  return api.put(`/travel/${id}`, data)
}
