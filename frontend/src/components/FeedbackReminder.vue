<template>
  <div class="feedback-reminder">
    <el-badge :value="badgeValue" :hidden="badgeValue === 0" :max="99">
      <button class="reminder-btn" type="button" title="消息提醒" @click="openDrawer">
        <el-icon :size="18"><Bell /></el-icon>
      </button>
    </el-badge>

    <el-drawer v-model="drawerVisible" title="消息提醒" size="360px" append-to-body>
      <div class="notice-group">
        <div class="notice-title">
          <span>问题反馈</span>
          <el-tag v-if="badgeValue > 0" size="small" type="danger" effect="plain">{{ badgeValue }}</el-tag>
        </div>

        <div v-if="isAdmin && reminders.pending_count > 0" class="notice-item" @click="goFeedback('pending')">
          <div class="notice-main">有 {{ reminders.pending_count }} 条新的问题反馈待处理</div>
          <div class="notice-sub">点击查看待处理反馈</div>
        </div>

        <div v-if="isAdmin && reminders.reopened_count > 0" class="notice-item is-reopened" @click="goFeedback('reopened')">
          <div class="notice-main">有 {{ reminders.reopened_count }} 条已处理反馈被重新打开</div>
          <div class="notice-sub">提交人继续反馈了问题，需要再次确认处理</div>
        </div>

        <div v-if="reminders.unread_reply_count > 0" class="notice-item" @click="goFeedback('unreadReply')">
          <div class="notice-main">你有 {{ reminders.unread_reply_count }} 条反馈有新回复</div>
          <div class="notice-sub">点击查看处理进展，必要时确认关闭或继续反馈</div>
        </div>

        <div v-if="reminders.pending_confirm_count > 0" class="notice-item" @click="goFeedback('pendingConfirm')">
          <div class="notice-main">有 {{ reminders.pending_confirm_count }} 条反馈待你确认</div>
          <div class="notice-sub">点击查看处理结果并确认是否完成</div>
        </div>

        <el-empty v-if="badgeValue === 0" description="暂无新的反馈提醒" :image-size="96" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Bell } from '@element-plus/icons-vue'
import { getFeedbackReminders } from '@/api/feedback'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const drawerVisible = ref(false)
const reminders = ref({ pending_count: 0, unread_reply_count: 0, reopened_count: 0, pending_confirm_count: 0, total: 0 })

const isAdmin = computed(() => userStore.userInfo?.is_superuser || userStore.userInfo?.is_manager)
const badgeValue = computed(() => Number(reminders.value.total || 0))

async function loadReminders() {
  if (!userStore.userInfo) return
  try {
    const res = await getFeedbackReminders()
    reminders.value = {
      pending_count: Number(res?.pending_count || 0),
      unread_reply_count: Number(res?.unread_reply_count ?? res?.unread_resolved_count ?? 0),
      reopened_count: Number(res?.reopened_count || 0),
      pending_confirm_count: Number(res?.pending_confirm_count || 0),
      total: Number(res?.total || 0),
    }
  } catch {}
}

function openDrawer() {
  loadReminders()
  drawerVisible.value = true
}

function goFeedback(type) {
  drawerVisible.value = false
  const query = type === 'pendingConfirm'
    ? { tab: 'my', status: 'pending_confirm' }
    : type === 'pending'
    ? { tab: 'todo' }
    : type === 'reopened'
      ? { tab: 'todo', reopened: '1' }
    : { tab: 'my' }
  router.push({ path: '/feedback', query })
}

function onFeedbackChanged() {
  loadReminders()
}

onMounted(() => {
  loadReminders()
  window.addEventListener('feedback-reminders-refresh', onFeedbackChanged)
})

onBeforeUnmount(() => {
  window.removeEventListener('feedback-reminders-refresh', onFeedbackChanged)
})
</script>

<style scoped>
.feedback-reminder { display: inline-flex; align-items: center; }
.reminder-btn {
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #606266;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background .2s, color .2s;
}
.reminder-btn:hover { background: #f0f5ff; color: var(--nexus-primary, #1677ff); }
.notice-group { display: flex; flex-direction: column; gap: 12px; }
.notice-title { display: flex; align-items: center; justify-content: space-between; font-size: 16px; font-weight: 700; color: #303133; }
.notice-item {
  padding: 14px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  transition: border-color .2s, background .2s;
}
.notice-item:hover { border-color: var(--nexus-primary, #1677ff); background: #f7fbff; }
.notice-item.is-reopened { border-color: #f3d19e; background: #fffaf2; }
.notice-item.is-reopened:hover { border-color: #e6a23c; background: #fff7e8; }
.notice-main { font-size: 14px; font-weight: 600; color: #303133; line-height: 1.5; }
.notice-sub { margin-top: 4px; font-size: 12px; color: #909399; }
</style>
