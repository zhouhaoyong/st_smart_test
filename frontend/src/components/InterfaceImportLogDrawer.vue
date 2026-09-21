<template>
  <el-dialog
    :model-value="modelValue"
    title="操作记录"
    width="min(760px, calc(100vw - 48px))"
    align-center
    destroy-on-close
    class="interface-import-log-dialog"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="dialog-body" v-loading="loading">
      <div class="log-filter-bar">
        <el-select v-model="filterForm.operationType" clearable placeholder="全部操作" class="log-filter-operation">
          <el-option v-for="item in OPERATION_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select
          v-model="filterForm.userId"
          clearable
          filterable
          placeholder="全部操作人"
          class="log-filter-user"
          :loading="operatorLoading"
        >
          <el-option v-for="item in operatorOptions" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-date-picker
          v-model="filterForm.dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          format="YYYY-MM-DD"
          class="log-filter-date"
        />
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>
      <div class="dialog-scroll-content">
        <el-alert
          v-if="errorMessage"
          :title="errorMessage"
          type="error"
          show-icon
          :closable="false"
          class="load-error"
        >
          <el-button link type="danger" @click="loadLogs">重试</el-button>
        </el-alert>

        <div v-if="!loading && !errorMessage && !logs.length" class="log-empty">
          <GlobalEmpty text="暂无操作记录" />
        </div>

        <el-timeline v-else-if="logs.length" class="import-log-timeline">
          <el-timeline-item
            v-for="log in logs"
            :key="log.id"
            :type="timelineType(log.status)"
            :timestamp="formatBeijingTime(log.created_at)"
            placement="top"
          >
            <div class="log-card">
              <div class="log-card-header">
                <div class="log-title-line">
                  <el-tag :type="sourceTagType(log.source)" size="small" effect="light">
                    {{ sourceLabel(log.source) }}
                  </el-tag>
                  <span class="log-operator">
                    <UserAvatar :size="18" :src="log.user_avatar" :name="log.user_name" :user-id="log.user_id" />
                    <span class="log-operator-name">{{ log.user_name || '未知用户' }}</span>
                  </span>
                </div>
                <el-tag :type="statusTagType(log.status)" size="small" effect="plain">
                  {{ statusLabel(log.status) }}
                </el-tag>
              </div>

              <div class="log-source-name" v-if="displaySourceName(log.source_name)">
                {{ displaySourceName(log.source_name) }}
              </div>
              <div class="log-summary" :title="summaryLabel(log)">{{ summaryLabel(log) }}</div>

              <div class="log-counts">
                <template v-if="isInterfaceDeleteLog(log)">
                  <button type="button" class="log-count-link" @click="openDeleteItems(log, 'interfaces')">
                    接口：删除 {{ interfaceCount(log) }} 个
                  </button>
                  <button type="button" class="log-count-link" @click="openDeleteItems(log, 'cases')">
                    用例：删除 {{ caseCount(log) }} 个
                  </button>
                  <span v-if="executionItemCount(log) > 0">执行项：删除 {{ executionItemCount(log) }} 个</span>
                </template>
                <template v-else-if="isCaseDeleteLog(log)">
                  <button type="button" class="log-count-link" @click="openDeleteItems(log, 'cases')">
                    用例：删除 {{ caseCount(log) }} 个
                  </button>
                  <span v-if="executionItemCount(log) > 0">执行项：删除 {{ executionItemCount(log) }} 个</span>
                </template>
                <template v-else-if="isAiGenerationLog(log)">
                  <span>用例：新增 {{ generatedCaseCount(log) }} 个</span>
                  <span v-if="preservedCaseCount(log) > 0">用例：保留 {{ preservedCaseCount(log) }} 个</span>
                </template>
                <template v-else>
                  <span>接口：新增 {{ newInterfaceCount(log) }} 个，更新 {{ updatedInterfaceCount(log) }} 个</span>
                  <span>用例：新增 {{ newCaseCount(log) }} 个，更新 {{ updatedCaseCount(log) }} 个</span>
                </template>
              </div>

              <button
                v-if="log.source === 'ai'"
                type="button"
                class="ai-choice-link"
                @click="openAiChoice(log)"
              >
                查看 AI 导入选择
              </button>
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>

      <el-pagination
        v-if="total > 0"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="[10, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        class="log-pagination"
        @current-change="handlePageChange"
        @size-change="handlePageSizeChange"
      />
    </div>
  </el-dialog>

  <el-dialog
    v-model="detailVisible"
    :title="detailTitle"
    width="min(760px, calc(100vw - 32px))"
    append-to-body
    align-center
    destroy-on-close
    class="interface-delete-detail-dialog"
  >
    <div class="detail-content" v-loading="detailLoading">
      <div class="detail-toolbar">
        <el-input
          v-model="detailKeyword"
          clearable
          :placeholder="detailType === 'interfaces' ? '按接口名称、方法或 URL 查询' : '按用例名称或所属接口查询'"
          @keyup.enter="queryDeleteItems"
        />
        <el-button type="primary" @click="queryDeleteItems">查询</el-button>
      </div>

      <el-alert
        v-if="detailError"
        :title="detailError"
        type="error"
        show-icon
        :closable="false"
        class="detail-error"
      />

      <el-table v-else :data="detailItems" border size="small" max-height="420" class="detail-table">
        <template #empty>
          <GlobalEmpty />
        </template>
        <el-table-column v-if="detailType === 'interfaces'" prop="name" label="接口名称" min-width="160" show-overflow-tooltip />
        <el-table-column v-if="detailType === 'interfaces'" prop="method" label="方法" width="84" />
        <el-table-column v-if="detailType === 'interfaces'" prop="url" label="URL" min-width="230" show-overflow-tooltip />
        <el-table-column v-if="detailType !== 'interfaces'" prop="name" label="用例名称" min-width="190" show-overflow-tooltip />
        <el-table-column v-if="detailType !== 'interfaces'" prop="interface_name" label="所属接口" min-width="160" show-overflow-tooltip />
        <el-table-column v-if="detailType !== 'interfaces'" label="优先级" width="90">
          <template #default="{ row }">{{ priorityLabel(row.priority) }}</template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="detailTotal > detailPageSize"
        v-model:current-page="detailPage"
        v-model:page-size="detailPageSize"
        :page-sizes="[10, 50, 100]"
        :total="detailTotal"
        layout="total, sizes, prev, pager, next"
        class="detail-pagination"
        @size-change="handleDetailSizeChange"
        @current-change="handleDetailPageChange"
      />
    </div>
  </el-dialog>

  <el-dialog
    v-model="aiChoiceVisible"
    title="AI 导入选择"
    width="min(560px, calc(100vw - 32px))"
    append-to-body
    align-center
    destroy-on-close
    class="ai-import-choice-dialog"
  >
    <el-descriptions :column="1" border size="small">
      <el-descriptions-item label="第一步">
        {{ analysisScopeLabel(aiChoiceLog?.details?.analysis_scope) }}
      </el-descriptions-item>
      <el-descriptions-item label="分析接口">
        {{ aiChoiceLog?.details?.analysis_interface_count ?? 0 }} 个
      </el-descriptions-item>
      <el-descriptions-item label="第三步">
        {{ generationModeLabel(aiChoiceLog?.details?.generation_mode) }}
        <span v-if="aiChoiceLog?.details?.generation_target_count != null">
          （{{ aiChoiceLog.details.generation_target_count }} 个接口）
        </span>
      </el-descriptions-item>
      <el-descriptions-item label="第四步">
        {{ saveStrategyLabel(aiChoiceLog?.details?.save_strategy) }}
      </el-descriptions-item>
    </el-descriptions>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { getInterfaceImportLogs, getInterfaceImportLogItems, getInterfaceImportLogOperators } from '@/api/interfaces'
import { formatBeijingTime } from '@/utils/beijingTime'
import GlobalEmpty from '@/components/GlobalEmpty.vue'
import UserAvatar from '@/components/UserAvatar.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  projectId: { type: [Number, String], required: true },
})

const emit = defineEmits(['update:modelValue'])

const pageSize = ref(10)
const page = ref(1)
const total = ref(0)
const logs = ref([])
const loading = ref(false)
const errorMessage = ref('')
const operatorLoading = ref(false)
const operatorOptions = ref([])
const filterForm = ref({ operationType: '', userId: null, dateRange: null })
const appliedFilters = ref({ operationType: '', userId: null, dateRange: null })
const detailVisible = ref(false)
const detailLog = ref(null)
const aiChoiceVisible = ref(false)
const aiChoiceLog = ref(null)
const detailType = ref('interfaces')
const detailPage = ref(1)
const detailPageSize = ref(10)
const detailTotal = ref(0)
const detailItems = ref([])
const detailKeyword = ref('')
const detailLoading = ref(false)
const detailError = ref('')
let detailRequestSeq = 0

const SOURCE_LABELS = {
  file: '文件导入',
  curl: 'cURL 导入',
  ai: '历史接口导入',
  delete: '接口删除',
  case_delete_all: '用例删除',
  ai_generate: 'AI生成用例',
}
const OPERATION_OPTIONS = [
  { value: 'file', label: '文件导入' },
  { value: 'curl', label: 'cURL 导入' },
  { value: 'ai_import', label: '历史接口导入' },
  { value: 'ai_generate', label: 'AI生成用例' },
  { value: 'interface_delete', label: '接口删除' },
  { value: 'case_delete', label: '用例删除' },
]
const STATUS_LABELS = {
  success: '成功',
  partial: '部分成功',
  failed: '失败',
}
const PRIORITY_LABELS = {
  high: '高',
  medium: '中',
  low: '低',
}
const ANALYSIS_SCOPE_LABELS = {
  full: '全量解析',
  incremental: '增量解析',
  unknown: '未记录',
}
const GENERATION_MODE_LABELS = {
  main: '主流程',
  normal: '常规覆盖',
  full: '全面覆盖',
  skip: '仅保存接口',
  unknown: '未记录',
}
const SAVE_STRATEGY_LABELS = {
  skip: '仅导入新增接口用例',
  append_cases: '全部接口新增用例',
  append_duplicate_cases: '仅追加重复接口用例',
  unknown: '未记录',
}

const detailTitle = computed(() => detailType.value === 'interfaces' ? '删除接口明细' : '删除用例明细')

function sourceLabel(source) {
  return SOURCE_LABELS[source] || '接口导入'
}

function statusLabel(status) {
  return STATUS_LABELS[status] || '未知'
}

function priorityLabel(priority) {
  const value = String(priority || '').trim().toLowerCase()
  return PRIORITY_LABELS[value] || priority || '—'
}

function sourceTagType(source) {
  return {
    file: 'primary', curl: 'warning', ai: 'warning', delete: 'danger',
    case_delete_all: 'danger', ai_generate: 'success',
  }[source] || 'info'
}

function statusTagType(status) {
  return { success: 'success', partial: 'warning', failed: 'danger' }[status] || 'info'
}

function timelineType(status) {
  return { success: 'success', partial: 'warning', failed: 'danger' }[status] || 'primary'
}

function displaySourceName(value) {
  const text = String(value || '').trim()
  return text.startsWith('ai_import:') ? text.slice('ai_import:'.length) : text
}

function isDeleteLog(log) {
  return isInterfaceDeleteLog(log) || isCaseDeleteLog(log)
}

function isInterfaceDeleteLog(log) {
  return log?.record_type === 'interface_delete' || log?.source === 'delete'
}

function isCaseDeleteLog(log) {
  return log?.record_type === 'case_delete_all' || log?.source === 'case_delete_all'
}

function isAiGenerationLog(log) {
  return log?.record_type === 'interface_case_generate' || log?.source === 'ai_generate'
}

function reportOf(log) {
  return log?.details?.report && typeof log.details.report === 'object'
    ? log.details.report
    : log?.details || {}
}

function interfaceCount(log) {
  const details = log?.details || {}
  if (isDeleteLog(log)) return details.interface_count ?? details.deleted_interfaces ?? 0
  const report = reportOf(log)
  return details.interface_count ?? details.imported_interfaces ?? report.interface_count
    ?? ((report.new_interfaces || 0) + (report.updated_interfaces || 0))
    ?? 0
}

function newInterfaceCount(log) {
  const report = reportOf(log)
  return report.new_interfaces ?? 0
}

function updatedInterfaceCount(log) {
  const report = reportOf(log)
  return report.updated_interfaces ?? 0
}

function caseCount(log) {
  const details = log?.details || {}
  if (isDeleteLog(log)) return details.case_count ?? details.deleted_cases ?? 0
  const report = reportOf(log)
  return report.new_test_cases ?? details.created_cases ?? 0
}

function executionItemCount(log) {
  const details = log?.details || {}
  return details.execution_item_count ?? 0
}

function newCaseCount(log) {
  return isDeleteLog(log) ? 0 : caseCount(log)
}

function updatedCaseCount(log) {
  if (isDeleteLog(log)) return 0
  const report = reportOf(log)
  return report.updated_test_cases ?? detailsOf(log).updated_test_cases ?? 0
}

function generatedCaseCount(log) {
  const details = detailsOf(log)
  return details.new_case_count ?? details.generated_cases ?? 0
}

function preservedCaseCount(log) {
  return detailsOf(log).preserved_case_count ?? 0
}

function detailsOf(log) {
  return log?.details || {}
}

function summaryLabel(log) {
  if (log?.summary) return log.summary
  if (isInterfaceDeleteLog(log)) return `接口：删除 ${interfaceCount(log)} 个；用例：删除 ${caseCount(log)} 个`
  if (isCaseDeleteLog(log)) return `删除当前接口下用例 ${caseCount(log)} 条`
  if (isAiGenerationLog(log)) return `AI生成用例：新增 ${generatedCaseCount(log)} 个`
  return '接口导入完成'
}

function analysisScopeLabel(value) {
  return ANALYSIS_SCOPE_LABELS[value] || '未记录'
}

function generationModeLabel(value) {
  return GENERATION_MODE_LABELS[value] || '未记录'
}

function saveStrategyLabel(value) {
  return SAVE_STRATEGY_LABELS[value] || '未记录'
}

function resetDetail() {
  detailRequestSeq += 1
  detailLog.value = null
  detailType.value = 'interfaces'
  detailPage.value = 1
  detailPageSize.value = 10
  detailTotal.value = 0
  detailItems.value = []
  detailKeyword.value = ''
  detailLoading.value = false
  detailError.value = ''
}

function cloneDateRange(value) {
  return Array.isArray(value) ? value.map(item => item ? new Date(item) : item) : null
}

function cloneFilters(value) {
  return {
    operationType: value.operationType || '',
    userId: value.userId || null,
    dateRange: cloneDateRange(value.dateRange),
  }
}

function buildFilterParams() {
  const filters = appliedFilters.value
  const params = {}
  if (filters.operationType) params.operation_type = filters.operationType
  if (filters.userId) params.user_id = filters.userId
  if (filters.dateRange?.length === 2) {
    params.start_time = formatBeijingTime(filters.dateRange[0])
    params.end_time = `${formatBeijingTime(filters.dateRange[1]).slice(0, 10)} 23:59:59`
  }
  return params
}

function openDeleteItems(log, itemType) {
  detailLog.value = log
  detailType.value = itemType
  detailPage.value = 1
  detailPageSize.value = 10
  detailKeyword.value = ''
  detailVisible.value = true
  queryDeleteItems()
}

function openAiChoice(log) {
  aiChoiceLog.value = log
  aiChoiceVisible.value = true
}

async function queryDeleteItems() {
  if (!detailLog.value || !props.projectId) return
  const requestSeq = ++detailRequestSeq
  const requestProjectId = Number(props.projectId)
  const requestLogId = detailLog.value.id
  const requestItemType = detailType.value
  detailLoading.value = true
  detailError.value = ''
  try {
    const data = await getInterfaceImportLogItems(
      requestProjectId,
      requestLogId,
      requestItemType,
      detailPage.value,
      detailPageSize.value,
      detailKeyword.value,
    )
    if (
      requestSeq !== detailRequestSeq
      || !detailVisible.value
      || Number(props.projectId) !== requestProjectId
      || detailLog.value?.id !== requestLogId
      || detailType.value !== requestItemType
    ) return
    detailItems.value = Array.isArray(data?.items) ? data.items : []
    detailTotal.value = Number(data?.total || 0)
  } catch (error) {
    if (requestSeq !== detailRequestSeq) return
    detailItems.value = []
    detailTotal.value = 0
    detailError.value = error?.data?.message || error?.message || '明细加载失败，请重试'
  } finally {
    if (requestSeq === detailRequestSeq) detailLoading.value = false
  }
}

function handleDetailSizeChange(size) {
  detailPageSize.value = size
  detailPage.value = 1
  queryDeleteItems()
}

function handleDetailPageChange(pageNumber) {
  detailPage.value = pageNumber
  queryDeleteItems()
}

async function loadLogs() {
  if (!props.projectId) return
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await getInterfaceImportLogs(Number(props.projectId), page.value, pageSize.value, buildFilterParams())
    logs.value = Array.isArray(data?.items) ? data.items : []
    total.value = Number(data?.total || 0)
  } catch (error) {
    logs.value = []
    total.value = 0
    errorMessage.value = error?.data?.message || error?.message || '操作记录加载失败，请重试'
  } finally {
    loading.value = false
  }
}

async function loadOperators() {
  if (!props.projectId) return
  operatorLoading.value = true
  try {
    const data = await getInterfaceImportLogOperators(Number(props.projectId))
    operatorOptions.value = Array.isArray(data?.items) ? data.items : []
  } catch {
    operatorOptions.value = []
  } finally {
    operatorLoading.value = false
  }
}

function handleSearch() {
  appliedFilters.value = cloneFilters(filterForm.value)
  page.value = 1
  loadLogs()
}

function handleReset() {
  filterForm.value = { operationType: '', userId: null, dateRange: null }
  handleSearch()
}

function handlePageChange(pageNumber) {
  page.value = pageNumber
  loadLogs()
}

function handlePageSizeChange(size) {
  pageSize.value = size
  page.value = 1
  loadLogs()
}

watch(() => props.modelValue, (visible) => {
  if (visible) {
    page.value = 1
    filterForm.value = { operationType: '', userId: null, dateRange: null }
    appliedFilters.value = cloneFilters(filterForm.value)
    loadOperators()
    loadLogs()
  } else {
    detailVisible.value = false
    aiChoiceVisible.value = false
    resetDetail()
  }
})

watch(detailVisible, (visible) => {
  if (!visible) resetDetail()
})

watch(aiChoiceVisible, (visible) => {
  if (!visible) aiChoiceLog.value = null
})

watch(() => props.projectId, () => {
  if (props.modelValue) {
    loadOperators()
    loadLogs()
  }
  if (detailVisible.value) detailVisible.value = false
})
</script>

<style scoped>
.dialog-body {
  min-height: 260px;
  height: min(620px, calc(100vh - 168px));
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.dialog-scroll-content { flex: 1; min-height: 0; min-width: 0; overflow-y: auto; }
.log-filter-bar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  min-width: 0;
  overflow-x: auto;
  gap: 8px;
  margin: 0 4px 4px;
  padding: 0 0 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.log-filter-operation,
.log-filter-user,
.log-filter-date,
.log-filter-bar > .el-button { flex: 0 0 auto; }
.log-filter-operation { width: 150px; }
.log-filter-user { width: 140px; }
.log-filter-date { width: 250px; }
.load-error { margin-bottom: 14px; }
.log-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  box-sizing: border-box;
}
.import-log-timeline { padding: 8px 10px 0 4px; }
.log-card {
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-bg-color);
}
.log-card-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.log-title-line { display: flex; align-items: center; gap: 12px; min-width: 0; }
.log-title-line strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--el-text-color-primary); }
.log-operator { display: inline-flex; align-items: center; gap: 5px; color: var(--el-text-color-secondary); font-size: 12px; }
.log-operator-name { max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.log-source-name { margin-top: 8px; color: var(--el-text-color-secondary); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.log-summary { margin-top: 8px; color: var(--el-text-color-primary); font-size: 13px; line-height: 1.5; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.log-counts { display: flex; flex-wrap: nowrap; min-width: 0; overflow: hidden; gap: 8px 14px; margin-top: 10px; color: var(--el-text-color-secondary); font-size: 12px; }
.log-counts > * { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.log-count-link { padding: 0; border: 0; background: transparent; color: var(--el-color-primary); font: inherit; cursor: pointer; }
.log-count-link:hover { color: var(--el-color-primary-light-3); text-decoration: underline; }
.ai-choice-link { display: inline-flex; align-items: center; margin-top: 10px; padding: 0; border: 0; background: transparent; color: var(--el-color-primary); font: inherit; font-size: 12px; cursor: pointer; }
.ai-choice-link:hover { color: var(--el-color-primary-light-3); text-decoration: underline; }
.log-pagination { justify-content: flex-end; margin: auto 0 0; padding: 14px 4px 0; }
.detail-content { min-height: 180px; min-width: 0; }
.detail-toolbar { display: flex; gap: 10px; min-width: 0; }
.detail-toolbar .el-input { flex: 1; min-width: 0; }
.detail-error { margin-top: 14px; }
.detail-table { width: 100%; margin-top: 14px; }
.detail-pagination { justify-content: flex-end; margin-top: 14px; }
</style>
