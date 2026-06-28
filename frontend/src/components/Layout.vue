<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
    <el-aside width="240px" class="sidebar">
      <div class="logo">
        <div class="logo-icon">
          <el-icon :size="22"><Compass /></el-icon>
        </div>
        <span class="logo-text">旅行攻略</span>
      </div>

      <div class="sidebar-nav">
        <el-menu
          :default-active="activeMenu"
          class="sidebar-menu"
          router
          background-color="transparent"
          text-color="var(--sidebar-text)"
          active-text-color="var(--sidebar-text-active)"
        >
          <!-- 管理员：仅显示管理后台菜单 -->
          <template v-if="authStore.isAdmin">
            <div class="menu-group-label">管理后台</div>
            <el-menu-item index="/admin/users" class="menu-item">
              <el-icon><UserFilled /></el-icon>
              <span>用户管理</span>
            </el-menu-item>
            <el-menu-item index="/admin/knowledge" class="menu-item">
              <el-icon><Document /></el-icon>
              <span>系统知识库</span>
            </el-menu-item>
          </template>

          <!-- 普通用户：显示业务菜单 -->
          <template v-else>
            <el-menu-item index="/home" class="menu-item">
              <el-icon><HomeFilled /></el-icon>
              <span>首页</span>
            </el-menu-item>
            <el-menu-item index="/knowledge" class="menu-item">
              <el-icon><Reading /></el-icon>
              <span>知识库</span>
            </el-menu-item>
            <el-menu-item index="/travel/list" class="menu-item">
              <el-icon><Tickets /></el-icon>
              <span>我的攻略</span>
            </el-menu-item>
          </template>
        </el-menu>
      </div>

    </el-aside>

    <el-container>
      <!-- 顶部导航栏 -->
      <el-header class="header">
        <div class="header-left">
          <span class="page-breadcrumb">{{ pageTitle }}</span>
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand" trigger="click">
            <span class="user-info">
              <div class="user-avatar">
                <el-icon><UserFilled /></el-icon>
              </div>
              <span class="user-name">{{ userName }}</span>
              <el-icon class="user-arrow"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu class="user-dropdown">
                <el-dropdown-item command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 主内容区 -->
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  Compass,
  HomeFilled,
  Tickets,
  Reading,
  UserFilled,
  Document,
  ArrowDown,
  SwitchButton
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

/**
 * 当前激活的菜单项
 */
const activeMenu = computed(() => route.path)

/**
 * 顶部面包屑标题（依据当前路由动态展示）
 */
const pageTitle = computed(() => {
  const nameMap = {
    Home: '首页',
    Knowledge: '知识库',
    TravelList: '我的攻略',
    TravelDetail: '攻略详情',
    AdminUsers: '用户管理',
    AdminKnowledge: '系统知识库'
  }
  return nameMap[route.name] || '旅行攻略'
})

/**
 * 显示的用户名
 */
const userName = computed(() => {
  return authStore.user?.name || authStore.user?.username || '用户'
})

/**
 * 处理下拉菜单命令
 */
const handleCommand = async (command) => {
  if (command === 'logout') {
    await authStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

/* ============================================
   侧边栏 - 现代渐变深色
   ============================================ */
.sidebar {
  background-color: var(--sidebar-bg-start);
  display: flex;
  flex-direction: column;
  box-shadow: 1px 0 4px rgba(0, 0, 0, 0.08);
  position: relative;
  z-index: 10;
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.logo-icon {
  width: 36px;
  height: 36px;
  background-color: var(--color-primary);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  flex-shrink: 0;
}

.logo-text {
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  white-space: nowrap;
  letter-spacing: 0.02em;
}

.sidebar-nav {
  flex: 1;
  padding: 12px 10px;
  overflow-y: auto;
}

.sidebar-menu {
  border-right: none;
  background-color: transparent;
}

/* 菜单项样式 */
:deep(.sidebar-menu .el-menu-item) {
  height: 44px;
  line-height: 44px;
  margin: 2px 0;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-base);
  color: var(--sidebar-text);
}

:deep(.sidebar-menu .el-menu-item:hover) {
  background-color: var(--sidebar-hover) !important;
  color: #e2e8f0 !important;
}

:deep(.sidebar-menu .el-menu-item.is-active) {
  background-color: rgba(37, 99, 235, 0.15) !important;
  color: var(--sidebar-text-active) !important;
  font-weight: 600;
}

:deep(.sidebar-menu .el-menu-item.is-active::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--color-primary);
  border-radius: 0 3px 3px 0;
}

:deep(.sidebar-menu .el-menu-item .el-icon) {
  margin-right: 10px;
  font-size: 18px;
}

/* ============================================
   顶部栏
   ============================================ */
.header {
  background-color: var(--color-surface);
  border-bottom: 1px solid var(--color-border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  height: 60px;
  flex-shrink: 0;
  box-shadow: var(--shadow-sm);
}

.header-left {
  display: flex;
  align-items: center;
}

.page-breadcrumb {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: var(--radius-md);
  transition: background-color var(--transition-fast);
}

.user-info:hover {
  background-color: var(--color-border-light);
}

.user-avatar {
  width: 32px;
  height: 32px;
  background-color: var(--color-primary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 14px;
}

.user-name {
  color: var(--color-text-primary);
  font-size: 14px;
  font-weight: 500;
}

.user-arrow {
  color: var(--color-text-tertiary);
  font-size: 12px;
}

/* ============================================
   主内容区
   ============================================ */
.main-content {
  background-color: var(--color-bg);
  padding: var(--space-6);
  overflow-y: auto;
}

/* 下拉菜单样式 */
:deep(.user-dropdown) {
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  border: 1px solid var(--color-border-light);
  padding: 4px;
}

:deep(.user-dropdown .el-dropdown-menu__item) {
  border-radius: var(--radius-sm);
  font-size: 13px;
  padding: 8px 16px;
}

:deep(.user-dropdown .el-dropdown-menu__item:hover) {
  background-color: var(--color-danger-bg);
  color: var(--color-danger);
}

/* 管理后台菜单分隔线与分组标签 */
.menu-divider {
  height: 1px;
  background-color: rgba(255, 255, 255, 0.08);
  margin: 12px 8px;
}

.menu-group-label {
  padding: 4px 20px 8px;
  font-size: 11px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.35);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
</style>
