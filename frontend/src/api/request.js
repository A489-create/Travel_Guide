import axios from 'axios'
import { getAccessToken, getRefreshToken, setTokens, clearTokens } from '@/utils/tokenStorage'

/**
 * Axios 请求封装
 * 配置基础 URL、拦截器等
 */

// 创建 axios 实例
const api = axios.create({
  baseURL: '/api', // 使用 Vite 代理
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器 - 添加 JWT Token
api.interceptors.request.use(
  (config) => {
    const token = getAccessToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器 - 处理响应和错误
api.interceptors.response.use(
  (response) => {
    // 直接返回 data 字段（符合后端统一响应格式）
    return response.data.data
  },
  async (error) => {
    // 401 错误 - Token 过期或无效
    if (error.response && error.response.status === 401) {
      // 尝试刷新 Token
      const refreshToken = getRefreshToken()
      if (refreshToken && !error.config._retry) {
        error.config._retry = true
        try {
          const response = await axios.post('/api/auth/refresh-token', {
            refreshToken
          })
          const { accessToken, refreshToken: newRefreshToken } = response.data.data

          // 保存新的 Token（双写 sessionStorage + localStorage）
          setTokens(accessToken, newRefreshToken)

          // 重试原请求
          error.config.headers.Authorization = `Bearer ${accessToken}`
          return api(error.config)
        } catch (refreshError) {
          // 刷新失败，清除 Token 并跳转到登录页
          clearTokens()
          window.location.href = '/login'
          return Promise.reject(refreshError)
        }
      }
    }
    
    // 返回错误信息
    const message = error.response?.data?.message || '请求失败'
    return Promise.reject(new Error(message))
  }
)

export default api