<template>
  <el-dialog v-model="visible" :title="title" width="min(920px, calc(100vw - 48px))" :close-on-click-modal="false" align-center class="debug-dialog" @close="$emit('close')">
    <!-- 调试模式：请求栏 -->
    <div class="debug-hero" v-if="method">
      <div class="request-line">
        <el-tag :type="methodType" size="large" effect="dark" class="method-tag">{{ method }}</el-tag>
        <span class="debug-url">{{ fullUrl || requestUrl }}</span>
      </div>
      <div class="debug-actions">
        <el-button type="primary" @click="$emit('send')" :loading="loading">再次调试</el-button>
        <el-button @click="copyCurl">复制 cURL</el-button>
      </div>
    </div>

    <div v-if="loading && (!steps || !steps.length)" class="debug-loading" role="status" aria-live="polite">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在运行用例…</span>
    </div>

    <!-- 断言结果（运行模式） -->
    <div v-if="steps && steps.length" class="run-summary">
      <button type="button" :class="['summary-item', 'assertion-summary-item', { 'is-active': assertionFilter === 'all' }]" @click="showAssertions('all')">
        <span class="summary-label">总断言</span>
        <strong>{{ assertionTotal }}</strong>
      </button>
      <button type="button" :class="['summary-item', 'assertion-summary-item', 'success', { 'is-active': assertionFilter === 'passed' }]" @click="showAssertions('passed')">
        <span class="summary-label">断言通过</span>
        <strong>{{ assertionPassedCount }}</strong>
      </button>
      <button type="button" :class="['summary-item', 'assertion-summary-item', 'danger', { 'is-active': assertionFilter === 'failed' }]" @click="showAssertions('failed')">
        <span class="summary-label">未通过</span>
        <strong>{{ assertionFailedCount }}</strong>
      </button>
    </div>

    <el-table v-if="steps && steps.length" :data="steps" stripe size="small" class="run-table" highlight-current-row @current-change="onStepSelect">
      <el-table-column type="index" label="#" width="40" />
      <el-table-column label="接口名称" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">{{ row.interfaceName || row.name || '-' }}</template>
      </el-table-column>
      <el-table-column v-if="hasCaseNames" label="用例名称" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ row.caseName || '-' }}</template>
      </el-table-column>
      <el-table-column label="状态码" width="75">
        <template #default="{ row }">{{ row.statusCode || '-' }}</template>
      </el-table-column>
      <el-table-column label="耗时" width="80">
        <template #default="{ row }">{{ row.duration != null ? `${row.duration}ms` : '-' }}</template>
      </el-table-column>
      <el-table-column label="执行结果" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'success' ? 'success' : row.status === 'error' ? 'warning' : 'danger'" size="small">
            {{ row.status === 'success' ? '通过' : row.status === 'error' ? '错误' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="断言结果" min-width="120">
        <template #default="{ row }">
          <el-button
            v-if="getStepAssertionDiffs(row).length"
            link
            :type="getStepAssertionSummary(row).failed ? 'danger' : 'success'"
            class="assertion-link"
            @click.stop="showStepAssertions(row)"
          >查看 {{ getStepAssertionDiffs(row).length }} 条断言</el-button>
          <span v-else style="color:#909399">无断言</span>
        </template>
      </el-table-column>
    </el-table>

    <!-- 选中步骤的请求/响应详情 -->
    <template v-if="selectedStep && (selectedStep.request || selectedStep.response)">
      <div class="execution-result-header">
        <div class="execution-result-title">
          <el-tag v-if="selectedStep.request?.method" :type="methodTypeFor(selectedStep.request.method)" size="small" effect="dark" class="method-tag">
            {{ selectedStep.request.method }}
          </el-tag>
          <strong>{{ selectedStep.interfaceName || selectedStep.name || '接口请求' }}</strong>
        </div>
        <span v-if="selectedStep.caseName" class="execution-case-name">用例：{{ selectedStep.caseName }}</span>
      </div>
      <el-tabs v-model="stepTab" class="panel-tabs">
        <el-tab-pane label="请求信息" name="req">
          <ExecutionRequestDetail
            v-model:active-tab="stepRequestTab"
            :method="selectedStep.request?.method"
            :request-url="selectedStep.request?.url"
            :params-text="stepReqParamsText"
            :path-params-text="stepReqPathParamsText"
            :body-text="stepReqBodyText"
            :headers-text="stepReqHeadersText"
            :proxy-text="stepProxyText"
            :service="selectedStep.request?.service"
          />
        </el-tab-pane>
        <el-tab-pane label="响应结果" name="resp">
          <ExecutionResponseDetail
            v-model:active-tab="stepResponseTab"
            :body-text="stepRespBodyText"
            :headers-text="stepRespHeadersText"
          >
            <template #body>
              <el-input :model-value="stepRespBodyText" type="textarea" :rows="10" readonly class="code-input" />
            </template>
          </ExecutionResponseDetail>
        </el-tab-pane>
        <el-tab-pane label="断言结果" name="assertions">
          <AssertionDiffTable
            :diffs="selectedAssertionDiffs"
            :empty-text="assertionFilter === 'all' ? '暂无断言结果' : '暂无对应断言结果'"
          />
        </el-tab-pane>
        <el-tab-pane label="脚本日志" name="logs">
          <pre class="code-block">{{ selectedStep.logs || '(无)' }}</pre>
        </el-tab-pane>
      </el-tabs>
    </template>

    <!-- 错误信息 -->
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" style="margin-bottom:12px" />

    <!-- 调试模式：请求/响应标签页 -->
    <div v-if="method && hasResponseMeta" class="response-summary">
      <div class="summary-card">
        <span>状态码</span>
        <el-tag v-if="statusCode" class="status-code-tag" :type="statusType" effect="plain">{{ statusCode }}</el-tag>
        <strong v-else>-</strong>
      </div>
      <div class="summary-card">
        <span>耗时</span>
        <strong>{{ duration || 0 }}ms</strong>
      </div>
      <div class="summary-card">
        <span>大小</span>
        <strong>{{ responseSize }}</strong>
      </div>
    </div>

    <el-tabs v-if="method" v-model="mainTab" class="panel-tabs">
      <el-tab-pane label="请求信息" name="request">
          <ExecutionRequestDetail
            v-model:active-tab="requestDetailTab"
            :method="method"
            :request-url="fullUrl || requestUrl"
            :params-text="reqParamsText"
            :path-params-text="reqPathParamsText"
            :body-text="reqBodyText"
            :headers-text="reqHeadersText"
            :proxy-text="reqProxyText"
            :service="reqService"
          />
      </el-tab-pane>
      <el-tab-pane label="响应结果" name="response">
        <ExecutionResponseDetail
          v-model:active-tab="responseDetailTab"
          :body-text="respBodyText"
          :headers-text="respHeadersText"
        >
          <template #body>
            <el-input :model-value="respBodyText" type="textarea" :rows="10" readonly class="code-input" />
          </template>
        </ExecutionResponseDetail>
      </el-tab-pane>
      <el-tab-pane label="脚本日志" name="logs">
        <pre class="code-block">{{ logs || '(无)' }}</pre>
      </el-tab-pane>
    </el-tabs>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { copyToClipboard } from '@/utils/clipboard'
import { formatExecutionValue, formatResponseBody, pickResponseBodyText, summarizeAssertionDiffs } from '@/utils/executionResult'
import ExecutionRequestDetail from '@/components/ExecutionRequestDetail.vue'
import ExecutionResponseDetail from '@/components/ExecutionResponseDetail.vue'
import AssertionDiffTable from '@/components/AssertionDiffTable.vue'

const props = defineProps({
  modelValue: Boolean,
  title: { type: String, default: '调试' },
  loading: Boolean,
  method: { type: String, default: '' },
  requestUrl: { type: String, default: '' },
  fullUrl: { type: String, default: '' },
  reqHeaders: { type: Object, default: () => ({}) },
  reqProxy: { type: [Object, String, Array], default: '' },
  reqService: { type: [Object, String, Array], default: null },
  reqBody: { type: [Object, String, Array], default: '' },
  reqParams: { type: Object, default: () => ({}) },
  reqPathParams: { type: Array, default: () => [] },
  response: { type: [Object, String, Array], default: null },
  respHeaders: { type: Object, default: null },
  error: { type: String, default: '' },
  statusCode: { type: Number, default: 0 },
  duration: { type: Number, default: 0 },
  steps: { type: Array, default: null },
  logs: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'send', 'close'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const mainTab = ref('response')
const stepTab = ref('resp')
// 请求信息默认自动定位到第一个有数据的页签，响应结果固定先看响应体
const requestDetailTab = ref('auto')
const responseDetailTab = ref('body')
const stepRequestTab = ref('auto')
const stepResponseTab = ref('body')
const selectedStep = ref(null)
const assertionFilter = ref('all')

const onStepSelect = (row) => {
  selectedStep.value = row
  // 换一个步骤就重新自动定位，各步骤的请求内容不一样
  stepRequestTab.value = 'auto'
  stepResponseTab.value = 'body'
}

const getStepAssertionDiffs = (step) => Array.isArray(step?.assertionDiffs) ? step.assertionDiffs : []
const getStepAssertionSummary = (step) => summarizeAssertionDiffs(getStepAssertionDiffs(step))
const allAssertionDiffs = computed(() => (props.steps || []).flatMap(getStepAssertionDiffs))
const assertionSummary = computed(() => summarizeAssertionDiffs(allAssertionDiffs.value))
const assertionTotal = computed(() => assertionSummary.value.total)
const assertionPassedCount = computed(() => assertionSummary.value.passed)
const assertionFailedCount = computed(() => assertionSummary.value.failed)
const assertionMatchesFilter = (diff, filter) => {
  if (filter === 'passed') return diff?.result === 'pass'
  if (filter === 'failed') return diff?.result !== 'pass'
  return true
}
const sortedAssertions = (list) => [...(list || [])].sort((a, b) => (a.result === 'pass') - (b.result === 'pass'))
const selectedAssertionDiffs = computed(() => sortedAssertions(
  getStepAssertionDiffs(selectedStep.value).filter(diff => assertionMatchesFilter(diff, assertionFilter.value)),
))
const showAssertions = (filter) => {
  assertionFilter.value = filter
  const target = (props.steps || []).find(step => getStepAssertionDiffs(step).some(diff => assertionMatchesFilter(diff, filter))) || props.steps?.[0]
  if (!target) return
  onStepSelect(target)
  stepTab.value = 'assertions'
}
const showStepAssertions = (row) => {
  assertionFilter.value = 'all'
  onStepSelect(row)
  stepTab.value = 'assertions'
}

const hasCaseNames = computed(() => (props.steps || []).some(step => step?.caseName || step?.test_case_name))

const methodTypeFor = (method) => {
  const m = method?.toUpperCase()
  return { GET: 'success', POST: 'primary', PUT: 'warning', DELETE: 'danger', PATCH: 'info' }[m] || 'info'
}
const methodType = computed(() => methodTypeFor(props.method))

const statusTypeFor = (code) => {
  const s = Number(code || 0)
  if (s >= 200 && s < 300) return 'success'
  if (s >= 300 && s < 400) return 'warning'
  return 'danger'
}
const statusType = computed(() => statusTypeFor(props.statusCode))

const hasReqParams = computed(() => props.reqParams && Object.keys(props.reqParams).length > 0)
const reqParamsText = computed(() => {
  if (!hasReqParams.value) return ''
  return JSON.stringify(props.reqParams, null, 2)
})
// 空值一律返回空串，由展示组件统一渲染「(无)」，避免各处文案不一致
const reqHeadersText = computed(() => {
  if (!props.reqHeaders || !Object.keys(props.reqHeaders).length) return ''
  return JSON.stringify(props.reqHeaders, null, 2)
})
const respHeadersText = computed(() => {
  if (!props.respHeaders) return ''
  if (typeof props.respHeaders === 'string') return props.respHeaders
  return JSON.stringify(props.respHeaders, null, 2)
})

const respBodyText = computed(() => {
  return formatResponseBody(props.response)
})

const responseSize = computed(() => {
  const text = respBodyText.value
  if (!text) return '0 B'
  const bytes = new Blob([text]).size
  return bytes > 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${bytes} B`
})
const hasResponseMeta = computed(() => !!props.response || !!props.statusCode || !!props.duration)
const reqProxyText = computed(() => formatExecutionValue(props.reqProxy))

const stringifyPretty = (value) => {
  if (value == null || value === '') return ''
  if (typeof value === 'string') return value
  try { return JSON.stringify(value, null, 2) } catch { return String(value) }
}

const reqBodyText = computed(() => stringifyPretty(props.reqBody))
const reqPathParamsText = computed(() => stringifyPretty(props.reqPathParams || []))

const stepReqHeadersText = computed(() => {
  const headers = selectedStep.value?.request?.headers
  if (!headers || !Object.keys(headers).length) return ''
  return stringifyPretty(headers)
})
const stepReqParamsText = computed(() => stringifyPretty(selectedStep.value?.request?.params))
const stepReqPathParamsText = computed(() => stringifyPretty(selectedStep.value?.request?.path_params || []))
const stepReqBodyText = computed(() => stringifyPretty(selectedStep.value?.request?.body))
const stepProxyText = computed(() => formatExecutionValue(selectedStep.value?.request?.proxy))
const stepRespBodyText = computed(() => pickResponseBodyText(selectedStep.value?.response))
const stepRespHeadersText = computed(() => {
  const headers = selectedStep.value?.response?.headers
  return headers && Object.keys(headers).length ? stringifyPretty(headers) : ''
})

const shellQuote = (value) => {
  return `'${String(value ?? '').replace(/'/g, `'\\''`)}'`
}

const bodyToCurlText = (body) => {
  if (body == null || body === '') return ''
  if (typeof body === 'string') return body
  try { return JSON.stringify(body) } catch { return String(body) }
}

const isJsonBodyText = (text) => {
  const trimmed = String(text || '').trim()
  if (!trimmed) return false
  if (!((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']')))) return false
  try {
    JSON.parse(trimmed)
    return true
  } catch {
    return false
  }
}

const hasContentTypeHeader = (headers) => {
  return Object.keys(headers || {}).some(k => k.toLowerCase() === 'content-type')
}

const buildUrlWithParams = (url, params) => {
  if (!params || !Object.keys(params).length) return url
  const qs = new URLSearchParams(params).toString()
  if (!qs) return url
  return `${url}${url.includes('?') ? '&' : '?'}${qs}`
}

const copyCurl = async () => {
  const url = props.fullUrl || props.requestUrl
  let curl = `curl -X ${props.method} ${shellQuote(buildUrlWithParams(url, props.reqParams))}`
  const headers = { ...(props.reqHeaders || {}) }
  const bodyText = bodyToCurlText(props.reqBody)
  if (bodyText && isJsonBodyText(bodyText) && !hasContentTypeHeader(headers)) {
    headers['Content-Type'] = 'application/json'
  }
  Object.entries(headers).forEach(([k, v]) => {
    curl += ` \\\n  -H ${shellQuote(`${k}: ${v}`)}`
  })
  if (bodyText) {
    curl += ` \\\n  --data-raw ${shellQuote(bodyText)}`
  }
  try {
    const copied = await copyToClipboard(curl)
    copied ? ElMessage.success('已复制 cURL') : ElMessage.warning('复制失败，请手动复制')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

watch(() => props.response, () => {
  mainTab.value = 'response'
  requestDetailTab.value = 'auto'
  responseDetailTab.value = 'body'
})
watch(() => props.steps, (steps) => {
  selectedStep.value = steps?.[0] || null
  assertionFilter.value = 'all'
  stepTab.value = 'resp'
  stepRequestTab.value = 'auto'
  stepResponseTab.value = 'body'
}, { immediate: true })
</script>

<style scoped>
.debug-hero {
  display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 14px;
  padding: 12px 14px; background: #f7f9fc; border: 1px solid #e8edf3; border-radius: 8px;
}
.request-line { min-width: 0; flex: 1; display: flex; align-items: center; gap: 10px; }
.method-tag { min-width: 58px; text-align: center; }
.debug-url { flex: 1; font-size: 13px; font-family: SFMono-Regular, Consolas, monospace; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.debug-actions { display: flex; gap: 8px; flex-shrink: 0; }
.execution-result-header {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  margin: 12px 0 10px; padding: 10px 12px;
  border: 1px solid #e8edf3; border-radius: 8px; background: #f7f9fc;
}
.execution-result-title { min-width: 0; display: flex; align-items: center; gap: 8px; }
.execution-result-title strong { flex-shrink: 0; color: #303133; font-size: 14px; }
.execution-case-name { flex-shrink: 0; color: #606266; font-size: 12px; }
.debug-loading { min-height: 120px; display: flex; align-items: center; justify-content: center; gap: 8px; color: #409eff; font-size: 14px; }
.run-summary, .response-summary {
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px;
}
.summary-item, .summary-card {
  min-height: 58px; border: 1px solid #e8edf3; border-radius: 8px; background: #fbfcfe;
  padding: 10px 12px; display: flex; flex-direction: column; justify-content: center; gap: 4px;
}
.summary-item strong, .summary-card strong { color: #303133; font-size: 18px; line-height: 1; }
.summary-label, .summary-card span { color: #909399; font-size: 12px; }
.assertion-summary-item {
  width: 100%; color: inherit; font: inherit; text-align: left; cursor: pointer;
  transition: border-color .18s ease, box-shadow .18s ease, background .18s ease;
}
.assertion-summary-item:hover, .assertion-summary-item.is-active {
  border-color: #91caff; background: #f7fbff; box-shadow: 0 2px 8px rgba(22, 119, 255, .08);
}
.assertion-summary-item:focus-visible { outline: 2px solid #1677ff; outline-offset: 2px; }
.assertion-link { padding: 0; font-size: 12px; }
.status-code-tag { align-self: flex-start; min-width: 0; width: fit-content; }
.summary-item.success strong { color: #67c23a; }
.summary-item.danger strong { color: #f56c6c; }
.run-table { margin-bottom: 12px; border: 1px solid #e8edf3; border-radius: 8px; overflow: hidden; }
.run-table :deep(.el-table__body-wrapper) { max-height: 220px; overflow-y: auto; }
.run-table :deep(.el-table__cell) { padding: 7px 0; }
.detail-title, .code-title {
  font-weight: 600; font-size: 13px; color: #303133; margin: 12px 0 6px;
}
.panel-tabs {
  border: 1px solid #e8edf3; border-radius: 8px; padding: 0 12px 12px; background: #fff;
}
.panel-tabs :deep(.el-tab-pane) {
  min-height: 0;
}
.code-block {
  max-height: min(260px, 32vh); overflow: auto; background: #f7f9fc;
  border: 1px solid #edf1f7; padding: 10px; border-radius: 6px; font-size: 13px;
  font-family: SFMono-Regular, Consolas, monospace;
  white-space: pre-wrap; word-break: break-all; margin: 0;
}
.code-input :deep(textarea) {
  max-height: min(260px, 32vh);
  font-family: SFMono-Regular, Consolas, monospace; font-size: 13px;
  background: #f7f9fc; border-color: #edf1f7; border-radius: 6px;
}
/* 弹窗：自适应屏幕高度 */
.debug-dialog :deep(.el-dialog) { display: flex; flex-direction: column; max-height: calc(100vh - 48px); margin: 0 auto; }
.debug-dialog :deep(.el-dialog__body) { flex: 1; min-height: 0; overflow-y: auto; padding: 18px 24px 22px; }
.debug-dialog :deep(.el-dialog__header) { padding: 18px 24px 12px; border-bottom: 1px solid #edf1f7; }

@media (max-width: 768px) {
  .debug-hero { flex-direction: column; align-items: stretch; }
  .execution-result-header { flex-direction: column; align-items: stretch; }
  .execution-case-name { align-self: flex-start; }
  .run-summary, .response-summary { grid-template-columns: 1fr; }
}
</style>

<style>
/* el-dialog 会 teleport 到 body，这里用全局样式确保运行结果弹窗始终被视口约束住 */
.el-dialog.debug-dialog {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 48px);
  margin: 0 auto;
}
.el-dialog.debug-dialog .el-dialog__header {
  flex: 0 0 auto;
}
.el-dialog.debug-dialog .el-dialog__body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}
</style>
