<template>
  <section class="pending-page">
    <WorkbenchPageHeader title="待办事项" />
    <WorkbenchContentCard>
      <el-tabs v-model="activeTab" class="pending-tabs">
        <el-tab-pane name="pending">
          <template #label>待我处理 <el-badge v-if="dashboardStats.my_pending_bug_count" :value="dashboardStats.my_pending_bug_count" type="danger" class="tab-badge" /></template>
          <WorkbenchPendingList view="pending" :columns="bugColumns" :refresh-key="refreshKey" empty-text="暂无待处理 Bug" @changed="refreshAll" />
        </el-tab-pane>
        <el-tab-pane name="verification">
          <template #label>待我验证 <el-badge v-if="dashboardStats.my_verification_bug_count" :value="dashboardStats.my_verification_bug_count" type="danger" class="tab-badge" /></template>
          <WorkbenchPendingList view="verification" :columns="bugColumns" :refresh-key="refreshKey" empty-text="暂无待验证 Bug" @changed="refreshAll" />
        </el-tab-pane>
        <el-tab-pane name="handled">
          <template #label>我处理过</template>
          <WorkbenchPendingList view="handled" :columns="bugColumns" :refresh-key="refreshKey" empty-text="暂无处理记录" @changed="refreshAll" />
        </el-tab-pane>
      </el-tabs>
    </WorkbenchContentCard>
  </section>
</template>

<script setup>
import { inject, ref } from 'vue'
import WorkbenchContentCard from '@/views/test-workbench/components/WorkbenchContentCard.vue'
import WorkbenchPageHeader from '@/views/test-workbench/components/WorkbenchPageHeader.vue'
import WorkbenchPendingList from '@/views/test-workbench/components/WorkbenchPendingList.vue'

const { dashboardStats, refreshDashboardStats } = inject('workbenchContext')
const activeTab = ref('pending')
const refreshKey = ref(0)

const bugColumns = [
  { prop: 'title', label: 'Bug 标题', minWidth: 220 },
  { prop: 'system_name', label: '所属系统', width: 130 },
  { prop: 'version_no', label: '所属版本', width: 120 },
  { prop: 'severity', label: '严重级别', width: 100, format: 'severity' },
  { prop: 'status', label: '当前状态', width: 110, format: 'status' },
  { prop: 'assignee_name', label: '处理人', width: 120 },
  { prop: 'verifier_name', label: '验证人', width: 120 },
  { prop: 'updated_at', label: '最近更新时间', width: 180, format: 'time' },
]

const refreshAll = async () => {
  refreshKey.value += 1
  await refreshDashboardStats?.()
}
</script>

<style scoped>
.pending-page { height: 100%; min-height: 0; display: flex; flex-direction: column; gap: 16px; }
.pending-tabs { display: flex; flex: 1; flex-direction: column; min-height: 0; }
.pending-tabs :deep(.el-tabs__content) { flex: 1; min-height: 0; }
.pending-tabs :deep(.el-tab-pane) { height: 100%; display: flex; flex-direction: column; min-height: 0; }
.tab-badge { margin-left: 6px; }
</style>
