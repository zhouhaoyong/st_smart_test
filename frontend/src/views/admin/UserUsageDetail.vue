<template>
  <div class="page-wrap" v-loading="loading">
    <div class="page-head">
      <el-button text @click="goBack"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
    </div>

    <template v-if="userInfo">
      <div class="user-card">
        <div class="user-avatar" :style="userInfo.avatar ? {} : { background: avatarColor }">
          <img v-if="userInfo.avatar" :src="userInfo.avatar" :alt="`${userInfo.real_name || '用户'}头像`" />
          <span v-else>{{ userInfo.real_name?.charAt(0) || '?' }}</span>
        </div>
        <div class="user-meta">
          <h2>{{ userInfo.real_name || '未知用户' }}</h2>
          <p>{{ userInfo.phone || '—' }} · 用户 ID: {{ userId }}</p>
        </div>
        <div class="user-stats">
          <div class="ustat"><span class="ustat-label">总调用</span><strong>{{ formatNumber(summary.total_calls) }}</strong></div>
          <div class="ustat"><span class="ustat-label">今日调用</span><strong>{{ formatNumber(summary.today_calls) }}</strong></div>
          <div class="ustat"><span class="ustat-label">本月调用</span><strong>{{ formatNumber(summary.month_calls) }}</strong></div>
          <div class="ustat"><span class="ustat-label">最近调用</span><strong class="ustat-time">{{ lastCallTime }}</strong></div>
        </div>
      </div>

      <div class="detail-grid">
        <div class="detail-card detail-card-wide">
          <div class="card-title">模型分布</div>
          <div class="card-list" v-if="modelList.length">
            <div v-for="m in modelList" :key="m.model" class="card-row">
              <span>{{ m.model || '-' }}</span>
              <span class="card-count">{{ m.count }} 次</span>
            </div>
          </div>
          <el-empty v-else description="暂无数据" :image-size="40" />
        </div>
      </div>

      <div class="log-section">
        <div class="section-title">调用明细</div>
        <el-table :data="logs" border stripe size="small" class="log-table" empty-text="暂无调用记录">
          <el-table-column label="时间" width="150">
            <template #default="{ row }">{{ shortTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="功能" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">{{ actionLabel(row.action, row.feature) }}</template>
          </el-table-column>
          <el-table-column label="模型" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ row.model || '-' }}</template>
          </el-table-column>
          <el-table-column label="平台模型额度" width="120" align="center">
            <template #default="{ row }">{{ quotaDisplay(row, 'platform') }}</template>
          </el-table-column>
          <el-table-column label="我的模型额度" width="140" align="center">
            <template #default="{ row }">{{ quotaDisplay(row, 'personal') }}</template>
          </el-table-column>
          <el-table-column label="次数" width="80" align="right">
            <template #default="{ row }">{{ row.call_count || 1 }}</template>
          </el-table-column>
        </el-table>
        <div class="log-foot" v-if="total > logPageSize">
          <el-pagination
            v-model:current-page="logPage"
            :page-size="logPageSize"
            layout="total, prev, pager, next"
            :total="total"
            @current-change="onLogPageChange"
          />
        </div>
      </div>
    </template>
    <el-empty v-else description="用户不存在" :image-size="60" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { getUser } from '@/api/user'
import { getAiUsageLogs } from '@/api/ai'
import { buildAiUsageLogParams } from '@/utils/aiUsageFilters'
import { resolveAiFunctionLabel } from '@/utils/aiUsageLabels'
import { formatBeijingMinute } from '@/utils/beijingTime'

const route = useRoute()
const router = useRouter()
const userId = computed(() => Number(route.params.userId))
const loading = ref(false)
const userInfo = ref(null)
const summary = ref({ total_calls: 0, today_calls: 0, month_calls: 0 })
const modelList = ref([])
const logs = ref([])
const total = ref(0)
const logPage = ref(1)
const logPageSize = ref(20)

const avatarColors = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#f5222d', '#faad14']
const avatarColor = computed(() => avatarColors[(userId.value || 0) % avatarColors.length])

const lastCallTime = computed(() => {
  if (logs.value.length) return shortTime(logs.value[0].created_at)
  return '—'
})

function actionLabel(action, feature) {
  return resolveAiFunctionLabel({ action, feature })
}

function quotaDisplay(row, scope) {
  const actualScope = row?.quota_scope === 'superuser' ? row?.model_scope : row?.quota_scope
  if (actualScope !== scope) return '—'
  const used = row?.quota_consumed ? Number(row?.quota_count || 1) : 0
  const limit = Number(row?.quota_limit)
  if (limit === -1) return `${used}/不限`
  if (!Number.isFinite(limit)) return `${used}/—`
  if (limit <= 0) return `${used}/已关闭`
  return `${used}/${limit}`
}

function shortTime(d) {
  if (!d) return '—'
  const value = formatBeijingMinute(d)
  return value ? value.slice(5) : '-'
}

async function loadData() {
  loading.value = true
  try {
    const user = await getUser(userId.value)
    userInfo.value = user

    const filterUserName = user.real_name || user.user_name || ''
    const statsRes = await getAiUsageLogs(buildAiUsageLogParams({
      page: 1, pageSize: 1,
      scope: 'all',
      userName: filterUserName,
      includeStats: true,
    }))
    const s = statsRes?.stats || {}
    summary.value = {
      total_calls: s.total_calls || 0,
      today_calls: s.today_calls || 0,
      month_calls: s.month_calls || 0,
    }
    modelList.value = s.models || []
    await loadLogs()
  } catch {
    userInfo.value = null
  } finally {
    loading.value = false
  }
}

async function loadLogs() {
  try {
    const filterUserName = userInfo.value?.real_name || ''
    const res = await getAiUsageLogs(buildAiUsageLogParams({
      page: logPage.value, pageSize: logPageSize.value,
      scope: 'all',
      userName: filterUserName,
      includeStats: false,
    }))
    logs.value = res?.items || []
    total.value = res?.total || 0
  } catch {
    logs.value = []
    total.value = 0
  }
}

const onLogPageChange = (p) => { logPage.value = p; loadLogs() }
const goBack = () => router.back()

onMounted(loadData)
</script>

<style scoped>
.page-wrap { height: 100%; display: flex; flex-direction: column; overflow: hidden; padding: 0 4px; }
.page-head { flex-shrink: 0; margin-bottom: 12px; }

.user-card {
  display: flex; align-items: center; gap: 16px;
  padding: 20px; border: 1px solid #edf1f7; border-radius: 8px; background: #fff;
  margin-bottom: 16px; flex-shrink: 0; flex-wrap: wrap;
}
.user-avatar { width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: 700; color: #fff; flex-shrink: 0; overflow: hidden; }
.user-avatar img { width: 100%; height: 100%; object-fit: cover; }
.user-meta { flex: 1; min-width: 160px; }
.user-meta h2 { margin: 0 0 4px; font-size: 18px; font-weight: 600; color: #1a1a1a; }
.user-meta p { margin: 0; font-size: 13px; color: #8c8c8c; }
.user-stats { display: flex; gap: 24px; margin-left: auto; flex-wrap: wrap; }
.ustat { display: flex; flex-direction: column; gap: 2px; min-width: 70px; }
.ustat-label { font-size: 12px; color: #8c8c8c; }
.ustat strong { font-size: 18px; color: #1a1a1a; }
.ustat-time { font-size: 14px !important; font-weight: 500 !important; color: #606266 !important; }

.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 16px; flex-shrink: 0; }
.detail-card { border: 1px solid #edf1f7; border-radius: 8px; background: #fff; padding: 14px 18px; }
.detail-card-wide { grid-column: 1 / -1; }
.card-title { font-size: 13px; font-weight: 600; color: #8c8c8c; margin-bottom: 10px; }
.card-list { display: flex; flex-direction: column; }
.card-row { display: flex; justify-content: space-between; gap: 12px; min-width: 0; padding: 6px 0; font-size: 13px; color: #303133; border-bottom: 1px solid #f8f9fb; }
.card-row:last-child { border-bottom: none; }
.card-row > span:first-child { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-count { flex-shrink: 0; font-weight: 500; color: #606266; white-space: nowrap; }

.log-section { flex: 1; min-height: 0; display: flex; flex-direction: column; border: 1px solid #edf1f7; border-radius: 8px; background: #fff; overflow: hidden; }
.section-title { padding: 12px 18px; font-size: 13px; font-weight: 600; color: #8c8c8c; border-bottom: 1px solid #f0f0f0; flex-shrink: 0; }
.log-table { flex: 1; }
.log-table :deep(.el-table__header .cell) { white-space: nowrap; }
.log-table :deep(.el-table__cell .cell) { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.log-foot { display: flex; justify-content: flex-end; padding: 10px 16px; border-top: 1px solid #f0f0f0; flex-shrink: 0; }
</style>
