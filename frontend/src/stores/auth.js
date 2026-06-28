import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authApi from '@/api/auth'
import { getAccessToken, clearTokens } from '@/utils/tokenStorage'

/**
 * 认证状态管理
 */
export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const isLoggedIn = ref(false)

  /**
   * 是否为管理员（含系统管理员）
   */
  const isAdmin = computed(() => user.value?.role === 'admin' || user.value?.role === 'super_admin')

  /**
   * 是否为系统管理员
   */
  const isSuperAdmin = computed(() => user.value?.role === 'super_admin')

  /**
   * 用户登录
   */
  const login = async (credentials) => {
    try {
      const userData = await authApi.login(credentials)
      user.value = userData
      isLoggedIn.value = true
      return userData
    } catch (error) {
      throw error
    }
  }

  /**
   * 用户注册
   */
  const register = async (data) => {
    try {
      const userData = await authApi.register(data)
      return userData
    } catch (error) {
      throw error
    }
  }

  /**
   * 管理员注册（需邀请码）
   */
  const registerAdmin = async (data) => {
    try {
      const userData = await authApi.registerAdmin(data)
      return userData
    } catch (error) {
      throw error
    }
  }

  /**
   * 用户登出
   */
  const logout = async () => {
    try {
      await authApi.logout()
      user.value = null
      isLoggedIn.value = false
    } catch (error) {
      // 即使 API 失败，也清除本地状态
      clearTokens()
      user.value = null
      isLoggedIn.value = false
    }
  }

  /**
   * 获取当前用户信息
   */
  const fetchCurrentUser = async () => {
    try {
      const userData = await authApi.getCurrentUser()
      user.value = userData
      isLoggedIn.value = true
      return userData
    } catch (error) {
      isLoggedIn.value = false
      throw error
    }
  }

  /**
   * 检查登录状态
   */
  const checkAuth = async () => {
    const token = getAccessToken()
    if (token) {
      try {
        await fetchCurrentUser()
      } catch (error) {
        isLoggedIn.value = false
      }
    } else {
      isLoggedIn.value = false
    }
  }

  return {
    user,
    isLoggedIn,
    isAdmin,
    isSuperAdmin,
    login,
    register,
    registerAdmin,
    logout,
    fetchCurrentUser,
    checkAuth
  }
})