<template>
  <div class="reports-container">
    <!-- 列表视图 -->
    <el-card v-if="!detailVisible">
      <template #header>
        <div class="card-header">
          <h3>测试报告</h3>
        </div>
      </template>
      <div class="list-toolbar-frame">
        <el-form :inline="true" class="report-filter-form" @submit.prevent>
          <el-form-item label="报告名称">
            <el-input v-model="searchName" placeholder="模糊搜索" clearable style="width:180px" />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="filterStatus" placeholder="全部" clearable style="width:110px">
              <el-option label="全部" value="all" />
              <el-option label="成功" value="success" />
              <el-option label="失败" value="failed" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="page=1;loadReports()">查询</el-button>
            <el-button @click="searchName='';filterStatus='all';page=1;loadReports()">重置</el-button>
          </el-form-item>
        </el-form>
        <div class="card-header-actions list-toolbar-actions">
          <el-button type="default" @click="handleSelectAll">全选</el-button>
          <el-button type="danger" @click="handleBatchDelete">批量删除</el-button>
        </div>
      </div>

      <div v-if="listLoadError" class="load-error">
        <span>报告加载失败，请重试</span>
        <el-button link type="primary" @click="loadReports">重新加载</el-button>
      </div>

      <el-table class="report-list-table" :data="reportList" v-loading="loading" stripe style="width:100%" @selection-change="handleSelectionChange" ref="reportTableRef">
        <template #empty><GlobalEmpty text="暂无数据" /></template>
        <el-table-column type="selection" width="45" />
        <el-table-column label="报告名称" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click="handleView(row)">{{ row.name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="execution_set_name" label="所属执行集" min-width="130" show-overflow-tooltip />
        <el-table-column prop="environment_name" label="运行环境" min-width="100" show-overflow-tooltip />
        <el-table-column label="执行方式" width="90">
          <template #default="{ row }">
            <el-tag :type="row.execution_mode === 'parallel' ? 'warning' : 'info'" size="small">{{ row.execution_mode === 'parallel' ? '并行' : '串行' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="执行结果" min-width="140">
          <template #default="{ row }">
            <div class="result-cell">
              <span style="color:#67c23a;font-weight:600">{{ row.passed_cases }}</span>
              <span style="color:#c0c4cc">/</span>
              <span style="color:#f56c6c;font-weight:600">{{ row.failed_cases }}</span>
              <el-progress :percentage="Math.round(row.pass_rate || 0)" :color="getProgressColor(row.pass_rate)" :stroke-width="8" :show-text="false" style="width:50px;margin-left:6px;flex-shrink:0" />
              <span style="color:#909399;font-size:12px;white-space:nowrap">{{ Math.round(row.pass_rate || 0) }}%</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="90">
          <template #default="{ row }">{{ formatDuration(row.duration) }}</template>
        </el-table-column>
        <el-table-column label="执行时间" min-width="170">
          <template #default="{ row }">{{ formatDate(row.start_time || row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="消息发送记录" min-width="120">
          <template #default="{ row }">
            <el-button class="clickable-soft" link type="info" size="small" @click="showSendLogs(row)">点击查看</el-button>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <div style="white-space:nowrap">
              <el-button link type="primary" size="small" @click="handleView(row)">查看详情</el-button>
              <el-button link type="primary" size="small" @click="handleSendReport(row)">发送报告</el-button>
              <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, sizes, prev, pager, next" :page-sizes="[10, 50, 100]"
        @current-change="onPageChange"
        @size-change="onPageSizeChange"
        style="margin-top:20px;justify-content:flex-end"
      />
    </el-card>

    <!-- 详情视图 -->
    <div v-else class="report-detail">
      <div class="report-detail-header">
        <el-button icon="Back" @click="goBack">返回列表</el-button>
        <h3>{{ report?.name }}</h3>
        <div class="report-meta">
          <el-tag :type="getStatusType(report?.status)">{{ getStatusText(report?.status) }}</el-tag>
          <span v-if="report?.environment_name" style="color:#8c8c8c">环境: {{ report.environment_name }}</span>
          <el-tag :type="report?.execution_mode === 'parallel' ? 'warning' : 'info'" size="small" style="vertical-align:middle">{{ report?.execution_mode === 'parallel' ? '并行' : '串行' }}</el-tag>
          <span>耗时: {{ formatDuration(report?.duration) }}</span>
        </div>
      </div>

      <!-- 前三张卡片点击即按状态筛选下方列表；通过率是派生指标，没有对应的用例子集，保持静态 -->
      <div class="stats-cards">
        <button
          type="button"
          :class="['stat-card', 'stat-card--total', 'stat-card--clickable', { 'is-active': !groupFilter }]"
          @click="filterGroupsByStatus('')"
        >
          <div class="stat-title">总用例</div>
          <div class="stat-value">{{ statTotal }}</div>
          <div class="stat-sub">{{ scopeFiltered ? '当前筛选范围内的用例' : `共 ${statTotal} 个测试用例` }}</div>
        </button>
        <button
          type="button"
          :class="['stat-card', 'stat-card--passed', 'stat-card--clickable', { 'is-active': groupFilter === 'pass' }]"
          @click="filterGroupsByStatus('pass')"
        >
          <div class="stat-title">成功用例</div>
          <div class="stat-value">{{ statPassed }}</div>
          <div class="stat-sub">占比 {{ statRatio(statPassed) }}%</div>
        </button>
        <button
          type="button"
          :class="['stat-card', 'stat-card--failed', 'stat-card--clickable', { 'is-active': groupFilter === 'fail' }]"
          @click="filterGroupsByStatus('fail')"
        >
          <div class="stat-title">失败用例</div>
          <div class="stat-value">{{ statFailed }}</div>
          <div class="stat-sub">占比 {{ statRatio(statFailed) }}%</div>
        </button>
        <div class="stat-card stat-card--rate">
          <div class="stat-title">通过率</div>
          <div class="stat-value">{{ Math.round(statPassRate) }}<span class="stat-unit">%</span></div>
          <div class="stat-sub">{{ scopeFiltered ? '当前筛选范围通过比例' : '测试用例通过比例' }}</div>
        </div>
      </div>

      <!-- 按用例分组展示 -->
      <!-- 常驻搜索栏 -->
      <div class="detail-query-bar">
        <el-form-item label="用例名称" class="report-filter-item report-filter-item--keyword">
          <el-input v-model="groupSearch" placeholder="搜索用例名称" clearable size="default" />
        </el-form-item>
        <el-form-item label="状态" class="report-filter-item report-filter-item--status">
          <el-select v-model="groupFilter" placeholder="全部状态" size="default" clearable>
            <el-option label="全部" value="" />
            <el-option label="通过" value="pass" />
            <el-option label="失败" value="fail" />
          </el-select>
        </el-form-item>
        <el-form-item label="接口集" class="report-filter-item report-collection-filter-item">
          <el-cascader
            v-model="groupCollectionFilter"
            :options="interfaceCollectionTree"
            :props="groupCollectionCascaderProps"
            filterable
            clearable
            collapse-tags
            :max-collapse-tags="1"
            :show-all-levels="false"
            placeholder="全部接口集"
            class="report-collection-filter-select"
            popper-class="report-collection-cascader-popper"
          >
            <template #default="{ data }">
              <CollectionNodeLabel :node="data" />
            </template>
          </el-cascader>
        </el-form-item>
        <el-button type="primary" @click="doGroupSearch">查询</el-button>
        <el-button @click="resetGroupFilters">重置</el-button>
        <span style="color:#909399;font-size:13px;margin-left:auto" v-if="groupTotal">共 {{ groupTotal }} 个用例</span>
      </div>
      <div class="case-list-panel">
        <div v-if="groups.length" class="groups-section" v-loading="groupLoading">
          <el-card
            v-for="(group, gi) in groups"
            :key="gi"
            :class="['case-card', group.failed > 0 ? 'case-failed' : 'case-passed', isCaseExpanded(group, gi) ? 'is-expanded' : 'is-collapsed']"
            :body-style="isCaseExpanded(group, gi) ? undefined : { display: 'none' }"
          >
            <template #header>
              <div class="case-card-header" @click="toggleCaseGroup(group, gi)">
                <div class="case-title-area">
                  <el-icon class="case-expand-icon" :size="14">
                    <ArrowDown v-if="isCaseExpanded(group, gi)" />
                    <ArrowRight v-else />
                  </el-icon>
                  <span class="case-name">
                    <el-icon :size="16" :color="group.failed > 0 ? '#f56c6c' : '#67c23a'" style="margin-right:4px">
                      <CircleCheck v-if="group.failed === 0" /><CircleClose v-else />
                    </el-icon>
                    <span class="case-name-text" :title="`用例 #${(groupPage - 1) * groupPageSize + gi + 1}: ${group.test_case_name || '-'}`">用例 #{{ (groupPage - 1) * groupPageSize + gi + 1 }}: {{ group.test_case_name }}</span>
                  </span>
                  <el-button
                    v-if="canJumpToTestCase(group)"
                    class="case-link-button"
                    link
                    type="primary"
                    size="small"
                    @click.stop="jumpToTestCase(group)"
                  >
                    <el-icon :size="14"><Link /></el-icon>
                    查看用例
                  </el-button>
                  <span v-else class="case-link-button case-link-button--disabled" aria-disabled="true">
                    <el-icon :size="14"><CircleClose /></el-icon>
                    {{ getCaseLinkText(group) }}
                  </span>
                  <span :class="['case-status-pill', group.failed > 0 ? 'is-failed' : 'is-passed']">
                    {{ group.failed > 0 ? '失败' : '通过' }}
                  </span>
                </div>
              </div>
            </template>

            <div v-if="isCaseExpanded(group, gi)" class="case-body">
              <div class="case-summary">
                <div class="case-summary-grid">
                  <button type="button" class="summary-metric assertion-summary-button" @click="showGroupAssertions(group, gi, 'all')">
                    <span class="summary-label">总断言</span>
                    <span class="summary-value">{{ groupAssertionSummary(group).total }}</span>
                  </button>
                  <button type="button" class="summary-metric assertion-summary-button" @click="showGroupAssertions(group, gi, 'passed')">
                    <span class="summary-label">断言通过</span>
                    <span class="summary-value success">{{ groupAssertionSummary(group).passed }}</span>
                  </button>
                  <button type="button" class="summary-metric assertion-summary-button" @click="showGroupAssertions(group, gi, 'failed')">
                    <span class="summary-label">未通过</span>
                    <span class="summary-value danger">{{ groupAssertionSummary(group).failed }}</span>
                  </button>
                  <div class="summary-metric summary-metric--wide">
                    <span class="summary-label">接口集</span>
                    <span class="summary-text">{{ formatInterfaceCollection(group) }}</span>
                  </div>
                  <div class="summary-metric summary-metric--wide">
                    <span class="summary-label">接口</span>
                    <span class="summary-text">{{ formatInterface(group) }}</span>
                  </div>
                </div>
              </div>

              <div v-for="(step, si) in group.steps" :key="si" class="step-block">
              <div :class="['step-bar', step.status === 'success' ? 'step-success' : 'step-failed']">
                <div class="step-bar-left">
                  <span class="step-num">{{ step.step_order }}</span>
                    <span class="step-name" :title="step.interface_name || step.name || '接口请求'">{{ step.interface_name || step.name || '接口请求' }}</span>
                </div>
                <div class="step-metrics">
                  <span :class="['step-status-pill', step.status === 'success' ? 'is-passed' : 'is-failed']">
                    {{ step.status === 'success' ? '通过' : '失败' }}
                  </span>
                  <span v-if="step.retry_attempts" class="step-metric warn">重试 {{ step.retry_attempts }} 次</span>
                  <span v-if="step.duration" class="step-metric">{{ step.duration }}ms</span>
                </div>
              </div>

              <div v-if="shouldShowStepError(step)" class="step-error">
                <el-alert :title="step.error_message" type="error" show-icon :closable="false" />
              </div>

              <div class="step-detail-panel">
                <div class="execution-result-header">
                  <div class="execution-result-title">
                    <span v-if="step.interface_method" class="execution-method">{{ step.interface_method }}</span>
                    <strong :title="step.interface_name || step.name || '接口请求'">{{ step.interface_name || step.name || '接口请求' }}</strong>
                  </div>
                  <span class="execution-case-name">用例：{{ group.test_case_name || step.name || '-' }}</span>
                </div>
                <el-tabs
                  :model-value="getReportMainTab(gi, si)"
                  class="step-tabs"
                  @update:model-value="setReportDetailTab(gi, si, 'main', $event)"
                >
                  <el-tab-pane label="请求信息" name="request">
                    <ExecutionRequestDetail
                      :active-tab="getReportDetailTab(gi, si, 'request')"
                      :method="step.request_data?.method || step.interface_method || ''"
                      :request-url="step.request_data?.url || step.interface_url || ''"
                      :params-text="structuredText(step.request_data?.params)"
                      :path-params-text="structuredText(step.request_data?.path_params)"
                      :body-text="requestBodyText(step.request_data?.body)"
                      :headers-text="structuredText(step.request_data?.headers)"
                      :proxy-text="formatExecutionValue(step.request_data?.proxy)"
                      :service="step.request_data?.service"
                      @update:active-tab="setReportDetailTab(gi, si, 'request', $event)"
                    />
                  </el-tab-pane>
                  <el-tab-pane label="响应结果" name="response">
                    <ExecutionResponseDetail
                      :active-tab="getReportDetailTab(gi, si, 'response')"
                      :body-text="responseBodyText(step.response_data)"
                      :headers-text="structuredText(step.response_data?.headers)"
                      @update:active-tab="setReportDetailTab(gi, si, 'response', $event)"
                    >
                      <template #body>
                        <pre class="code-block code-block--response">{{ responseBodyText(step.response_data) || '(无)' }}</pre>
                      </template>
                      <template #headers>
                        <pre class="code-block">{{ structuredText(step.response_data?.headers) || '(无)' }}</pre>
                      </template>
                    </ExecutionResponseDetail>
                  </el-tab-pane>
                  <el-tab-pane label="断言结果" name="assertions">
                    <AssertionDiffTable :diffs="getReportAssertionDiffs(gi, si, step)" />
                  </el-tab-pane>
                  <el-tab-pane label="脚本日志" name="logs">
                    <pre class="code-block log-block">{{ step.logs || '(无)' }}</pre>
                  </el-tab-pane>
                </el-tabs>
              </div>
              </div>
            </div>
          </el-card>
        </div>

        <GlobalEmpty
          v-else-if="!groupLoading"
          :text="groupTotal ? '没有匹配的用例' : '暂无详情数据'"
        />
      </div>

      <div v-if="groupLoadError" class="load-error">
        <span>报告详情加载失败，请重试</span>
        <el-button link type="primary" @click="loadReportGroups">重新加载</el-button>
      </div>

      <el-pagination
        v-if="groupTotal > groupPageSize"
        v-model:current-page="groupPage"
        v-model:page-size="groupPageSize"
        :total="groupTotal"
        layout="total, sizes, prev, pager, next"
        :page-sizes="[10, 50, 100]"
        class="detail-pagination"
        @current-change="loadReportGroups"
        @size-change="handleGroupPageSizeChange"
      />
    </div>

    <!-- 发送日志弹窗 -->
    <el-dialog v-model="sendLogDialogVisible" title="消息发送记录" width="760px" destroy-on-close class="send-log-dialog">
      <el-table :data="pagedSendLogs" stripe v-loading="sendLogLoading" style="width:100%" class="send-log-table">
        <el-table-column prop="group_name" label="发送群" min-width="120" show-overflow-tooltip />
        <el-table-column prop="channel_name" label="渠道" width="100">
          <template #default="{ row }">{{ channelLabel(row.channel_name) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sent_at" label="发送时间" width="180">
          <template #default="{ row }"><span class="send-log-time">{{ formatDate(row.sent_at) }}</span></template>
        </el-table-column>
      </el-table>
      <div v-if="!sendLogLoading && sendLogs.length === 0" style="text-align:center;padding:20px;color:#909399">暂无发送记录</div>
      <el-pagination
        v-if="sendLogs.length > sendLogPageSize"
        v-model:current-page="sendLogPage"
        :page-size="sendLogPageSize"
        :total="sendLogs.length"
        layout="total, prev, pager, next"
        style="margin-top:12px;justify-content:flex-end"
      />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { ArrowDown, ArrowRight, Back, CircleCheck, CircleClose, Link } from '@element-plus/icons-vue'
import { formatBeijingTime } from '@/utils/beijingTime'
import { getReports, getReport, getReportGroupedDetails, sendReport, getReportSendLogs, deleteReport, batchDeleteReports } from '@/api/reports'
import GlobalEmpty from '@/components/GlobalEmpty.vue'
import { formatExecutionValue, formatResponseBody, summarizeAssertionDiffs } from '@/utils/executionResult'
import ExecutionRequestDetail from '@/components/ExecutionRequestDetail.vue'
import ExecutionResponseDetail from '@/components/ExecutionResponseDetail.vue'
import AssertionDiffTable from '@/components/AssertionDiffTable.vue'
import CollectionNodeLabel from '@/components/CollectionNodeLabel.vue'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => route.params.id)

const reportTableRef = ref(null)
const selectedReports = ref([])
const loading = ref(false)
const reportList = ref([])
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const listLoadError = ref(false)
const filterStatus = ref('all')
const searchName = ref('')

const detailVisible = ref(false)
const report = ref(null)
const groups = ref([])
const groupLoading = ref(false)
const groupTotal = ref(0)
const groupLoadError = ref(false)
const groupSearch = ref('')
const groupFilter = ref('')
const groupCollectionFilter = ref([])
const groupPage = ref(1)
const groupPageSize = ref(10)
const interfaceCollectionTree = ref([])
const groupCollectionCascaderProps = {
  value: 'id',
  label: 'name',
  children: 'children',
  multiple: true,
  checkStrictly: true,
  emitPath: false,
}
const expandedCaseGroups = ref({})
const reportDetailTabs = ref({})

// 统计卡片数字跟随用例名称、接口集条件变化；状态条件不算在内，
// 因为卡片本身就是这个范围内的状态分布，也是状态筛选的入口。
// 后端没返回统计时退回报告整体数字，保证卡片不会空着
const groupStats = ref(null)
const scopeFiltered = ref(false)
const statTotal = computed(() => groupStats.value?.total_cases ?? report.value?.total_cases ?? 0)
const statPassed = computed(() => groupStats.value?.passed_cases ?? report.value?.passed_cases ?? 0)
const statFailed = computed(() => groupStats.value?.failed_cases ?? report.value?.failed_cases ?? 0)
const statPassRate = computed(() => groupStats.value?.pass_rate ?? report.value?.pass_rate ?? 0)
const statRatio = (value) => (statTotal.value ? Math.round(value / statTotal.value * 100) : 0)

const getCaseGroupKey = (group, index) => `${group.test_case_id || 'case'}-${groupPage.value}-${index}`
const isCaseExpanded = (group, index) => !!expandedCaseGroups.value[getCaseGroupKey(group, index)]
const toggleCaseGroup = (group, index) => {
  const key = getCaseGroupKey(group, index)
  expandedCaseGroups.value = {
    ...expandedCaseGroups.value,
    [key]: !expandedCaseGroups.value[key],
  }
}

const getReportDetailKey = (groupIndex, stepIndex) => `${groupPage.value}-${groupIndex}-${stepIndex}`
const getReportDetailTab = (groupIndex, stepIndex, section) => {
  const key = getReportDetailKey(groupIndex, stepIndex)
  // 请求信息未手动切过时交给详情组件自动定位到第一个有数据的页签；响应结果固定先看响应体
  return reportDetailTabs.value[key]?.[section] || (section === 'request' ? 'auto' : 'body')
}
const setReportDetailTab = (groupIndex, stepIndex, section, value) => {
  const key = getReportDetailKey(groupIndex, stepIndex)
  reportDetailTabs.value = {
    ...reportDetailTabs.value,
    [key]: { ...(reportDetailTabs.value[key] || {}), [section]: value },
  }
}
// 与接口调试、用例执行保持一致：默认先看响应结果，请求信息和断言结果由用户主动切
const getReportMainTab = (groupIndex, stepIndex) => {
  const key = getReportDetailKey(groupIndex, stepIndex)
  return reportDetailTabs.value[key]?.main || 'response'
}
const getReportStepAssertionDiffs = (step) => Array.isArray(step?.diff_result) ? step.diff_result : []
const getGroupAssertionDiffs = (group) => (group?.steps || []).flatMap(getReportStepAssertionDiffs)
const groupAssertionSummary = (group) => summarizeAssertionDiffs(getGroupAssertionDiffs(group))
const assertionMatchesFilter = (diff, filter) => {
  if (filter === 'passed') return diff?.result === 'pass'
  if (filter === 'failed') return diff?.result !== 'pass'
  return true
}
const getReportAssertionFilter = (groupIndex, stepIndex) => {
  const key = getReportDetailKey(groupIndex, stepIndex)
  return reportDetailTabs.value[key]?.assertionFilter || 'all'
}
const getReportAssertionDiffs = (groupIndex, stepIndex, step) => sortedAssertions(
  getReportStepAssertionDiffs(step).filter(diff => assertionMatchesFilter(diff, getReportAssertionFilter(groupIndex, stepIndex))),
)
const showGroupAssertions = (group, groupIndex, filter) => {
  const steps = Array.isArray(group?.steps) ? group.steps : []
  if (!steps.length) return
  const matchedIndex = steps.findIndex(step => getReportStepAssertionDiffs(step).some(diff => assertionMatchesFilter(diff, filter)))
  const stepIndex = matchedIndex >= 0 ? matchedIndex : 0
  const caseKey = getCaseGroupKey(group, groupIndex)
  const detailKey = getReportDetailKey(groupIndex, stepIndex)
  expandedCaseGroups.value = { ...expandedCaseGroups.value, [caseKey]: true }
  reportDetailTabs.value = {
    ...reportDetailTabs.value,
    [detailKey]: { ...(reportDetailTabs.value[detailKey] || {}), main: 'assertions', assertionFilter: filter },
  }
}

const buildGroupQueryParams = () => {
  const params = {}
  if (groupSearch.value) params.name = groupSearch.value
  if (groupFilter.value) params.status = groupFilter.value
  if (groupCollectionFilter.value.length) {
    params.interface_collection_ids = groupCollectionFilter.value.join(',')
  }
  return params
}

const loadReportGroups = async () => {
  if (!report.value?.id) return
  groupLoading.value = true
  try {
    const params = buildGroupQueryParams()
    const res = await getReportGroupedDetails(report.value.id, groupPage.value, groupPageSize.value, params)
    groups.value = res?.groups || []
    expandedCaseGroups.value = {}
    reportDetailTabs.value = {}
    groupTotal.value = res?.total || 0
    groupStats.value = res?.stats || null
    // 用已生效的查询条件判断，不用输入框的实时值，避免边打字边改卡片文案
    scopeFiltered.value = !!(params.name || params.interface_collection_ids)
    interfaceCollectionTree.value = Array.isArray(res?.collection_tree) ? res.collection_tree : []
    groupLoadError.value = false
  } catch {
    groupLoadError.value = true
  } finally {
    groupLoading.value = false
  }
}

const doGroupSearch = () => {
  groupPage.value = 1
  loadReportGroups()
}
// 统计卡片筛选：卡片只负责状态这一个条件，效果等同于操作上方的状态下拉框，
// 已填的用例名称和接口集条件保留并一起生效，避免用户的筛选被悄悄清掉。
// 再点一次已选中的卡片回到全部状态。
const filterGroupsByStatus = (status) => {
  groupFilter.value = groupFilter.value === status ? '' : status
  groupPage.value = 1
  loadReportGroups()
}
const resetGroupFilters = () => {
  groupSearch.value = ''
  groupFilter.value = ''
  groupCollectionFilter.value = []
  groupPage.value = 1
  loadReportGroups()
}
const handleGroupPageSizeChange = (size) => {
  groupPageSize.value = size
  groupPage.value = 1
  loadReportGroups()
}

const jumpToTestCase = (group) => {
  const testCaseId = Number(group?.test_case_id)
  const interfaceId = Number(group?.interface_id)
  if (!testCaseId || !interfaceId) return
  router.push({
    name: 'InterfaceCases',
    params: { id: projectId.value, iid: interfaceId },
    query: { tc: String(testCaseId) },
  })
}
const canJumpToTestCase = (group) => Boolean(
  group?.test_case_id
  && group?.interface_id
  && !group?.test_case_deleted
  && !group?.interface_deleted,
)
const getCaseLinkText = (group) => {
  if (!group?.test_case_id || group?.test_case_deleted) return '用例已删除'
  if (!group?.interface_id || group?.interface_deleted) return '接口已删除'
  return '用例不可用'
}

const getStatusType = (s) => ({ success: 'success', failed: 'danger', running: '' }[s] || 'info')
const getStatusText = (s) => ({ success: '成功', failed: '失败', running: '运行中' }[s] || s)
const getProgressColor = (p) => {
  p = p || 0
  return p >= 90 ? '#67c23a' : p >= 70 ? '#e6a23c' : '#f56c6c'
}
const formatDate = (d) => d ? formatBeijingTime(d) || '-' : '-'
const channelLabel = (type) => ({
  dingtalk: '钉钉',
  feishu: '飞书',
  wecom: '企业微信',
  webhook: 'Webhook',
}[type] || type || '-')
const formatDuration = (ms) => {
  if (!ms || ms === 0) return '0.00s'
  return (ms / 1000).toFixed(2) + 's'
}
const jsonString = (obj) => {
  if (obj === null || obj === undefined) return '-'
  try { return JSON.stringify(obj, null, 2) } catch { return String(obj) }
}
const formatBody = (body) => {
  if (body === null || body === undefined || body === '') return '-'
  if (typeof body !== 'string') return body
  try { return JSON.parse(body) } catch { return body }
}
// 请求/响应各页签恒定展示，无数据时统一给空串，由详情组件渲染「(无)」，
// 避免报告里出现 {}、[]、- 等多种空值写法
const structuredText = (value) => {
  if (value === null || value === undefined || value === '') return ''
  if (Array.isArray(value) && !value.length) return ''
  if (typeof value === 'object' && !Object.keys(value).length) return ''
  return jsonString(value)
}
const requestBodyText = (body) => {
  const formatted = formatBody(body)
  return formatted === '-' ? '' : jsonString(formatted)
}
const getResponseBody = (responseData) => {
  if (!responseData) return '-'
  if (responseData.json !== null && responseData.json !== undefined) return responseData.json
  return responseData.text || '-'
}
const responseBodyText = (responseData) => {
  const body = getResponseBody(responseData)
  return body === '-' ? '' : formatResponseBody(body)
}
const sortedAssertions = (list) => [...(list || [])].sort((a, b) => (a.result === 'pass') - (b.result === 'pass'))
const formatInterfaceCollection = (item) => item?.interface_collection_name || '未关联接口集'
const formatInterface = (item) => {
  if (!item?.interface_id) return '未关联接口'
  const method = item.interface_method ? `${item.interface_method} ` : ''
  const url = item.interface_url || item.interface_name || ''
  const name = item.interface_name && item.interface_url ? ` ${item.interface_name}` : ''
  return `${method}${url}${name}`.trim()
}
const shouldShowStepError = (step) => {
  const message = step?.error_message || ''
  return !!message && !/^断言失败[:：]\s*\d+\s*个?$/.test(message)
}

const loadReports = async () => {
  loading.value = true
  try {
    const execSetId = route.query.execution_set_id ? parseInt(route.query.execution_set_id) : null
    const extra = {}
    if (searchName.value) extra.name = searchName.value
    const res = await getReports(projectId.value, execSetId, page.value, pageSize.value, filterStatus.value, extra) || { items: [] }
    reportList.value = res.items || []
    total.value = res.total || 0
    listLoadError.value = false
  } catch { listLoadError.value = true }
  finally { loading.value = false }
}

const onPageChange = (val) => {
  page.value = val
  loadReports()
}

const onPageSizeChange = (size) => {
  pageSize.value = size
  page.value = 1
  loadReports()
}

const handleSelectionChange = (rows) => {
  selectedReports.value = rows
}

const handleSelectAll = () => {
  const table = reportTableRef.value
  if (!table) return
  if (selectedReports.value.length === reportList.value.length) {
    table.clearSelection()
  } else {
    reportList.value.forEach(row => table.toggleRowSelection(row, true))
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除报告「${row.name}」？此操作不可恢复。`, '删除确认', {
      confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning'
    })
  } catch { return }
  try {
    await deleteReport(row.id)
    // Toast由后端返回的message自动显示
    loadReports()
  } catch {}
}

const handleBatchDelete = async () => {
  if (selectedReports.value.length === 0) {
    ElMessage.warning('请选择要删除的报告')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将删除 ${selectedReports.value.length} 个报告，此操作不可恢复，确认删除？`,
      '批量删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
  try {
    const res = await batchDeleteReports(selectedReports.value.map(r => r.id))
    // Toast由后端返回的message自动显示
    selectedReports.value = []
    loadReports()
  } catch {}
}

const handleView = async (row) => {
  loading.value = true
  try {
    const r = await getReport(row.id)
    report.value = r
    groups.value = []
    expandedCaseGroups.value = {}
    groupTotal.value = 0
    groupStats.value = null
    scopeFiltered.value = false
    groupSearch.value = ''
    groupFilter.value = ''
    groupCollectionFilter.value = []
    groupPage.value = 1
    groupPageSize.value = 10
    detailVisible.value = true
    router.replace({ query: { report_id: row.id } })
    await loadReportGroups()
  } catch {
    // 权限错误已由统一请求层提示，不能降级打开列表行并再次请求详情。
    return
  } finally {
    loading.value = false
  }
}

// 只收回详情态、不动地址栏：「返回列表」按钮和侧栏导航共用这段
const closeDetail = () => {
  detailVisible.value = false
  report.value = null
  groups.value = []
  expandedCaseGroups.value = {}
  groupTotal.value = 0
  groupStats.value = null
  scopeFiltered.value = false
  groupCollectionFilter.value = []
  interfaceCollectionTree.value = []
}

const goBack = () => {
  closeDetail()
  router.replace({ query: {} })
}

// 详情态跟地址栏的报告参数绑定。侧栏点「测试报告」或浏览器后退时，
// 地址栏参数被清掉但页面组件不会重建，这里主动收回列表，避免点了没反应
watch(() => route.query.report_id, (reportId) => {
  if (!reportId && detailVisible.value) closeDetail()
})

// 发送报告
const handleSendReport = async (row) => {
  try {
    const res = await sendReport(row.id)
    const results = res || []
    const successCount = results.filter(r => r.status === 'success').length
    const failCount = results.filter(r => r.status !== 'success').length

    if (failCount === 0) {
      ElMessage.success(`发送成功：${successCount} 个渠道`)
    } else {
      results.forEach(r => {
        ElNotification({
          title: r.status === 'success' ? '发送成功' : '发送失败',
          message: `${r.channel}: ${r.detail}`,
          type: r.status === 'success' ? 'success' : 'error',
          duration: 6000,
        })
      })
    }
  } catch {}
}

// 发送记录
const sendLogDialogVisible = ref(false)
const sendLogs = ref([])
const sendLogLoading = ref(false)
const sendLogPage = ref(1)
const sendLogPageSize = ref(10)
const currentSendLogReportId = ref(null)

const pagedSendLogs = computed(() => {
  const start = (sendLogPage.value - 1) * sendLogPageSize.value
  return sendLogs.value.slice(start, start + sendLogPageSize.value)
})

const showSendLogs = async (row) => {
  currentSendLogReportId.value = row.id
  sendLogPage.value = 1
  sendLogDialogVisible.value = true
  sendLogLoading.value = true
  sendLogs.value = []
  try {
    const res = await getReportSendLogs(row.id)
    // 补充群名称
    const logs = (res || []).map(l => ({
      ...l,
      group_name: l.group_name || l.channel_name || '-',
    }))
    sendLogs.value = logs
  } catch { sendLogs.value = [] }
  finally { sendLogLoading.value = false }
}

onMounted(() => {
  loadReports()
  const reportId = route.query.report_id
  if (reportId) {
    handleView({ id: parseInt(reportId) })
  }
})
</script>

<style scoped>
.reports-container { height: 100%; min-height: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.card-header h3 { margin: 0; font-size: 20px; font-weight: 600; color: #1a1a1a; }
.card-header-actions { display: flex; gap: 8px; flex-wrap: wrap; }

/* 搜索/筛选栏：小屏可换行，避免按钮溢出裁剪 */
.report-filter-form { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 4px; margin-bottom: 16px; }
.report-filter-form :deep(.el-form-item) { margin: 0 12px 0 0; }
.report-filter-form :deep(.el-form-item:last-child) { margin-right: 0; }

/* 统一操作列背景色 */
:deep(.el-table__fixed-right) {
  box-shadow: none !important;
}
:deep(.el-table__fixed-right-patch) {
  background: transparent !important;
}
:deep(.el-table__fixed-right .el-table__row) {
  background: inherit !important;
}
:deep(.el-table__fixed-right .el-table__row:hover) {
  background: inherit !important;
}

.action-buttons { display: flex; gap: 4px; align-items: center; justify-content: flex-start; }

.report-detail {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  animation: fadeIn .2s ease;
}
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
.report-detail-header {
  display: flex; align-items: center; gap: 16px;
  margin-bottom: 16px; flex-wrap: wrap; flex-shrink: 0;
}
.report-detail-header h3 { margin: 0; }
.report-meta { display: flex; align-items: center; gap: 12px; }
.result-cell { display: flex; align-items: center; gap: 2px; font-size: 13px; }
.clickable-soft {
  border-radius: 6px;
  padding: 2px 8px;
  background: linear-gradient(135deg, rgba(22,119,255,.08), rgba(103,194,58,.08));
  transition: background .18s ease, box-shadow .18s ease, transform .18s ease;
}
.clickable-soft:hover {
  background: linear-gradient(135deg, rgba(22,119,255,.16), rgba(103,194,58,.14));
  box-shadow: 0 2px 8px rgba(22,119,255,.10);
  transform: translateY(-1px);
}
.step-collapse {
  margin-top: 8px;
  border: 1px solid #e5eaf3;
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
}
.step-collapse :deep(.el-collapse-item__header) {
  height: 46px;
  padding: 0 12px;
  background: #f7faff;
  border-bottom: 1px solid #e5eaf3;
  font-weight: 600;
  color: #1677ff;
  cursor: pointer;
  transition: background .18s ease, color .18s ease, box-shadow .18s ease;
}
.step-collapse :deep(.el-collapse-item__header:hover) {
  color: #0d5fc5;
  background: #eef6ff;
  box-shadow: inset 3px 0 0 rgba(22,119,255,.32);
}
.step-collapse :deep(.el-collapse-item__arrow) {
  color: #1677ff;
}
.step-collapse :deep(.el-collapse-item:last-child .el-collapse-item__header) {
  border-bottom: none;
}
.step-collapse :deep(.el-collapse-item.is-active .el-collapse-item__header) {
  border-bottom: 1px solid #e5eaf3;
}
.step-collapse :deep(.el-collapse-item__content) {
  padding: 14px 12px;
  border-bottom: 1px solid #e5eaf3;
}
.step-collapse :deep(.el-collapse-item:last-child .el-collapse-item__content) {
  border-bottom: none;
}
.response-meta { margin-bottom: 10px; color: #606266; font-size: 13px; }
.data-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px; margin-bottom: 10px; }
.data-section { min-width: 0; }
.data-section--wide { grid-column: 1 / -1; }
.data-section-title { font-size: 13px; font-weight: 600; color: #303133; margin-bottom: 6px; }
.nested-collapse { margin-top: 8px; }
.detail-query-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
  padding: 10px 12px;
  align-items: center;
  flex-shrink: 0;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f5f7fa;
  box-sizing: border-box;
}
.report-filter-item { display: flex; align-items: center; flex: 0 0 auto; height: 32px; min-height: 32px; max-height: 32px; margin: 0; }
.report-filter-item :deep(.el-form-item__label) { padding-right: 8px; line-height: 32px; white-space: nowrap; }
.report-filter-item :deep(.el-form-item__content) { display: flex; align-items: center; height: 32px; min-height: 32px; max-height: 32px; }
.report-filter-item--keyword :deep(.el-form-item__content) { width: 240px; min-width: 240px; }
.report-filter-item--status :deep(.el-form-item__content) { width: 110px; min-width: 110px; }
.report-collection-filter-item :deep(.el-form-item__content) { width: 220px; min-width: 220px; max-width: 220px; overflow: visible; }
:global(.report-collection-filter-select) { display: block; width: 220px !important; min-width: 220px; max-width: 220px; height: 32px !important; min-height: 32px !important; max-height: 32px !important; overflow: hidden !important; box-sizing: border-box; }
:global(.report-collection-filter-select .el-input),
:global(.report-collection-filter-select .el-input__wrapper) { width: 220px !important; min-width: 220px !important; max-width: 220px !important; height: 32px !important; min-height: 32px !important; max-height: 32px !important; box-sizing: border-box; }
:global(.report-collection-filter-select .el-cascader__tags) { right: 22px; left: 11px; flex-wrap: nowrap; gap: 4px; overflow: hidden; white-space: nowrap; }
:global(.report-collection-filter-select .el-cascader__tags .el-tag) { flex: 0 0 auto; max-width: 100%; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
:global(.report-collection-cascader-popper .collection-node-label__count) { color: var(--el-color-warning) !important; }
:global(.report-collection-cascader-popper) { max-width: min(720px, calc(100vw - 48px)); }
:global(.report-collection-cascader-popper .el-cascader-panel) { max-width: min(720px, calc(100vw - 48px)); overflow-x: auto; }
:global(.report-collection-cascader-popper .el-cascader-menu) { min-width: 180px; max-height: 320px; }
:global(.report-collection-cascader-popper .el-cascader-menu__wrap) { max-height: 320px; }
:global(.report-collection-cascader-popper .el-cascader-node) { white-space: nowrap; }
.case-list-panel {
  flex: 1;
  min-height: 240px;
  overflow-y: auto;
  padding: 0 14px 2px 0;
  scrollbar-gutter: stable;
  scrollbar-width: auto;
  scrollbar-color: #b8c4d6 #eef2f7;
}
.case-list-panel::-webkit-scrollbar {
  width: 14px;
}
.case-list-panel::-webkit-scrollbar-track {
  background: #eef2f7;
  border-radius: 8px;
}
.case-list-panel::-webkit-scrollbar-thumb {
  background: #b8c4d6;
  border: 3px solid #eef2f7;
  border-radius: 8px;
}
.case-list-panel::-webkit-scrollbar-thumb:hover {
  background: #8fa1ba;
}
.detail-pagination {
  display: flex;
  justify-content: flex-end;
  flex-shrink: 0;
  margin-top: 12px;
  padding: 8px 0 0;
  background: #fff;
}

/* 统计卡片 */
.stats-cards {
  display: flex; gap: 16px; margin-bottom: 16px; flex-shrink: 0;
}
.stat-card {
  flex: 1; min-height: 104px; border-radius: 12px; padding: 16px 20px;
  display: flex; flex-direction: column; gap: 4px;
  position: relative; overflow: hidden;
  background: #fff;
  border: 1px solid #e5eaf3;
  box-shadow: 0 1px 3px rgba(15, 23, 42, .04);
}
.stat-card::after {
  content: ''; position: absolute; right: -20px; top: -20px;
  width: 100px; height: 100px; border-radius: 50%;
  background: rgba(255,255,255,.35); pointer-events: none;
}
.stat-card--total {
  border-color: rgba(22,119,255,.18);
  background: linear-gradient(135deg, #f0f7ff 0%, #e5f1ff 100%);
}
.stat-card--passed {
  border-color: rgba(82,196,26,.18);
  background: linear-gradient(135deg, #f4fbef 0%, #e8f7df 100%);
}
.stat-card--failed {
  border-color: rgba(245,108,108,.18);
  background: linear-gradient(135deg, #fff5f5 0%, #ffeaea 100%);
}
.stat-card--rate {
  border-color: rgba(114,46,209,.18);
  background: linear-gradient(135deg, #faf5ff 0%, #f0e6ff 100%);
}
/* 可点筛选的卡片：button 不继承字体和对齐，需要显式还原成和 div 版一致 */
.stat-card--clickable {
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
  /* 浏览器默认样式会给 button 居中，显式还原成从左上往下排，和静态卡片完全一致 */
  align-items: stretch;
  justify-content: flex-start;
  transition: transform .18s ease;
}
/* 悬浮用位移而不是阴影：阴影要留给下面的选中态内描边，两者会互相覆盖 */
.stat-card--clickable:hover { transform: translateY(-2px); }
.stat-card--clickable:focus-visible { outline: 2px solid #1677ff; outline-offset: 2px; }
/* 选中态用内描边标记，不改边框宽度，避免卡片高度和文字位置抖动 */
.stat-card--total.is-active { box-shadow: inset 0 0 0 2px #0d5fc5; }
.stat-card--passed.is-active { box-shadow: inset 0 0 0 2px #389e0d; }
.stat-card--failed.is-active { box-shadow: inset 0 0 0 2px #cf1322; }
.stat-title {
  font-size: 13px; color: #555; z-index: 1;
}
.stat-value {
  font-size: 36px; font-weight: 700; line-height: 1.2; z-index: 1;
}
.stat-card--total .stat-value { color: #0d5fc5; }
.stat-card--passed .stat-value { color: #389e0d; }
.stat-card--failed .stat-value { color: #cf1322; }
.stat-card--rate .stat-value { color: #531dab; }
.stat-unit {
  font-size: 22px; font-weight: 500; margin-left: 2px;
}
.stat-sub {
  font-size: 12px; color: #777; z-index: 1;
}

/* 用例卡片 */
.groups-section { display: flex; flex-direction: column; gap: 16px; }
.case-card { border-left: 4px solid #e0e0e0; overflow: visible; }
.case-card.case-passed { border-left-color: #67c23a; }
.case-card.case-failed { border-left-color: #f56c6c; }
.case-card.is-expanded :deep(.el-card__header) {
  position: sticky;
  top: 0;
  z-index: 5;
  background: #fff;
  box-shadow: 0 2px 8px rgba(15, 23, 42, .08);
}
.case-card-header {
  display: flex; justify-content: space-between; align-items: center;
  gap: 12px;
  cursor: pointer;
  user-select: none;
}
.case-card-header:hover .case-expand-icon {
  color: #1677ff;
  background: #eef6ff;
}
.case-title-area {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 8px;
  flex: 1;
}
.case-expand-icon {
  flex-shrink: 0;
  color: #909399;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  transition: background .18s ease, color .18s ease;
}
.report-list-table :deep(.el-table__header .cell),
.report-list-table :deep(.el-table__body .cell) {
  white-space: nowrap;
}
.report-list-table :deep(.el-table__body .cell) {
  overflow: hidden;
  text-overflow: ellipsis;
}
.report-list-table :deep(.el-table__body .cell .el-link) {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.case-name { display: flex; align-items: center; flex: 0 1 auto; min-width: 0; overflow: hidden; font-weight: 600; font-size: 15px; }
.case-name-text { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.case-link-button { flex-shrink: 0; white-space: nowrap; }
.case-link-button--disabled {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #909399;
  cursor: not-allowed;
}
.clickable-title {
  cursor: pointer;
  min-width: 0;
  max-width: 100%;
  padding: 5px 8px;
  border-radius: 6px;
  background: linear-gradient(135deg, rgba(22,119,255,.08), rgba(103,194,58,.08));
  transition: background .18s ease, box-shadow .18s ease, transform .18s ease;
}
.clickable-title:hover {
  color: #1677ff;
  background: linear-gradient(135deg, rgba(22,119,255,.16), rgba(103,194,58,.14));
  box-shadow: 0 2px 10px rgba(22,119,255,.10);
  transform: translateY(-1px);
}
.case-header-metrics {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-shrink: 0;
}
.case-status-pill,
.step-status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 24px;
  min-width: 44px;
  padding: 0 10px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 600;
}
.case-status-pill.is-passed,
.step-status-pill.is-passed {
  color: #389e0d;
  background: #f0f9eb;
  border: 1px solid #d9f7be;
}
.case-status-pill.is-failed,
.step-status-pill.is-failed {
  color: #f56c6c;
  background: #fef0f0;
  border: 1px solid #fbc4c4;
}
/* 用例摘要 */
.case-body { padding-top: 2px; }
.case-summary {
  padding: 8px 0 12px;
}
.case-summary-grid {
  display: grid;
  grid-template-columns: 120px 120px 120px minmax(180px, 1fr) minmax(260px, 2fr);
  gap: 8px;
}
.summary-metric {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid #e5eaf3;
  border-radius: 6px;
  background: #f8fafc;
}
.assertion-summary-button {
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color .18s ease, box-shadow .18s ease, background .18s ease;
}
.assertion-summary-button:hover,
.assertion-summary-button:focus-visible {
  border-color: #91caff;
  background: #f7fbff;
  box-shadow: 0 2px 8px rgba(22, 119, 255, .08);
}
.assertion-summary-button:focus-visible { outline: 2px solid #1677ff; outline-offset: 2px; }
.summary-label {
  display: block;
  margin-bottom: 4px;
  color: #909399;
  font-size: 12px;
}
.summary-value {
  color: #303133;
  font-size: 16px;
  line-height: 1.2;
  font-weight: 700;
}
.summary-value.success { color: #67c23a; }
.summary-value.danger { color: #f56c6c; }
.summary-text {
  display: block;
  color: #303133;
  font-size: 13px;
  line-height: 1.4;
  word-break: break-all;
}
.case-stat { font-size: 13px; color: #606266; }

/* 步骤块 */
.step-block { margin-bottom: 12px; padding: 8px; background: #fafafa; border-radius: 6px; }
.step-bar {
  display: flex; justify-content: space-between; align-items: center;
  gap: 12px;
  padding: 8px 10px; border-radius: 4px;
}
.step-bar.step-success { background: #f0f9eb; }
.step-bar.step-failed { background: #fef0f0; }
.step-bar-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.step-num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 50%;
  background: #1677ff; color: #fff; font-size: 12px; font-weight: 600;
  flex-shrink: 0;
}
.step-name { flex: 1; font-weight: 500; font-size: 14px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.step-metrics {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-shrink: 0;
}
.step-metric {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}
.step-metric.warn { color: #e6a23c; }
.step-error { margin: 8px 0; }
.step-detail-panel {
  margin-top: 8px;
  border: 1px solid #e5eaf3;
  border-radius: 6px;
  background: #fff;
  overflow: hidden;
}
.execution-result-header {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 10px 14px; border-bottom: 1px solid #e5eaf3; background: #f7f9fc;
}
.execution-result-title { min-width: 0; display: flex; align-items: center; gap: 8px; }
.execution-method {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 42px; height: 24px; padding: 0 8px; border-radius: 4px;
  background: #67c23a; color: #fff; font-size: 12px; font-weight: 600;
}
.execution-result-title strong { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #303133; font-size: 14px; }
.execution-case-name { flex-shrink: 0; color: #606266; font-size: 12px; }
.step-tabs :deep(.el-tabs__header) {
  margin: 0;
  padding: 0 14px;
  background: #f7faff;
  border-bottom: 1px solid #e5eaf3;
}
.step-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}
.step-tabs :deep(.el-tabs__item) {
  height: 44px;
  color: #606266;
  font-weight: 500;
}
.step-tabs :deep(.el-tabs__item.is-active) {
  color: #1677ff;
}
.step-tabs :deep(.el-tabs__active-bar) {
  background: #1677ff;
}
.step-tabs :deep(.el-tabs__content) {
  padding: 14px;
}
.meta-strip {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(140px, .6fr) minmax(160px, .8fr);
  gap: 10px;
  margin-bottom: 12px;
}
.meta-item {
  min-width: 0;
  padding: 9px 10px;
  border: 1px solid #edf1f7;
  border-radius: 6px;
  background: #fafcff;
}
.meta-label {
  display: block;
  margin-bottom: 4px;
  color: #909399;
  font-size: 12px;
}
.meta-value {
  color: #303133;
  font-size: 13px;
  word-break: break-all;
}
.http-status {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 5px;
  font-size: 13px;
  color: #606266;
  background: #f4f4f5;
}
.http-status.is-success {
  color: #389e0d;
  background: #f0f9eb;
}
.http-status.is-warn {
  color: #b7791f;
  background: #fdf6ec;
}
.http-status.is-error {
  color: #cf1322;
  background: #fef0f0;
}

.empty-inline {
  padding: 22px;
  color: #909399;
  text-align: center;
  background: #fafafa;
  border-radius: 6px;
}
.assert-item {
  padding: 10px; margin-bottom: 8px; border-radius: 6px;
  border: 1px solid #e8e8e8;
}
.assert-item.assert-pass { border-left: 3px solid #67c23a; }
.assert-item.assert-fail { border-left: 3px solid #f56c6c; background: #fef0f0; }
.assert-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.assert-title { font-size: 13px; font-weight: 500; flex: 1; }
.assert-body { padding-left: 22px; }
.assert-row { display: flex; gap: 8px; margin: 3px 0; font-size: 12px; }
.assert-label { color: #909399; min-width: 50px; }
.assert-val { font-family: monospace; word-break: break-all; }
.expected-val { color: #1677ff; }
.actual-pass { color: #67c23a; }
.actual-fail { color: #f56c6c; }

/* 通用 */
.code-block {
  max-height: 280px; overflow: auto; background: #f5f7fa;
  padding: 10px; border-radius: 4px; font-size: 12px;
  white-space: pre-wrap; word-break: break-all; margin: 0;
  font-family: SFMono-Regular, Consolas, monospace;
}
.code-block--response {
  max-height: 260px;
  overflow: auto;
  white-space: pre;
  word-break: normal;
}
.log-block {
  max-height: 200px; overflow: auto; background: #1e1e1e; color: #d4d4d4;
  padding: 10px; border-radius: 4px; font-size: 12px;
}
.load-error { margin: 8px 0 12px; color: #f56c6c; display: flex; align-items: center; gap: 8px; }

/* 弹窗：自适应屏幕高度 */
:deep(.el-dialog) { display: flex; flex-direction: column; max-height: min(90vh, 750px); }
:deep(.el-dialog__body) { flex: 1; overflow-y: auto; padding: 20px 28px; }
:deep(.send-log-dialog.el-dialog) { width: min(760px, calc(100vw - 48px)) !important; }
.send-log-table :deep(.cell) { white-space: nowrap; }
.send-log-time { white-space: nowrap; }

/* 移动端适配 */
@media (max-width: 768px) {
  .el-row { flex-direction: column !important; }
  .el-row .el-col { max-width: 100% !important; flex: 0 0 100% !important; margin-bottom: 12px; }
  .el-dialog { width: 95vw !important; max-width: 95vw !important; }
  .el-table { font-size: 13px; overflow-x: auto; display: block; }
  .el-pagination { justify-content: center !important; }
  .card-header, .list-header, .tree-header { flex-direction: column; align-items: flex-start; gap: 8px; }
  .header-actions, .tree-header-actions { flex-wrap: wrap; }
  .case-card-header, .step-bar { align-items: flex-start; flex-direction: column; }
  .execution-result-header { align-items: flex-start; flex-direction: column; }
  .case-header-metrics, .step-metrics { justify-content: flex-start; flex-wrap: wrap; }
  .case-summary-grid { grid-template-columns: 1fr; }
}
</style>
