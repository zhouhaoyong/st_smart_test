<template>
  <header class="topbar">
    <div class="topbar-brand" role="link" tabindex="0" aria-label="返回首页" @click="$router.push('/dashboard')" @keydown.enter="$router.push('/dashboard')">
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="nxGrad" x1="0" y1="40" x2="40" y2="0">
            <stop offset="0%" stop-color="#1677ff"/>
            <stop offset="100%" stop-color="#722ed1"/>
          </linearGradient>
        </defs>
        <path d="M24 4 L12 22 L18 22 L14 36 L30 18 L22 18 Z" fill="url(#nxGrad)"/>
      </svg>
      <span class="brand-text">智测</span>
    </div>

    <nav class="topbar-nav">
      <router-link to="/test-workbench" class="topbar-tab" :class="{ active: isWorkbenchModule }">
        <el-icon :size="18"><Tickets /></el-icon>
        <span>测试工作台</span>
      </router-link>
      <router-link to="/projects" class="topbar-tab" :class="{ active: isApiModule }">
        <el-icon :size="18"><VideoPlay /></el-icon>
        <span>API测试</span>
      </router-link>
      <router-link to="/tools" class="topbar-tab" :class="{ active: isToolModule }">
        <el-icon :size="18"><Postcard /></el-icon>
        <span>工具箱</span>
      </router-link>
      <router-link to="/tools/navigation" class="topbar-tab" :class="{ active: isNavModule }">
        <el-icon :size="18"><Location /></el-icon>
        <span>导航管理</span>
      </router-link>
      <router-link to="/profile" class="topbar-tab" :class="{ active: isAdminModule }">
        <el-icon :size="18"><Setting /></el-icon>
        <span>管理中心</span>
      </router-link>
    </nav>

    <div class="topbar-right">
      <FeedbackReminder />
      <el-dropdown trigger="click" @command="handleCommand">
        <div class="user-info">
          <div class="user-avatar" :style="userStore.userInfo?.avatar ? {} : { background: avatarBgColor, color: '#fff' }">
            <img v-if="userStore.userInfo?.avatar" :src="userStore.userInfo.avatar" class="avatar-img" />
            <span v-else>{{ userAvatarLetter }}</span>
          </div>
          <span>{{ userStore.userInfo?.real_name || '用户' }}</span>
          <el-icon :size="14"><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile"><el-icon><User /></el-icon>个人中心</el-dropdown-item>
            <el-dropdown-item divided command="logout"><el-icon><SwitchButton /></el-icon>退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import FeedbackReminder from '@/components/FeedbackReminder.vue'
import { ElMessageBox } from 'element-plus'
import { Setting, SwitchButton, VideoPlay, ArrowDown, User, Location, Postcard, Tickets } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const adminPageNames = new Set(['Profile', 'Users', 'DataAdminAudit', 'DataAdminCleanup', 'ModelAdminModels', 'ModelAdminUsage', 'ConfigAdminChannels', 'ConfigAdminTemplates', 'ConfigAdminPolicies', 'Feedback', 'UserUsageDetail'])
const isAdminModule = computed(() => adminPageNames.has(route.name))

const isApiModule = computed(() => route.path.startsWith('/project/') || route.path === '/projects')
const isWorkbenchModule = computed(() => route.path.startsWith('/test-workbench'))
const isToolModule = computed(() => route.path.startsWith('/tools/') && !route.path.includes('/navigation'))
const isNavModule = computed(() => route.path.startsWith('/tools/navigation'))

const handleCommand = (cmd) => {
  switch (cmd) {
    case 'profile': router.push('/profile'); break
    case 'logout':
      ElMessageBox.confirm('确定退出登录？', '提示', { type: 'warning' })
        .then(async () => { await userStore.logout(); router.push('/login') })
        .catch(() => {})
      break
  }
}

const userAvatarLetter = computed(() => {
  const name = userStore.userInfo?.real_name
  return name ? name.charAt(0).toUpperCase() : '用'
})

const avatarBgColors = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#f5222d', '#faad14']
const avatarBgColor = computed(() => {
  const userId = userStore.userInfo?.id || 0
  return avatarBgColors[userId % avatarBgColors.length]
})
</script>

<style scoped>
.topbar {
  height: 60px; background: #fff; border-bottom: 1px solid #f0f0f0;
  display: flex; align-items: center; padding: 0 24px; flex-shrink: 0; z-index: 100;
}
.topbar-brand { display: flex; align-items: center; gap: 10px; cursor: pointer; color: #1677ff; margin-right: 28px; }
.brand-text { font-size: 22px; font-weight: 800; letter-spacing: -0.5px; }
.topbar-nav { display: flex; gap: 4px; flex: 1; }
.topbar-tab {
  display: flex; align-items: center; gap: 8px; padding: 9px 18px;
  border-radius: 8px; font-size: 16px; color: #595959; text-decoration: none;
  transition: background-color .18s ease, color .18s ease;
  font-weight: 500;
}
.topbar-tab:hover { background: #f0f5ff; color: #1677ff; }
.topbar-tab.active { background: #e6f4ff; color: #1677ff; box-shadow: inset 0 -2px 0 #1677ff; }
.topbar-tab:focus-visible,
.topbar-brand:focus-visible { outline: 2px solid #1677ff; outline-offset: 3px; }
.topbar-right { display: flex; align-items: center; gap: 10px; }
.user-info { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 15px; padding: 4px 6px; border-radius: 8px; }
.user-info:hover { background: #f5f5f5; }
.user-avatar { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 15px; font-weight: 700; flex-shrink: 0; overflow: hidden; }
.avatar-img { width: 100%; height: 100%; object-fit: cover; }

@media (max-width: 1600px) {
  .topbar { padding: 0 20px; }
  .topbar-brand { margin-right: 20px; }
  .topbar-tab { padding: 8px 14px; font-size: 15px; }
}
@media (max-width: 1200px) {
  .topbar-nav { gap: 2px; }
  .topbar-tab { padding: 8px 12px; gap: 6px; }
}
@media (max-width: 768px) {
  .topbar { padding: 0 12px; }
  .topbar-brand { margin-right: 12px; }
  .brand-text { font-size: 19px; }
  .topbar-tab { padding: 8px 10px; font-size: 14px; gap: 4px; }
  .topbar-tab span { display: none; }
  .user-info > span { display: none; }
}
@media (max-width: 480px) {
  .topbar-tab { padding: 6px 8px; font-size: 13px; }
  .topbar-brand { margin-right: 8px; }
  .brand-text { font-size: 17px; }
}
</style>
