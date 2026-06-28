<template>
  <AuthLayout>
    <div class="register-header">
      <h1 class="register-title">{{ isAdminMode ? '管理员注册' : '加入我们，探索更多精彩' }}</h1>
      <p class="register-subtitle">{{ isAdminMode ? '注册管理员账号，管理系统与知识库' : '注册账户，让 AI 为你定制每一次旅行' }}</p>
    </div>

    <el-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      @keyup.enter="handleRegister"
      class="register-form"
    >
      <el-form-item prop="phone">
        <el-input
          v-model="formData.phone"
          placeholder="手机号"
          :prefix-icon="Iphone"
          size="large"
        />
      </el-form-item>

      <el-form-item prop="username">
        <el-input
          v-model="formData.username"
          placeholder="用户名"
          :prefix-icon="User"
          size="large"
        />
      </el-form-item>

      <el-form-item prop="name">
        <el-input
          v-model="formData.name"
          placeholder="姓名"
          :prefix-icon="Avatar"
          size="large"
        />
      </el-form-item>

      <el-form-item prop="password">
        <el-input
          v-model="formData.password"
          type="password"
          placeholder="密码（至少6位）"
          :prefix-icon="Lock"
          size="large"
          show-password
        />
      </el-form-item>

      <el-form-item prop="confirmPassword">
        <el-input
          v-model="formData.confirmPassword"
          type="password"
          placeholder="确认密码"
          :prefix-icon="Lock"
          size="large"
          show-password
        />
      </el-form-item>

      <!-- 管理员注册时显示邀请码字段 -->
      <el-form-item v-if="isAdminMode" prop="inviteCode">
        <el-input
          v-model="formData.inviteCode"
          placeholder="管理员邀请码"
          :prefix-icon="Key"
          size="large"
        />
      </el-form-item>

      <el-form-item>
        <el-button
          type="primary"
          size="large"
          class="register-btn"
          :loading="loading"
          @click="handleRegister"
        >
          {{ isAdminMode ? '注册管理员' : '注册' }}
        </el-button>
      </el-form-item>

      <div class="form-footer">
        <span>已有账户？</span>
        <router-link to="/login" class="login-link">登录</router-link>
        <span class="divider">|</span>
        <a href="#" class="mode-link" @click.prevent="toggleMode">
          {{ isAdminMode ? '普通用户注册' : '管理员注册' }}
        </a>
      </div>
    </el-form>
  </AuthLayout>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Iphone, User, Avatar, Lock, Key } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import AuthLayout from '@/components/AuthLayout.vue'

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref(null)
const loading = ref(false)
const isAdminMode = ref(false)

const formData = reactive({
  phone: '',
  username: '',
  name: '',
  password: '',
  confirmPassword: '',
  inviteCode: ''
})

/**
 * 确认密码校验器
 */
const validateConfirmPassword = (rule, value, callback) => {
  if (value !== formData.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

/**
 * 管理员邀请码校验器
 */
const validateInviteCode = (rule, value, callback) => {
  if (isAdminMode.value && !value.trim()) {
    callback(new Error('请输入管理员邀请码'))
  } else {
    callback()
  }
}

const rules = computed(() => ({
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号格式', trigger: 'blur' }
  ],
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  name: [
    { required: true, message: '请输入姓名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少为6位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ],
  inviteCode: [
    { validator: validateInviteCode, trigger: 'blur' }
  ]
}))

/**
 * 切换普通/管理员注册模式
 */
const toggleMode = () => {
  isAdminMode.value = !isAdminMode.value
  formData.inviteCode = ''
}

/**
 * 处理注册
 */
const handleRegister = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const registerData = {
      phone: formData.phone,
      username: formData.username,
      name: formData.name,
      password: formData.password
    }

    if (isAdminMode.value) {
      registerData.inviteCode = formData.inviteCode
      await authStore.registerAdmin(registerData)
      ElMessage.success('管理员注册成功，请登录')
    } else {
      await authStore.register(registerData)
      ElMessage.success('注册成功，请登录')
    }

    setTimeout(() => {
      router.push('/login')
    }, 1500)
  } catch (error) {
    ElMessage.error(error.message || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-header {
  margin-bottom: 32px;
}

.register-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 6px;
  letter-spacing: -0.01em;
}

.register-subtitle {
  font-size: 14px;
  color: var(--color-text-tertiary);
  margin: 0;
}

.register-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.register-form :deep(.el-input__wrapper) {
  height: 42px;
  border-radius: 6px !important;
}

.register-btn {
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

.register-btn:hover {
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

.divider {
  margin: 0 8px;
  color: var(--color-border-light);
}

.login-link,
.mode-link {
  color: var(--color-text-primary);
  font-weight: 500;
  text-decoration: none;
  margin-left: 4px;
  transition: color 0.15s ease;
}

.login-link:hover,
.mode-link:hover {
  text-decoration: underline;
}
</style>
