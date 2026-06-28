<template>
  <div class="auth-page">
    <!-- 左侧插画区域 -->
    <div class="auth-illustration">
      <img src="/images/q75.jpg" alt="illustration" />
      <div class="illustration-overlay">
        <div class="brand">
          <div class="brand-mark">
            <el-icon :size="20"><Compass /></el-icon>
          </div>
          <h2 class="brand-name">旅途助手</h2>
          <p class="brand-desc">发现世界每一处风景，定制你的专属旅程</p>
        </div>
      </div>
    </div>

    <!-- 右侧表单区域 -->
    <div class="auth-form-panel">
      <div class="auth-form-wrapper">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup>
import { Compass } from '@element-plus/icons-vue'
</script>

<style scoped>
.auth-page {
  display: flex;
  min-height: 100vh;
}

/* 左侧插画 */
.auth-illustration {
  position: relative;
  width: 40%;
  min-height: 100vh;
  background: #1a1a2e;
  overflow: hidden;
}

.auth-illustration img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.7;
}

.illustration-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: 48px;
  background: linear-gradient(to top, rgba(26, 26, 46, 0.9) 0%, rgba(26, 26, 46, 0.3) 60%, transparent 100%);
}

.brand {
  color: #fff;
}

.brand-mark {
  width: 40px;
  height: 40px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
  backdrop-filter: blur(4px);
}

.brand-name {
  font-size: 22px;
  font-weight: 600;
  margin: 0 0 8px;
  letter-spacing: -0.01em;
}

.brand-desc {
  font-size: 14px;
  margin: 0;
  opacity: 0.7;
  line-height: 1.5;
  max-width: 280px;
}

/* 右侧表单 */
.auth-form-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fafafa;
  padding: 40px 24px;
}

.auth-form-wrapper {
  width: 100%;
  max-width: 380px;
}

/* 响应式：小屏隐藏左侧 */
@media (max-width: 768px) {
  .auth-illustration {
    display: none;
  }

  .auth-form-panel {
    padding: 32px 20px;
  }
}
</style>
