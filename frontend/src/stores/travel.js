import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as travelApi from '@/api/travel'

/**
 * 旅行攻略状态管理
 */
export const useTravelStore = defineStore('travel', () => {
  // 当前生成或查看的攻略
  const currentPlan = ref(null)
  // 攻略列表
  const travelList = ref([])
  // 分页与状态
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(10)
  const loading = ref(false)
  const error = ref(null)

  /**
   * 生成旅行攻略
   * @param {String} destination - 旅行目的地
   * @param {String} startDate - 开始日期
   * @param {String} endDate - 结束日期
   */
  const generate = async (destination, startDate, endDate) => {
    loading.value = true
    error.value = null
    try {
      const result = await travelApi.generateTravelPlan({ destination, startDate, endDate })
      currentPlan.value = result
      return result
    } catch (err) {
      error.value = err.message || '生成攻略失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 查询攻略列表
   * @param {Number} page - 当前页码
   * @param {Number} pageSize - 每页条数
   */
  const fetchList = async (p = 1, size = pageSize.value) => {
    loading.value = true
    error.value = null
    try {
      const result = await travelApi.getTravelList({ page: p, pageSize: size })
      // 兼容 list / travels 两种返回字段
      travelList.value = result.list || result.travels || result.records || []
      total.value = result.total ?? result.pagination?.total ?? 0
      page.value = result.page ?? p
      pageSize.value = result.pageSize ?? size
      return result
    } catch (err) {
      error.value = err.message || '获取攻略列表失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 查询单条攻略详情
   * @param {String} id - 攻略 ID
   */
  const fetchDetail = async (id) => {
    loading.value = true
    error.value = null
    try {
      const result = await travelApi.getTravelDetail(id)
      currentPlan.value = result
      return result
    } catch (err) {
      error.value = err.message || '获取攻略详情失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 删除一条攻略
   * @param {String} id - 攻略 ID
   */
  const remove = async (id) => {
    loading.value = true
    error.value = null
    try {
      await travelApi.deleteTravelPlan(id)
      return true
    } catch (err) {
      error.value = err.message || '删除攻略失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    currentPlan,
    travelList,
    total,
    page,
    pageSize,
    loading,
    error,
    generate,
    fetchList,
    fetchDetail,
    remove
  }
})
