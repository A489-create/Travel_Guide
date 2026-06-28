import api from './request'
import { setTokens, clearTokens, getRefreshToken } from '@/utils/tokenStorage'

/**
 * 认证相关 API
 */

/**
 * 用户注册
 * @param {Object} data - 注册数据 { phone, username, password, name }
 */
export const register = (data) => {
  return api.post('/auth/register', data)
}

/**
 * 管理员注册（需邀请码）
 * @param {Object} data - 注册数据 { phone, username, password, name, inviteCode }
 */
export const registerAdmin = (data) => {
  return api.post('/auth/register-admin', data)
}

/**
 * 用户登录
 * @param {Object} data - 登录数据 { phone, password }
 */
export const login = async (data) => {
  const response = await api.post('/auth/login', data)
  // 登录成功后保存 Token（双写 sessionStorage + localStorage 缓存）
  setTokens(response.accessToken, response.refreshToken)
  return response.user
}

/**
 * 刷新 Token
 */
export const refreshToken = async () => {
  const refreshTokenValue = getRefreshToken()
  const response = await api.post('/auth/refresh-token', {
    refreshToken: refreshTokenValue
  })
  setTokens(response.accessToken, response.refreshToken)
  return response
}

/**
 * 用户登出
 */
export const logout = async () => {
  await api.post('/auth/logout')
  clearTokens()
}

/**
 * 获取当前用户信息
 */
export const getCurrentUser = () => {
  return api.get('/auth/me')
}

/**
 * 修改密码
 * @param {Object} data - { oldPassword, newPassword }
 */
export const changePassword = (data) => {
  return api.put('/auth/change-password', data)
}