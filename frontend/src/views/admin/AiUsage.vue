<template>
  <div class="page-wrap">
    <div class="admin-page-title"><h2>AI用量统计</h2></div>
    <div class="usage-tabs">
      <el-tabs :model-value="activeUsageTab" @update:model-value="onUsageTabChange">
        <el-tab-pane label="用量概览" name="summary" />
        <el-tab-pane label="调用记录" name="logs" />
      </el-tabs>
    </div>
    <div v-if="showSummary" class="summary-section" v-loading="loading" element-loading-text="统计数据加载中…">
      <div class="scope-toolbar">
        <div v-if="canViewAllAiData" class="scope-group scope-data-group">
          <span class="scope-label">数据范围</span>
          <el-radio-group v-model="statsScope" class="scope-switch" size="small" @change="reloadSummary">
            <el-radio-button value="all">全部用户</el-radio-button>
            <el-radio-button value="self">我的数据</el-radio-button>
          </el-radio-group>
        </div>
        <div class="scope-group scope-model-group">
          <span class="scope-label">模型范围</span>
          <el-radio-group v-model="statsModelScope" class="scope-switch" size="small" @change="reloadSummary">
            <el-radio-button value="all">全部模型</el-radio-button>
            <el-radio-button value="platform">平台模型</el-radio-button>
            <el-radio-button value="mine">我的模型</el-radio-button>
          </el-radio-group>
        </div>
        <span class="scope-current">当前口径：{{ effectiveDataScopeLabel }} · {{ statsModelScopeLabel }}</span>
      </div>

      <template v-if="showStats">
        <div class="stats-layout">
          <!-- 左侧控制面板 -->
          <div class="stats-left">
            <div class="stats-grid-2x2">
              <div v-for="card in statCards" :key="card.key" class="stat-card" :class="card.class">
                <div class="stat-card-head">
                  <span class="stat-label">{{ card.label }}</span>
                </div>
                <strong>{{ card.value }}</strong>
                <span v-if="card.sub" class="quota-sub">{{ card.sub }}</span>
              </div>
            </div>
            <div class="stats-nav-panel">
              <div class="nav-panel-title">统计维度</div>
              <button v-for="t in statsTabs" :key="t.key" class="nav-panel-item" :class="{ active: activeStatsTab === t.key }" @click="activeStatsTab = t.key">
                <span>{{ t.label }}</span>
                <span class="nav-arrow">›</span>
              </button>
            </div>
            <div class="stat-summary" v-if="topSummary.length">
              <div class="summary-title">概览摘要</div>
              <div v-for="s in topSummary" :key="s.label" class="summary-row">
                <span class="summary-label">{{ s.label }}</span>
                <span class="summary-val">{{ s.value }}</span>
              </div>
            </div>
          </div>

          <!-- 右侧明细 -->
          <div class="stats-right">
            <!-- 筛选区 -->
        <div class="stats-filter-bar list-toolbar-frame">
              <el-input v-model="statsKeyword" :placeholder="statsSearchPlaceholder" clearable class="stats-search-input" size="small" @keyup.enter="doStatsSearch" />
              <template v-if="activeStatsTab === 'users'">
                <el-input v-model="statsPhone" placeholder="搜索手机号" clearable class="stats-phone-input" size="small" @keyup.enter="doStatsSearch" />
                <el-select v-model="statsDepartment" placeholder="选择部门" clearable class="stats-department-select" size="small">
                  <el-option v-for="item in departmentOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </template>
              <div class="stats-filter-actions">
                <el-button type="primary" size="small" @click="doStatsSearch">查询</el-button>
                <el-button size="small" @click="resetStatsFilter">重置</el-button>
                <span class="stats-total-hint">共 {{ statsTableTotal }} 条</span>
              </div>
            </div>

            <!-- 数据区 -->
            <div class="stats-data-area">
              <div class="stats-rank-body">
                <!-- 用户排行 -->
                <el-table
                  v-if="activeStatsTab === 'users'"
                  :data="userTableData"
                  stripe border size="small"
                  class="stats-el-table"
                  empty-text="暂无数据"
                >
                  <el-table-column label="排名" width="70" align="center" header-align="center">
                    <template #default="{ $index }">{{ rankIndex($index) }}</template>
                  </el-table-column>
                  <el-table-column label="用户名" min-width="160" align="center" header-align="center" show-overflow-tooltip>
                    <template #default="{ row }">
                      <span v-if="row.user_id" class="log-user-link" @click="onRowClick(row)">{{ row.user_name || '—' }}</span>
                      <span v-else class="text-muted">系统调用</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="手机号" min-width="160" align="center" header-align="center" show-overflow-tooltip>
                    <template #default="{ row }"><span class="text-muted">{{ row.phone || '—' }}</span></template>
                  </el-table-column>
                  <el-table-column label="部门" min-width="120" align="center" header-align="center" show-overflow-tooltip>
                    <template #default="{ row }"><span class="text-muted">{{ row.department || '—' }}</span></template>
                  </el-table-column>
                  <el-table-column label="状态" min-width="90" align="center" header-align="center">
                    <template #default="{ row }"><span class="text-muted">{{ row.status_label || '—' }}</span></template>
                  </el-table-column>
                  <el-table-column label="平台模型额度" min-width="130" align="center" header-align="center">
                    <template #default="{ row }"><span class="text-muted">{{ platformQuotaDisplay(row.platform_quota) }}</span></template>
                  </el-table-column>
                  <el-table-column label="调用次数" min-width="120" align="center" header-align="center">
                    <template #default="{ row }">
                      <button class="count-link" type="button" @click="goLogsByStatsRow(row)">{{ row.count }} 次</button>
                    </template>
                  </el-table-column>
                  <el-table-column label="占比" min-width="220" align="center" header-align="center">
                    <template #default="{ row }">
                      <div class="pct-bar-wrap">
                        <span class="pct-text">{{ pctText(row) }}</span>
                        <span class="pct-bar"><span class="pct-fill" :style="{ width: pctBarW(row) }"></span></span>
                      </div>
                    </template>
                  </el-table-column>
                </el-table>

                <!-- 其他 Tab -->
                <el-table
                  v-else-if="activeStatsTab !== 'users'"
                  :data="statsTablePagedData"
                  stripe border size="small"
                  class="stats-el-table"
                  empty-text="暂无数据"
                >
                  <el-table-column label="排名" width="70" align="center" header-align="center">
                    <template #default="{ $index }">{{ rankIndex($index) }}</template>
                  </el-table-column>
                  <el-table-column :label="statsTableColLabel" min-width="300" align="center" header-align="center" show-overflow-tooltip>
                    <template #default="{ row }">
                      <div class="distribution-name">
                        <span class="distribution-label">{{ row._label }}</span>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="调用次数" min-width="160" align="center" header-align="center">
                    <template #default="{ row }">
                      <button class="count-link" type="button" @click="goLogsByStatsRow(row)">{{ row.count }} 次</button>
                    </template>
                  </el-table-column>
                  <el-table-column label="占比" min-width="260" align="center" header-align="center">
                    <template #default="{ row }">
                      <div class="pct-bar-wrap">
                        <span class="pct-text">{{ pctText(row) }}</span>
                        <span class="pct-bar"><span class="pct-fill" :style="{ width: pctBarW(row) }"></span></span>
                      </div>
                    </template>
                  </el-table-column>
                </el-table>
            </div>
            </div>
            <div class="stats-table-foot">
              <el-pagination
                v-model:current-page="statsTablePage"
                :page-size="statsTablePageSize"
                layout="total, sizes, prev, pager, next"
                :page-sizes="[10, 50, 100]"
                :total="statsTableTotal"
                @current-change="statsTablePage = $event"
                @size-change="statsTablePageSize = $event; statsTablePage = 1"
              />
            </div>
          </div>
        </div>
      </template>

      <!-- 加载完成但没有拿到统计数据（接口失败/超时/暂无数据）时的兜底，避免一片白 -->
      <div v-else-if="summaryLoaded && !loading" class="stats-empty">
        <el-empty description="暂无数据">
          <el-button type="primary" @click="loadData()">重新加载</el-button>
        </el-empty>
      </div>
    </div>

    <UserDialog v-model="userDialogVisible" :user-id="detailUserId" mode="view" />
    <UserQuotaStatsDialog
      v-model="usageStatsVisible"
      :user-id="usageStatsUserId"
      :user-name="usageStatsUserName"
      :model-scope="usageStatsModelScope"
    />
    <el-dialog v-model="failureDetailVisible" title="调用失败详情" width="520px" append-to-body>
      <div class="failure-detail-content">{{ failureDetail }}</div>
      <template #footer><el-button type="primary" @click="failureDetailVisible = false">关闭</el-button></template>
    </el-dialog>
    <el-dialog v-model="usageDetailVisible" title="Token 用量明细" width="min(560px, calc(100vw - 48px))" append-to-body>
      <div class="usage-detail-summary">
        <AiUsageStatsBar variant="summary" layout="grid" :usage="usageDetail" />
      </div>
      <template #footer><el-button type="primary" @click="usageDetailVisible = false">关闭</el-button></template>
    </el-dialog>

    <div v-if="showLogs" class="scroll-area">
      <el-form :inline="true" :model="searchForm" class="log-search-form list-toolbar-frame">
        <el-form-item v-if="canViewAllAiData" label="姓名/手机号">
          <el-input v-model="searchForm.keyword" placeholder="姓名或手机号，模糊匹配" clearable style="width: 200px" @keyup.enter="searchLogs" />
        </el-form-item>
        <el-form-item label="调用时间">
          <el-date-picker
            v-model="searchForm.timeRange"
            type="daterange"
            format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DD"
            style="width: 240px"
          />
        </el-form-item>
        <el-form-item label="模型">
          <el-input v-model="searchForm.model" placeholder="模糊匹配" clearable style="width: 180px" @keyup.enter="searchLogs" />
        </el-form-item>
        <el-form-item label="模型范围">
          <el-select v-model="searchForm.modelScope" placeholder="全部" clearable style="width: 130px" @change="onLogModelScopeChange">
            <el-option label="平台模型" value="platform" />
            <el-option label="我的模型" value="personal" />
          </el-select>
        </el-form-item>
        <el-form-item label="功能">
          <el-input v-model="searchForm.action" placeholder="模糊匹配" clearable style="width: 180px" @keyup.enter="searchLogs" />
        </el-form-item>
        <el-form-item label="结果">
          <el-select v-model="searchForm.result" placeholder="全部" clearable style="width: 130px">
            <el-option label="成功" value="succeeded" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item class="log-search-actions">
          <div class="log-action-bar">
            <div class="log-action-buttons log-action-buttons--primary">
              <el-button type="primary" @click="searchLogs">查询</el-button>
              <el-button @click="resetLogs">重置</el-button>
            </div>
            <div v-if="canViewAllAiData" class="log-action-buttons">
              <el-button type="danger" plain :disabled="!selectedLogIds.length" @click="handleBatchDeleteLogs">
                批量删除<span v-if="selectedLogIds.length">（{{ selectedLogIds.length }}）</span>
              </el-button>
              <el-button type="danger" :disabled="!canDeleteAllLogs" @click="handleDeleteAllLogs">
                全部删除<span v-if="logsLoaded">（{{ total }}）</span>
              </el-button>
            </div>
          </div>
        </el-form-item>
      </el-form>

      <div class="usage-table-card">
      <el-table :data="logs" v-loading="loading" stripe class="usage-table" header-cell-class-name="no-wrap-header" @selection-change="handleLogSelectionChange">
        <template #empty><GlobalEmpty text="暂无数据" /></template>
        <el-table-column v-if="canViewAllAiData" type="selection" width="48" fixed="left" />
        <el-table-column label="真实姓名" prop="user_name" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.user_id" class="log-user-link" @click="detailUserId = row.user_id; userDialogVisible = true">{{ displayUserName(row) }}</span>
            <span v-else>{{ displayUserName(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="模型" prop="model" width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.model || '-' }}</template>
        </el-table-column>
        <el-table-column label="模型来源" width="140" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="modelScopeTagType(row)">{{ modelScopeLabel(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="功能" prop="action" width="210" show-overflow-tooltip>
          <template #default="{ row }"><span class="action-text">{{ actionLabel(row.action, row.feature) }}</span></template>
        </el-table-column>
        <el-table-column label="结果" width="90" align="center">
          <template #default="{ row }"><el-tag size="small" :type="row.status === 'succeeded' ? 'success' : 'danger'">{{ row.status === 'succeeded' ? '成功' : '失败' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="平台额度" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="quotaAppliesTo(row, 'platform')" size="small" :type="quotaSnapshotTagType(row)">{{ quotaSnapshot(row) }}</el-tag>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="我的额度" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="quotaAppliesTo(row, 'personal')" size="small" :type="quotaSnapshotTagType(row)">{{ quotaSnapshot(row) }}</el-tag>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="调用时间" min-width="170">
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="250" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :disabled="!row.user_id" @click="openUsageStats(row)">用量统计</el-button>
            <el-button link type="primary" @click="openUsageDetail(row)">用量明细</el-button>
            <el-button link type="primary" :disabled="row.status !== 'failed'" @click="showFailureDetail(row)">失败详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      </div>
    </div>

    <div class="pagination-area" v-if="showLogs && total > 0">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        layout="total, sizes, prev, pager, next"
        :page-sizes="[10, 50, 100]"
        :total="total"
        @current-change="onPageChange"
        @size-change="handleSizeChange"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { deleteAiUsageLogsAll, deleteAiUsageLogsBatch, getAiQuota, getAiUsageLogs } from '@/api/ai'
import UserDialog from '@/components/UserDialog.vue'
import AiUsageStatsBar from '@/components/AiUsageStatsBar.vue'
import UserQuotaStatsDialog from '@/views/admin/components/UserQuotaStatsDialog.vue'
import GlobalEmpty from '@/components/GlobalEmpty.vue'
import { buildAiUsageLogParams } from '@/utils/aiUsageFilters'
import { aiActionLabels, resolveAiFeatureLabel, resolveAiFunctionLabel } from '@/utils/aiUsageLabels'
import { formatBeijingMinute } from '@/utils/beijingTime'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps({
  view: {
    type: String,
    default: 'full',
    validator: (value) => ['summary', 'logs', 'full'].includes(value),
  },
})

const failureDetailVisible = ref(false)
const failureDetail = ref('')
const usageDetailVisible = ref(false)
const usageDetail = ref(null)

const userStore = useUserStore()
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const logs = ref([])
const total = ref(0)
const logsLoaded = ref(false)
const selectedLogIds = ref([])
const page = ref(1)
const pageSize = ref(10)
const quotaInfo = ref(null)
const quotaLoadFailed = ref(false)
const stats = ref(null)
const overviewStats = ref(null)
const summaryLoaded = ref(false)
const statsScope = ref('all')
const statsModelScope = ref('all')
const searchForm = ref({ userName: '', phone: '', keyword: '', department: '', callerType: '', timeRange: [], model: '', modelScope: '', modelOwnerScope: '', action: '', result: '' })

const cloneLogFilters = (form) => ({
  userName: form.userName || '',
  phone: form.phone || '',
  keyword: form.keyword || '',
  department: form.department || '',
  callerType: form.callerType || '',
  timeRange: Array.isArray(form.timeRange) ? [...form.timeRange] : [],
  model: form.model || '',
  modelScope: form.modelScope || '',
  modelOwnerScope: form.modelOwnerScope || '',
  action: form.action || '',
  result: form.result || '',
})
const serializeLogFilters = (form) => JSON.stringify({
  ...cloneLogFilters(form),
  timeRange: Array.isArray(form.timeRange)
    ? form.timeRange.map(value => value?.valueOf?.() ?? value)
    : [],
})
const appliedLogFilters = ref(cloneLogFilters(searchForm.value))
const appliedLogFiltersKey = ref(serializeLogFilters(appliedLogFilters.value))
const logFiltersDirty = computed(() => serializeLogFilters(searchForm.value) !== appliedLogFiltersKey.value)

const isSuperAdmin = computed(() => !!userStore.userInfo?.is_superuser)
const isManager = computed(() => !!userStore.userInfo?.is_manager)
const canViewAllAiData = computed(() => isSuperAdmin.value)
const canDeleteAllLogs = computed(() => canViewAllAiData.value && logsLoaded.value && !logFiltersDirty.value && total.value > 0)
const activeUsageTab = computed(() => route.meta.tab || (props.view === 'logs' || route.query.tab === 'logs' ? 'logs' : 'summary'))
const showSummary = computed(() => activeUsageTab.value === 'summary')
const showLogs = computed(() => activeUsageTab.value === 'logs')
const showStats = computed(() => !!overviewStats.value)
const remainingText = computed(() => {
  if (quotaLoadFailed.value) return '查询失败'
  const quota = quotaInfo.value
  if (!quota) return '查询中'
  if (quota.quota < 0) return '不限'
  if (quota.has_access === false) return '未配置'
  if (quota.quota == null && quota.has_personal_model_access) return '个人模型可用'
  return `${Math.max(0, Number(quota.remaining || 0))} 次`
})
const isQuotaExceeded = computed(() => {
  const quota = quotaInfo.value
  return !quotaLoadFailed.value && Number(quota?.quota) > 0 && Number(quota.today_used) >= Number(quota.quota)
})

// Stats table state
const activeStatsTab = ref('users')
const statsKeyword = ref('')
const statsAppliedKeyword = ref('')
const statsPhone = ref('')
const statsDepartment = ref('')
const statsTablePage = ref(1)
const statsTablePageSize = ref(10)
const detailUserId = ref(null)
const userDialogVisible = ref(false)
const usageStatsVisible = ref(false)
const usageStatsUserId = ref(null)
const usageStatsUserName = ref('')
const usageStatsModelScope = ref('')
const departmentOptions = [
  { label: '测试部门', value: 1 },
  { label: '开发部门', value: 2 },
  { label: '产品部门', value: 4 },
  { label: '运维部门', value: 3 },
  { label: '其他部门', value: 5 },
]
const statsTabs = computed(() => {
  return [
    { key: 'users', label: '用户排行' },
    { key: 'models', label: '模型分布' },
    { key: 'actions', label: '功能分布' },
  ]
})

function ensureStatsTabAccess() {
  if (!statsTabs.value.some(t => t.key === activeStatsTab.value)) {
    activeStatsTab.value = statsTabs.value[0]?.key || 'models'
  }
}

const statsSearchPlaceholder = computed(() => {
  const map = { actions: '搜索功能名称', models: '搜索模型名称', users: '搜索用户' }
  return map[activeStatsTab.value] || '搜索'
})
const effectiveDataScopeLabel = computed(() => (
  canViewAllAiData.value && statsScope.value === 'all' ? '全部用户' : '我的数据'
))
const statsModelScopeLabel = computed(() => ({
  all: '全部模型',
  platform: '平台模型',
  mine: '我的模型',
}[statsModelScope.value] || '全部模型'))
const statCards = computed(() => {
  const s = overviewStats.value || {}
  const cards = [
    { key: 'actual_calls', label: '实际调用', value: formatNumber(s.actual_calls ?? s.total_calls), sub: '总调用' },
    { key: 'quota_consumed_calls', label: '扣除次数', value: formatNumber(s.quota_consumed_calls) },
    { key: 'succeeded_calls', label: '成功', value: formatNumber(s.succeeded_calls) },
    { key: 'failed_calls', label: '失败', value: formatNumber(s.failed_calls) },
    { key: 'today', label: '今日调用', value: formatNumber(s.today_calls) },
    { key: 'week', label: '本周调用', value: formatNumber(s.week_calls) },
    { key: 'month', label: '本月调用', value: formatNumber(s.month_calls) },
    { key: 'year', label: '本年调用', value: formatNumber(s.year_calls) },
  ]
  const showRemainingCard = !canViewAllAiData.value || statsScope.value === 'self'
  if (!showRemainingCard && canViewAllAiData.value) {
    cards.push({ key: 'active_users', label: '活跃用户', value: formatNumber(s.active_users) })
  } else {
    cards.push({
      key: 'platform_quota',
      label: '平台模型额度',
      value: quotaLoadFailed.value
        ? '查询失败'
        : platformQuotaDisplay({ daily_limit: quotaInfo.value?.quota, today_used: quotaInfo.value?.today_used }),
      sub: `今日剩余：${remainingText.value}`,
      class: { 'quota-warning': isQuotaExceeded.value },
    })
  }
  return cards
})
const statsTableColLabel = computed(() => {
  const map = { actions: '功能名称', models: '模型名称', users: '用户' }
  return map[activeStatsTab.value] || '名称'
})
const statsTableRawData = computed(() => {
  const s = stats.value || {}
  const map = { actions: s.actions, models: s.models, users: s.top_users }
  const items = (map[activeStatsTab.value] || []).map(item => {
    const copy = { ...item }
    if (activeStatsTab.value === 'actions') {
      copy._label = actionLabel(item.action, item.feature)
      copy._key = item.feature || item.action
      copy._filterAction = item.feature || item.action
    }
    else if (activeStatsTab.value === 'models') { copy._label = item.model || '-'; copy._key = item.model }
    else if (activeStatsTab.value === 'users') { copy._label = userLabel(item); copy._key = item.user_id }
    else copy._label = '-'
    return copy
  })
  if (activeStatsTab.value !== 'actions') return items
  const grouped = new Map()
  items.forEach(item => {
    const existing = grouped.get(item._label)
    if (existing) {
      existing.count += Number(item.count || 0)
      existing._filterAction = existing._filterAction || item._filterAction
      return
    }
    grouped.set(item._label, { ...item, count: Number(item.count || 0) })
  })
  const totalCalls = Number(s.actual_calls ?? s.total_calls ?? 0)
  return Array.from(grouped.values()).map(item => ({
    ...item,
    percentage: totalCalls > 0 ? Math.round(item.count * 1000 / totalCalls) / 10 : 0,
  })).sort((a, b) => b.count - a.count)
})
const statsTableFiltered = computed(() => {
  let items = [...statsTableRawData.value]

  // 客户端关键字过滤，用于当前已返回的排行/分布列表内快速收窄。
  if (statsAppliedKeyword.value) {
    const kw = statsAppliedKeyword.value.toLowerCase()
    items = items.filter(item => {
      const searchable = [
        item._label || '',
        item.user_name || '',
        item.phone || '',
        item.model || '',
        item.action || '',
      ].join(' ').toLowerCase()
      return searchable.includes(kw)
    })
  }

  return items
})
const hasActiveFilter = computed(() => {
  return !!statsAppliedKeyword.value
})
const statsTableTotal = computed(() => {
  const systemRowCount = activeStatsTab.value === 'users' && unattributedCount.value > 0 ? 1 : 0
  return statsTableFiltered.value.length + systemRowCount
})
const statsTablePagedData = computed(() => {
  const start = (statsTablePage.value - 1) * statsTablePageSize.value
  return statsTableFiltered.value.slice(start, start + statsTablePageSize.value)
})
const userPagedData = computed(() => {
  return statsTablePagedData.value.map(item => ({
    ...item,
    _key: item._key || item.user_id || item._label,
    user_name: item.user_name || item._label || '—',
    phone: item.phone || '',
  }))
})
const userTableData = computed(() => {
  const list = [...userPagedData.value]
  if (showUnattributed.value) {
    list.push({
      _key: '__unattributed__',
      user_id: null,
      user_name: '系统调用',
      phone: '—',
      department: '—',
      status_label: '—',
      count: unattributedCount.value,
      percentage: Number(stats.value?.unattributed_percentage || 0),
    })
  }
  return list
})
const maxStatsCount = computed(() => Math.max(1, ...statsTableRawData.value.map(i => i.count || 0)))
const showUnattributed = computed(() => unattributedCount.value > 0 && statsTablePage.value === 1)
const unattributedCount = computed(() => Number(stats.value?.unattributed_calls || 0))

const topSummary = computed(() => {
  const s = overviewStats.value || {}
  const items = []
  const topUser = (s.top_users || [])[0]
  if (topUser) items.push({ label: 'Top 用户', value: `${topUser.user_name || '—'}，${topUser.count} 次` })
  const topModel = (s.models || [])[0]
  if (topModel) items.push({ label: 'Top 模型', value: `${topModel.model || '—'}，${topModel.count} 次` })
  return items
})

function pctText(item) {
  const pct = Number(item?.percentage || 0)
  if (pct >= 1) return `${pct.toFixed(1)}%`
  if (pct > 0) return '<1%'
  return '0%'
}
function pctBarW(item) {
  const pct = Number(item?.percentage || 0)
  if (pct <= 0) return '0%'
  return `${Math.max(pct, 0.5)}%`
}
function rankIndex(i) {
  return statsTablePageSize.value * (statsTablePage.value - 1) + i + 1
}

function isClickableRow(item) {
  // Only real users in the "users" tab are clickable
  if (activeStatsTab.value !== 'users') return false
  const name = (item._label || item.user_name || '').toLowerCase()
  if (name.includes('未归属') || name.includes('系统调用') || name.includes('已删除') || name.includes('未绑定')) return false
  return !!item.user_id
}

function onRowClick(item) {
  if (!item.user_id) return
  detailUserId.value = item.user_id
  userDialogVisible.value = true
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString('zh-CN')
}

function actionLabel(action, feature) {
  return resolveAiFunctionLabel({ action, feature })
}

function featureLabel(feature) {
  return resolveAiFeatureLabel(feature)
}

function userLabel(item) {
  const name = item.user_name || '未命名用户'
  return item.phone ? `${name} / ${item.phone}` : name
}

function modelScopeOf(row) {
  if (row?.model_scope === 'platform' || row?.model_scope === 'personal') return row.model_scope
  if (row?.quota_scope === 'platform' || row?.quota_scope === 'personal') return row.quota_scope
  return ''
}

function modelScopeLabel(row) {
  return { platform: '平台模型', personal: '我的模型' }[modelScopeOf(row)] || '归属未知'
}

function modelScopeTagType(row) {
  return { platform: 'primary', personal: 'success' }[modelScopeOf(row)] || 'info'
}

// 记录额度归属：优先看调用记录的额度范围，缺失/超管时回退模型范围，
// 一笔调用只会命中平台或个人其中一栏，另一栏展示 —。
function rowQuotaScope(row) {
  const raw = row?.quota_scope
  if (raw === 'platform' || raw === 'personal') return raw
  return row?.model_scope || null
}

function quotaAppliesTo(row, scope) {
  return rowQuotaScope(row) === scope
}

// 只展示本次调用的真实快照次数（扣费 1 次 / 未扣费 0 次），不再展示上限。
function quotaSnapshot(row) {
  const count = row?.quota_consumed ? Number(row?.quota_count || 1) : 0
  return `${count} 次`
}

function quotaSnapshotTagType(row) {
  return row?.quota_consumed ? 'success' : 'info'
}

function platformQuotaDisplay(quota) {
  if (!quota) return '未配置'
  const limit = Number(quota.daily_limit)
  if (limit === -1) return '不限'
  if (!Number.isFinite(limit) || limit <= 0) return '未配置'
  return `${Number(quota.today_used || 0)}/${limit}`
}

function displayUserName(row) {
  if (row.user_name) return row.user_name
  if (!row.user_id) return '系统任务'
  return '未命名用户'
}

function showFailureDetail(row) {
  failureDetail.value = row.failure_reason || '暂无失败详情'
  failureDetailVisible.value = true
}

function openUsageDetail(row) {
  usageDetail.value = row || null
  usageDetailVisible.value = true
}

function openUsageStats(row) {
  if (!row.user_id) return
  usageStatsUserId.value = row.user_id
  usageStatsUserName.value = displayUserName(row)
  usageStatsModelScope.value = modelScopeOf(row)
  usageStatsVisible.value = true
}

function onLogModelScopeChange(value) {
  searchForm.value.modelOwnerScope = value === 'personal' ? 'self' : ''
}

function fmt(d) {
  return formatBeijingMinute(d)
}

function addQueryValue(query, key, value) {
  if (value !== undefined && value !== null && value !== '') query[key] = String(value)
}

function buildStatsLogQuery(row) {
  const query = { fromUsage: '1' }
  addQueryValue(query, 'userName', searchForm.value.userName)
  addQueryValue(query, 'phone', searchForm.value.phone)
  addQueryValue(query, 'department', searchForm.value.department)
  addQueryValue(query, 'model', searchForm.value.model)
  addQueryValue(query, 'action', searchForm.value.action)
  delete query.callerType
  if (statsModelScope.value === 'platform') query.modelScope = 'platform'
  if (statsModelScope.value === 'mine') {
    query.modelScope = 'personal'
    query.modelOwnerScope = 'self'
  }
  if (canViewAllAiData.value && statsScope.value === 'self') query.scope = 'self'

  if (activeStatsTab.value === 'users') {
    if (row.user_id) {
      delete query.userName
      delete query.callerType
      addQueryValue(query, 'phone', row.phone)
      addQueryValue(query, 'department', statsDepartment.value)
    }
  } else if (activeStatsTab.value === 'models') {
    addQueryValue(query, 'model', row.model || row._key)
  } else if (activeStatsTab.value === 'actions') {
    addQueryValue(query, 'action', row._label || row._filterAction || row.action || row._key)
  }
  return query
}

function goLogsByStatsRow(row) {
  router.push({ path: '/model-admin/usage/records', query: buildStatsLogQuery(row) })
}

function onUsageTabChange(tab) {
  const target = tab === 'logs' ? '/model-admin/usage/records' : '/model-admin/usage/overview'
  const query = { ...route.query }
  delete query.tab
  if (target !== route.path) router.push({ path: target, query })
}

function readQueryValue(key) {
  const value = route.query[key]
  return Array.isArray(value) ? value[0] : value
}

function applyLogQuery() {
  if (!showLogs.value || readQueryValue('fromUsage') !== '1') return false
  const queryPhone = readQueryValue('phone') || ''
  searchForm.value = {
    userName: readQueryValue('userName') || '',
    phone: queryPhone,
    keyword: readQueryValue('keyword') || queryPhone,
    department: readQueryValue('department') || '',
    callerType: readQueryValue('callerType') || '',
    timeRange: readQueryValue('startDate') && readQueryValue('endDate')
      ? [readQueryValue('startDate'), readQueryValue('endDate')]
      : [],
    model: readQueryValue('model') || '',
    modelScope: readQueryValue('modelScope') || '',
    modelOwnerScope: readQueryValue('modelOwnerScope') || '',
    action: readQueryValue('action') || '',
    result: readQueryValue('result') || '',
  }
  page.value = 1
  return true
}

async function loadQuota() {
  try {
    quotaInfo.value = await getAiQuota()
    quotaLoadFailed.value = false
  } catch {
    quotaInfo.value = null
    quotaLoadFailed.value = true
  }
}

async function loadData(preserveOverview = false) {
  ensureStatsTabAccess()
  const appliedFilters = showLogs.value ? appliedLogFilters.value : searchForm.value
  if (showLogs.value) logsLoaded.value = false
  loading.value = true
  try {
    const res = await getAiUsageLogs(buildAiUsageLogParams({
      page: page.value,
      pageSize: pageSize.value,
      scope: canViewAllAiData.value
        ? (showLogs.value ? (readQueryValue('scope') || 'all') : statsScope.value)
        : 'self',
      userName: appliedFilters.userName,
      phone: appliedFilters.phone,
      keyword: appliedFilters.keyword,
      model: appliedFilters.model,
      modelScope: showSummary.value
        ? (statsModelScope.value === 'platform' ? 'platform' : statsModelScope.value === 'mine' ? 'personal' : '')
        : appliedFilters.modelScope,
      modelOwnerScope: showSummary.value
        ? (statsModelScope.value === 'mine' ? 'self' : '')
        : appliedFilters.modelOwnerScope,
      action: appliedFilters.action,
      result: appliedFilters.result,
      department: appliedFilters.department,
      callerType: showSummary.value ? '' : appliedFilters.callerType,
      timeRange: showSummary.value ? [] : appliedFilters.timeRange,
      includeStats: showSummary.value,
    }))
    logs.value = res?.items || []
    total.value = res?.total || 0
    selectedLogIds.value = []
    stats.value = res?.stats || null
    if (!preserveOverview && showSummary.value) overviewStats.value = res?.stats || null
  } catch {
    logs.value = []
    total.value = 0
    stats.value = null
    if (!preserveOverview) overviewStats.value = null
  } finally {
    loading.value = false
    if (showSummary.value) summaryLoaded.value = true
    if (showLogs.value) logsLoaded.value = true
  }
}

function handleSizeChange(size) {
  pageSize.value = size
  page.value = 1
  loadData()
}

function onPageChange(val) {
  page.value = val
  loadData()
}

function reloadSummary() {
  page.value = 1
  loadData()
}

function doStatsSearch() {
  statsAppliedKeyword.value = statsKeyword.value.trim()
  // Map stats tab to backend filter fields
  searchForm.value.userName = ''
  searchForm.value.model = ''
  searchForm.value.action = ''
  searchForm.value.result = ''
  searchForm.value.phone = ''
  searchForm.value.department = ''
  searchForm.value.callerType = ''
  if (activeStatsTab.value === 'users') {
    searchForm.value.userName = statsAppliedKeyword.value
    searchForm.value.phone = statsPhone.value.trim()
    searchForm.value.department = statsDepartment.value
  }
  else if (activeStatsTab.value === 'models') searchForm.value.model = statsAppliedKeyword.value
  else {
    const actionEntry = statsAppliedKeyword.value
      ? Object.entries(aiActionLabels).find(([, label]) => label.includes(statsAppliedKeyword.value))
      : null
    searchForm.value.action = actionEntry?.[0] || statsAppliedKeyword.value
  }
  statsTablePage.value = 1
  loadData()
}

function resetStatsFilter() {
  statsKeyword.value = ''
  statsAppliedKeyword.value = ''
  statsPhone.value = ''
  statsDepartment.value = ''
  searchForm.value.userName = ''
  searchForm.value.model = ''
  searchForm.value.action = ''
  searchForm.value.result = ''
  searchForm.value.phone = ''
  searchForm.value.department = ''
  searchForm.value.callerType = ''
  statsTablePage.value = 1
  loadData()
}

function handleLogSelectionChange(rows) {
  selectedLogIds.value = rows.map(row => row.id)
}

function buildUsageDeleteFilters() {
  const appliedFilters = appliedLogFilters.value
  const params = buildAiUsageLogParams({
    userName: appliedFilters.userName,
    phone: appliedFilters.phone,
    keyword: appliedFilters.keyword,
    model: appliedFilters.model,
    modelScope: appliedFilters.modelScope,
    modelOwnerScope: appliedFilters.modelOwnerScope,
    action: appliedFilters.action,
    result: appliedFilters.result,
    department: appliedFilters.department,
    callerType: appliedFilters.callerType,
    timeRange: appliedFilters.timeRange,
  })
  delete params.page
  delete params.page_size
  delete params.scope
  return params
}

async function handleBatchDeleteLogs() {
  try {
    await ElMessageBox.confirm(`将删除已选的 ${selectedLogIds.value.length} 条调用记录，删除后无法在页面恢复，是否继续？`, '删除确认', {
      type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消',
    })
    const res = await deleteAiUsageLogsBatch(selectedLogIds.value)
    ElMessage.success(res?.message || '调用记录已删除')
    await loadData()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') console.error('删除调用记录失败', error)
  }
}

async function handleDeleteAllLogs() {
  try {
    await ElMessageBox.confirm(`将删除当前查询结果中的 ${total.value} 条调用记录，删除后无法在页面恢复，是否继续？`, '全部删除确认', {
      type: 'warning', confirmButtonText: '确认全部删除', cancelButtonText: '取消',
    })
    const res = await deleteAiUsageLogsAll(buildUsageDeleteFilters())
    ElMessage.success(res?.message || '调用记录已删除')
    await loadData()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') console.error('删除调用记录失败', error)
  }
}

function searchLogs() {
  appliedLogFilters.value = cloneLogFilters(searchForm.value)
  appliedLogFiltersKey.value = serializeLogFilters(appliedLogFilters.value)
  page.value = 1
  loadData()
}

async function resetLogs() {
  searchForm.value = { userName: '', phone: '', keyword: '', department: '', callerType: '', timeRange: [], model: '', modelScope: '', modelOwnerScope: '', action: '', result: '' }
  if (Object.keys(route.query || {}).length) await router.replace({ path: '/model-admin/usage/records' })
  searchLogs()
}

onMounted(() => {
  ensureStatsTabAccess()
  applyLogQuery()
  appliedLogFilters.value = cloneLogFilters(searchForm.value)
  appliedLogFiltersKey.value = serializeLogFilters(appliedLogFilters.value)
  if (showSummary.value) loadQuota()
  loadData()
})

watch(() => route.query, () => {
  if (applyLogQuery()) {
    appliedLogFilters.value = cloneLogFilters(searchForm.value)
    appliedLogFiltersKey.value = serializeLogFilters(appliedLogFilters.value)
    loadData()
  }
})

watch(canViewAllAiData, () => {
  if (!canViewAllAiData.value) statsScope.value = 'self'
  ensureStatsTabAccess()
})

watch(activeStatsTab, () => {
  statsTablePage.value = 1
  statsKeyword.value = ''
  statsAppliedKeyword.value = ''
  statsPhone.value = ''
  statsDepartment.value = ''
  searchForm.value.userName = ''
  searchForm.value.model = ''
  searchForm.value.action = ''
  searchForm.value.phone = ''
  searchForm.value.department = ''
  searchForm.value.callerType = ''
  loadData()
})

watch(activeUsageTab, () => {
  page.value = 1
  if (showSummary.value) loadQuota()
  loadData()
})
</script>

<style scoped>
.page-wrap { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.usage-tabs { flex-shrink: 0; }
.usage-tabs :deep(.el-tabs__header) { margin-bottom: 12px; }
.failure-detail-content { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7; color: var(--el-text-color-regular); }
.usage-detail-summary { display: flex; justify-content: center; width: 100%; }

/* 范围切换 */
.scope-toolbar {
  position: relative; display: grid; grid-template-columns: 280px minmax(0, 1fr);
  align-items: center; gap: 10px 14px; margin-bottom: 10px; flex-shrink: 0;
}
.scope-group { display: flex; align-items: center; gap: 10px; }
.scope-data-group { grid-column: 1; }
.scope-model-group { grid-column: 2; }
.scope-label { color: #606266; font-size: 14px; font-weight: 500; white-space: nowrap; }
.scope-switch :deep(.el-radio-button__inner) { padding: 8px 18px; font-size: 14px; }
.scope-current {
  position: absolute; top: 50%; right: 0; transform: translateY(-50%);
  color: #909399; font-size: 12px; white-space: nowrap;
}

.summary-section { flex: 1; min-height: 0; overflow: hidden; display: flex; flex-direction: column; gap: 10px; padding-right: 4px; }
.stats-empty { flex: 1; min-height: 240px; display: flex; align-items: center; justify-content: center; }

/* 左右布局 */
.stats-layout { flex: 1; min-height: 0; overflow: hidden; display: grid; grid-template-columns: 280px 1fr; gap: 14px; }

/* ===== 左侧 ===== */
.stats-left { display: flex; flex-direction: column; gap: 12px; min-height: 0; height: 100%; overflow-y: auto; padding-right: 4px; }
.stats-grid-2x2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); grid-auto-rows: 94px; gap: 10px; flex-shrink: 0; }
.stats-left .stat-card {
  min-width: 0; height: 94px; padding: 14px 16px; border: 1px solid #edf1f7; border-radius: 8px; background: #fff;
  display: grid; grid-template-rows: 18px 30px 16px; row-gap: 3px; align-content: center;
}
.stat-card-head { min-width: 0; display: flex; align-items: center; justify-content: flex-start; }
.stat-label { min-width: 0; font-size: 12px; line-height: 18px; color: #8c8c8c; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.stats-left .stat-card strong { min-width: 0; font-size: 24px; line-height: 30px; color: #1a1a1a; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.stats-left .stat-card.quota-warning strong { color: #f56c6c; }
.quota-sub { min-width: 0; font-size: 12px; line-height: 16px; color: #909399; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 维度导航 */
.stats-nav-panel { flex-shrink: 0; border: 1px solid #e5eaf2; border-radius: 8px; background: #fff; overflow: hidden; }
.nav-panel-title,
.summary-title { padding: 10px 14px; font-size: 13px; font-weight: 600; color: #303133; background: #f8fafc; border-bottom: 1px solid #e9edf3; }
.nav-panel-item {
  display: flex; align-items: center; justify-content: space-between;
  width: 100%; padding: 10px 14px; border: none; background: transparent;
  font-size: 13px; color: #303133; cursor: pointer; text-align: left;
  transition: background .12s;
}
.nav-panel-item + .nav-panel-item { border-top: 1px solid #f8f9fb; }
.nav-panel-item:hover { background: #f5f7fa; }
.nav-panel-item.active { background: #e8f3ff; color: #1677ff; font-weight: 600; }
.nav-arrow { color: #bfbfbf; font-size: 14px; }
.nav-panel-item.active .nav-arrow { color: #1677ff; }

/* 概览摘要 */
.stat-summary { flex: 1; min-height: 0; margin-top: 0; border: 1px solid #e5eaf2; border-radius: 8px; background: #fff; overflow: hidden; }
.summary-row { display: flex; justify-content: space-between; gap: 8px; padding: 8px 14px; font-size: 12px; }
.summary-row + .summary-row { border-top: 1px solid #f3f5f8; }
.summary-label { color: #606266; white-space: nowrap; }
.summary-val { color: #303133; font-weight: 500; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ===== 右侧 ===== */
.stats-right { border: 1px solid #edf1f7; border-radius: 8px; background: #fff; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }

/* 筛选区 */
.stats-filter-bar {
  display: flex; align-items: center; flex-wrap: wrap; gap: 10px 12px;
  padding: 14px 16px; border-bottom: 1px solid #f0f0f0; flex-shrink: 0;
}
.stats-filter-bar :deep(.el-input__wrapper),
.stats-filter-bar :deep(.el-select__wrapper) { min-height: 34px; }
.stats-filter-bar :deep(.el-input__inner),
.stats-filter-bar :deep(.el-select__selected-item) { font-size: 14px; }
.stats-filter-bar :deep(.el-button) { min-height: 34px; padding: 8px 16px; font-size: 14px; }
.stats-search-input { width: 150px; }
.stats-phone-input { width: 180px; }
.stats-department-select { width: 150px; }
.stats-filter-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 10px 12px; }
.stats-filter-actions :deep(.el-button) { margin: 0; }
.stats-total-hint { font-size: 13px; color: #909399; flex-shrink: 0; margin-left: 4px; }

/* 数据区 */
.stats-data-area {
  flex: 1; min-height: 0; display: flex; flex-direction: column;
  border-bottom: 1px solid #f0f0f0;
}

/* 表格 */
.stats-rank-body { flex: 1; min-height: 0; overflow: auto; }
.stats-el-table { width: 100%; }
.stats-el-table :deep(th.el-table__cell) { background: #f8fafc; color: #303133; font-weight: 600; }
.stats-el-table :deep(.el-table__row) { height: 48px; }
.stats-el-table :deep(.el-table__header .cell) { white-space: nowrap; padding-left: 8px; padding-right: 8px; }
.stats-el-table :deep(.el-table__cell .cell) { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-left: 8px; padding-right: 8px; }
.text-muted { color: #909399; }

.pct-bar-wrap { display: flex; align-items: center; gap: 8px; }
.pct-text { flex-shrink: 0; width: 48px; text-align: right; font-size: 12px; color: #606266; font-weight: 500; }
.pct-bar { flex: 1; min-width: 30px; height: 6px; border-radius: 3px; background: #f0f2f5; overflow: hidden; }
.pct-fill { display: block; height: 100%; border-radius: 3px; background: #1677ff; transition: width .3s; }
.distribution-name { display: flex; align-items: center; justify-content: center; min-width: 0; }
.distribution-label { color: #303133; font-weight: 500; overflow: hidden; text-overflow: ellipsis; }
.pct-fill-muted { background: #dcdfe6; }
.count-link { padding: 0; border: 0; background: transparent; color: #1677ff; font: inherit; cursor: pointer; }
.count-link:hover { text-decoration: underline; }

.stats-table-foot { display: flex; justify-content: flex-end; padding: 10px 16px; flex-shrink: 0; }

/* 日志 */
.scroll-area { flex: 1; overflow: auto; min-height: 0; }
.pagination-area { flex-shrink: 0; display: flex; justify-content: flex-end; padding: 12px 0 0; }
.usage-table-card { min-width: 0; overflow-x: auto; border: 1px solid #edf1f7; border-radius: 8px; background: #fff; }
.usage-table { width: 100%; min-width: 980px; }
:deep(.no-wrap-header .cell) { white-space: nowrap; }
:deep(.usage-table .el-table__cell .cell) { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
:deep(.usage-table .el-table__cell:last-child .cell) { overflow: visible; }
:deep(.usage-table th.el-table__cell) { background: #f8fafc; color: #111827; font-weight: 700; }
:deep(.usage-table .el-table__row) { height: 48px; }
.mono-text { font-family: SFMono-Regular, Consolas, monospace; color: #475569; }
.action-text { color: #1f2937; font-weight: 600; }
.log-user-link { color: #1677ff; cursor: pointer; }
.log-user-link:hover { text-decoration: underline; }
.log-search-form { display: flex; align-items: flex-start; flex-wrap: wrap; gap: 12px 10px; margin-bottom: 10px; padding: 12px 14px; border: 1px solid #edf1f7; border-radius: 8px; background: #fff; }
.log-search-form :deep(.el-form-item) { margin: 0; }
.log-search-actions { flex: 1 1 100%; }
.log-search-actions :deep(.el-form-item__content) { width: 100%; margin: 0 !important; }
.log-action-bar { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-start; gap: 10px 12px; width: 100%; }
.log-action-buttons { display: flex; flex-wrap: wrap; gap: 10px 12px; }
.log-action-buttons :deep(.el-button) { margin: 0; }

/* 紧凑桌面端（1366~1600）：收窄调用记录筛选控件宽度与间距，尽量控制在两行内 */
@media (max-width: 1600px) {
  .log-search-form { gap: 10px 8px; }
  .log-search-form :deep(.el-form-item__label) { padding-right: 6px; }
  .log-search-form :deep(.el-form-item .el-input),
  .log-search-form :deep(.el-form-item .el-select) { max-width: 140px !important; }
  .log-search-form :deep(.el-form-item .el-date-editor) { max-width: 210px !important; }
}
@media (max-width: 1440px) {
  .log-search-form :deep(.el-form-item .el-input),
  .log-search-form :deep(.el-form-item .el-select) { max-width: 120px !important; }
  .log-search-form :deep(.el-form-item .el-date-editor) { max-width: 200px !important; }
}

@media (max-width: 1024px) {
  .stats-layout { grid-template-columns: 1fr; }
  .stats-left { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; overflow-y: visible; }
  .stats-nav-panel { grid-column: 1 / -1; }
  .stat-summary { grid-column: 1 / -1; }
  .scope-toolbar { grid-template-columns: 1fr; }
  .scope-data-group, .scope-model-group, .scope-current { grid-column: 1; }
  .scope-current { position: static; transform: none; justify-self: start; }
}
@media (max-width: 1366px) {
  .scope-current {
    position: static; grid-column: 1 / -1; transform: none;
    width: 100%; margin-left: 0; justify-self: end;
  }
}
</style>
