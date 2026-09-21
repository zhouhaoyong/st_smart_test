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

        <div
          v-for="item in reminders.items"
          :key="item.id"
          class="notice-item"
          :class="{ 'is-reopened': item.reminder_type === 'reopened' }"
          @click="goFeedback(item)"
        >
          <div class="notice-main">
            <el-tag size="small" :type="reminderTag(item.reminder_type)" effect="plain">{{ item.reminder_label }}</el-tag>
            <span class="notice-title-text">{{ item.title || '未命名反馈' }}</span>
          </div>
          <div class="notice-sub">
            <UserAvatar
              :size="20"
              :src="item.user_avatar"
              :name="item.user_name"
              :user-id="item.user_id"
            />
            <span>{{ item.user_name || '本人' }} · {{ formatTime(item.updated_at || item.created_at) }}</span>
          </div>
        </div>

        <el-empty v-if="reminders.items.length === 0" description="暂无新的反馈提醒" :image-size="96" />
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
import { formatBeijingMinute } from '@/utils/beijingTime'
import UserAvatar from '@/components/UserAvatar.vue'

const router = useRouter()
const userStore = useUserStore()
const drawerVisible = ref(false)
const reminders = ref({ pending_count: 0, todo_count: 0, unread_reply_count: 0, reopened_count: 0, pending_confirm_count: 0, my_attention_count: 0, total: 0, items: [] })

const isSuperAdmin = computed(() => userStore.userInfo?.is_superuser)
const badgeValue = computed(() => Number(isSuperAdmin.value ? reminders.value.todo_count : reminders.value.my_attention_count) || 0)

async function loadReminders() {
  if (!userStore.userInfo) return
  try {
    const res = await getFeedbackReminders()
    reminders.value = {
      pending_count: Number(res?.pending_count || 0),
      todo_count: Number(res?.todo_count || 0),
      unread_reply_count: Number(res?.unread_reply_count ?? res?.unread_resolved_count ?? 0),
      reopened_count: Number(res?.reopened_count || 0),
      pending_confirm_count: Number(res?.pending_confirm_count || 0),
      my_attention_count: Number(res?.my_attention_count || 0),
      total: Number(res?.total || 0),
      items: Array.isArray(res?.items) ? res.items : [],
    }
  } catch {}
}

function openDrawer() {
  loadReminders()
  drawerVisible.value = true
}

function formatTime(value) {
  return formatBeijingMinute(value)
}

function reminderTag(type) {
  return type === 'reopened' ? 'warning' : type === 'pending_confirm' ? 'danger' : type === 'unread_reply' ? 'primary' : 'info'
}

function goFeedback(item) {
  drawerVisible.value = false
  const query = {
    tab: isSuperAdmin.value ? 'todo' : 'my',
    feedback_id: String(item.id),
  }
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
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  transition: border-color .2s, background .2s;
}
.notice-item:hover { border-color: var(--nexus-primary, #1677ff); background: #f7fbff; }
.notice-item.is-reopened { border-color: #f3d19e; background: #fffaf2; }
.notice-item.is-reopened:hover { border-color: #e6a23c; background: #fff7e8; }
.notice-main { display: flex; align-items: flex-start; gap: 8px; min-width: 0; font-size: 14px; font-weight: 600; color: #303133; line-height: 1.5; }
.notice-title-text { min-width: 0; flex: 1; word-break: break-word; }
.notice-sub { display: flex; align-items: center; gap: 5px; margin-top: 5px; font-size: 12px; color: #909399; line-height: 20px; }
</style>
