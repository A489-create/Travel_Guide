<template>
  <AuthLayout>
    <div class="login-header">
      <h1 class="login-title">开启你的下一段旅程</h1>
      <p class="login-subtitle">登录后，开始规划属于你的专属旅行攻略</p>
    </div>

    <el-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      @keyup.enter="handleLogin"
      class="login-form"
    >
      <el-form-item prop="phone">
        <el-input
          v-model="formData.phone"
          placeholder="手机号"
          :prefix-icon="Iphone"
          size="large"
        />
      </el-form-item>

      <el-form-item prop="password">
        <el-input
          v-model="formData.password"
          type="password"
          placeholder="密码"
          :prefix-icon="Lock"
          size="large"
          show-password
        />
      </el-form-item>

      <div class="form-options">
        <el-checkbox v-model="rememberMe">记住我</el-checkbox>
        <a href="javascript:void(0)" class="forgot-link">忘记密码？</a>
      </div>

      <el-form-item>
        <el-button
          type="primary"
          size="large"
          class="login-btn"
          :loading="loading"
          @click="handleLogin"
        >
          登录
        </el-button>
      </el-form-item>

      <div class="form-footer">
        <span>还没有账户？</span>
        <router-link to="/register" class="register-link">注册</router-link>
      </div>
    </el-form>
  </AuthLayout>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Iphone, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import AuthLayout from '@/components/AuthLayout.vue'

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref(null)
const loading = ref(false)
const rememberMe = ref(false)

const formData = reactive({
  phone: '',
  password: ''
})

const rules = {
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少为6位', trigger: 'blur' }
  ]
}

/**
 * 处理登录
 */
const handleLogin = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authStore.login(formData)
    ElMessage.success('登录成功')
    // 管理员跳转到管理后台，普通用户跳转到首页
    router.push(authStore.isAdmin ? '/admin/users' : '/home')
  } catch (error) {
    ElMessage.error(error.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-header {
  margin-bottom: 32px;
}

.login-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 6px;
  letter-spacing: -0.01em;
}

.login-subtitle {
  font-size: 14px;
  color: var(--color-text-tertiary);
  margin: 0;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.login-form :deep(.el-input__wrapper) {
  height: 42px;
  border-radius: 6px !important;
}

.form-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.forgot-link {
  font-size: 13px;
  color: var(--color-text-tertiary);
  text-decoration: none;
  transition: color 0.15s ease;
}

.forgot-link:hover {
  color: var(--color-text-primary);
}

.login-btn {
  width: 100%;
  height: 42px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 6px !important;
  background: #1a1a2e !important;
  border: none !important;
  color: #fff !important;
  box-shadow: none !important;
  transition: opacity 0.15s ease;
}

.login-btn:hover {
  opacity: 0.85;
}

.form-footer {
  text-align: center;
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--color-border-light);
  font-size: 13px;
  color: var(--color-text-tertiary);
}

.register-link {
  color: var(--color-text-primary);
  font-weight: 500;
  text-decoration: none;
  margin-left: 4px;
  transition: color 0.15s ease;
}

.register-link:hover {
  text-decoration: underline;
}
</style>
