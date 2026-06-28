import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getAccessToken } from '@/utils/tokenStorage'

/**
 * Vue Router 配置
 */

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('@/components/Layout.vue'),
    meta: { requiresAuth: true },
    redirect: '/home',
    children: [
      {
        path: '/home',
        name: 'Home',
        component: () => import('@/views/Home.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: '/travel/list',
        name: 'TravelList',
        component: () => import('@/views/TravelList.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: '/travel/:id',
        name: 'TravelDetail',
        component: () => import('@/views/TravelDetail.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: '/knowledge',
        name: 'Knowledge',
        component: () => import('@/views/Knowledge.vue'),
        meta: { requiresAuth: true }
      },
      // 管理后台路由（仅管理员可访问）
      {
        path: '/admin/users',
        name: 'AdminUsers',
        component: () => import('@/views/AdminUsers.vue'),
        meta: { requiresAuth: true, requiresAdmin: true }
      },
      {
        path: '/admin/knowledge',
        name: 'AdminKnowledge',
        component: () => import('@/views/AdminKnowledge.vue'),
        meta: { requiresAuth: true, requiresAdmin: true }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

/**
 * 路由守卫 - 检查认证状态与角色权限
 */
router.beforeEach(async (to) => {
  const token = getAccessToken()

  if (to.meta.requiresAuth && !token) {
    // 需要认证但未登录，跳转到登录页
    return '/login'
  }

  if (!to.meta.requiresAuth && token && (to.path === '/login' || to.path === '/register')) {
    // 已登录但访问登录/注册页，根据角色跳转：管理员去后台，普通用户去首页
    const authStore = useAuthStore()
    if (!authStore.user) {
      try {
        await authStore.fetchCurrentUser()
      } catch {
        authStore.logout()
        return '/login'
      }
    }
    return authStore.isAdmin ? '/admin/users' : '/home'
  }

  if (to.meta.requiresAdmin) {
    // 需要管理员权限：确保用户信息已加载
    const authStore = useAuthStore()
    if (!authStore.user) {
      try {
        await authStore.fetchCurrentUser()
      } catch {
        authStore.logout()
        return '/login'
      }
    }
    if (!authStore.isAdmin) {
      return '/home'
    }
  }

  return true
})

export default router
