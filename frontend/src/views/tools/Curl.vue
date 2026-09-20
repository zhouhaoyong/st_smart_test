<template>
  <div class="curl-tool">
    <el-card>
      <template #header><h3 style="margin:0">cURL 解析</h3></template>
      <div class="curl-layout">
        <section class="curl-panel">
          <div class="panel-header">
            <span class="panel-label">输入</span>
            <div class="panel-actions">
              <CopyButton :value="curlText" label="复制" tooltip="复制 cURL 命令" />
              <el-button size="small" @click="clearCurl" :disabled="!curlText && !result && !error">清空</el-button>
              <el-button size="small" type="primary" @click="handleParse" :loading="loading">解析 cURL</el-button>
              <el-button size="small" type="success" @click="handleRun" :disabled="!result">运行接口</el-button>
            </div>
          </div>
          <el-input v-model="curlText" class="curl-input" type="textarea" :rows="18" placeholder="粘贴 cURL 命令" />
        </section>

        <section class="curl-panel">
          <div class="panel-header">
            <span class="panel-label">解析结果</span>
            <CopyButton :value="result ? jsonStr(result) : ''" label="复制 JSON" tooltip="复制解析结果" />
          </div>
          <div class="result-box">
            <template v-if="result">
              <CurlRequestPreview
                v-model:active-tab="activeResultTab"
                :name="result.name"
                :method="result.method"
                :url="result.url"
                :full-url="result.full_url"
                :body-type="result.body_type"
                :query-params-text="displayQueryParams"
                :body-text="displayBodyContent"
                :headers-text="displayHeaders"
                :query-param-count="queryParamCount"
                :header-count="headerCount"
                :body-copy-disabled="!result.body_content"
              />
            </template>
            <div v-else class="empty-result">
                <p>解析后的请求方法、路径、查询参数、请求体和请求头会显示在这里。</p>
              <span>粘贴 cURL 后点击“解析 cURL”。</span>
            </div>
          </div>
        </section>
      </div>
      <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    </el-card>

    <el-dialog v-model="runDialogVisible" title="运行接口" width="880px" destroy-on-close>
      <template v-if="result">
        <div class="run-request-hero">
          <el-tag type="primary" effect="dark">{{ result.method || 'GET' }}</el-tag>
          <span>{{ runResult?.request?.url || result.full_url || result.url || '-' }}</span>
        </div>

        <div v-if="runError" class="run-error">
          <el-alert :title="runError" type="error" show-icon :closable="false" />
        </div>

        <div v-if="runResult" class="run-status-row">
          <span>状态码：<el-tag size="small" :type="responseStatusType">{{ runResult.response?.status_code || '-' }}</el-tag></span>
          <span>耗时：{{ runResult.duration_ms ?? '-' }} ms</span>
        </div>

        <el-tabs v-model="activeRunTab" class="run-detail-tabs">
          <el-tab-pane label="请求信息" name="request">
            <ExecutionRequestDetail
              v-model:active-tab="activeRunRequestTab"
              :request-url="runResult?.request?.url || result.full_url || result.url"
              :params-text="displayQueryParams"
              :path-params-text="displayPathParams"
              :body-text="displayRunRequestBody"
              :headers-text="displayRunRequestHeaders"
              :show-proxy="false"
              :show-service="false"
            />
          </el-tab-pane>
          <el-tab-pane label="响应结果" name="response">
            <ExecutionResponseDetail
              v-model:active-tab="activeRunResponseTab"
              :body-text="displayResponseBody"
              :headers-text="displayResponseHeaders"
            >
              <template #body>
                <CodePreview :content="displayResponseBody" />
              </template>
              <template #headers>
                <CodePreview :content="displayResponseHeaders" />
              </template>
            </ExecutionResponseDetail>
          </el-tab-pane>
        </el-tabs>
      </template>
      <template #footer>
        <el-button @click="runDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { executeCurl, parseCurl } from '@/api/tools'
import CopyButton from '@/components/CopyButton.vue'
import CodePreview from '@/components/CodePreview.vue'
import CurlRequestPreview from '@/components/CurlRequestPreview.vue'
import ExecutionRequestDetail from '@/components/ExecutionRequestDetail.vue'
import ExecutionResponseDetail from '@/components/ExecutionResponseDetail.vue'

const curlText = ref('')
const loading = ref(false)
const result = ref(null)
const error = ref('')
const activeResultTab = ref('info')
const runDialogVisible = ref(false)
const runLoading = ref(false)
const runResult = ref(null)
const runError = ref('')
const activeRunRequestTab = ref('info')
const activeRunTab = ref('response')
const activeRunResponseTab = ref('body')

const jsonStr = (v) => {
  if (!v || (Array.isArray(v) && !v.length)) return '(无)'
  try { return JSON.stringify(v, null, 2) } catch { return String(v) }
}

const pairsToObject = (pairs) => {
  if (!Array.isArray(pairs) || !pairs.length) return null
  return pairs.reduce((acc, item) => {
    if (!item?.key) return acc
    if (Object.prototype.hasOwnProperty.call(acc, item.key)) {
      acc[item.key] = Array.isArray(acc[item.key]) ? [...acc[item.key], item.value] : [acc[item.key], item.value]
    } else {
      acc[item.key] = item.value
    }
    return acc
  }, {})
}

const formStringToObject = (text) => {
  if (!text) return null
  const params = new URLSearchParams(text)
  const entries = Array.from(params.entries())
  if (!entries.length) return null
  return entries.reduce((acc, [key, value]) => {
    if (Object.prototype.hasOwnProperty.call(acc, key)) {
      acc[key] = Array.isArray(acc[key]) ? [...acc[key], value] : [acc[key], value]
    } else {
      acc[key] = value
    }
    return acc
  }, {})
}

const displayQueryParams = computed(() => jsonStr(pairsToObject(result.value?.query_params)))
const displayPathParams = computed(() => jsonStr(result.value?.path_params || []))
const displayHeaders = computed(() => jsonStr(pairsToObject(result.value?.headers)))
const queryParamCount = computed(() => result.value?.query_params?.length || 0)
const headerCount = computed(() => result.value?.headers?.length || 0)

const displayBodyContent = computed(() => {
  const body = result.value?.body_content
  if (!body) return '(无)'
  if (result.value?.body_type === 'form') return jsonStr(formStringToObject(body))
  if (result.value?.body_type === 'json') {
    try { return JSON.stringify(JSON.parse(body), null, 2) } catch { return body }
  }
  return jsonStr({ raw: body })
})

const displayResponseBody = computed(() => runResult.value ? jsonStr(runResult.value.response?.body) : '暂无响应')
const displayResponseHeaders = computed(() => runResult.value ? jsonStr(runResult.value.response?.headers) : '暂无响应')
const displayRunRequestHeaders = computed(() => {
  const headers = runResult.value?.request?.headers
  return jsonStr(headers && Object.keys(headers).length ? headers : pairsToObject(result.value?.headers))
})
const displayRunRequestBody = computed(() => {
  const body = runResult.value?.request?.body || result.value?.body_content
  if (!body) return '(无)'
  if (result.value?.body_type === 'form') return jsonStr(formStringToObject(body))
  if (result.value?.body_type === 'json') {
    try { return JSON.stringify(JSON.parse(body), null, 2) } catch { return body }
  }
  return jsonStr({ raw: body })
})
const responseStatusType = computed(() => {
  const status = runResult.value?.response?.status_code
  if (!status) return 'info'
  if (status >= 200 && status < 300) return 'success'
  if (status >= 400) return 'danger'
  return 'warning'
})

const clearCurl = () => {
  curlText.value = ''
  result.value = null
  error.value = ''
  activeResultTab.value = 'info'
  runResult.value = null
  runError.value = ''
  activeRunTab.value = 'response'
  activeRunRequestTab.value = 'body'
  activeRunResponseTab.value = 'body'
}

const handleParse = async () => {
  if (!curlText.value.trim()) {
    ElMessage.warning('请输入 cURL 命令')
    return
  }
  loading.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await parseCurl(curlText.value)
    activeResultTab.value = 'info'
    runResult.value = null
    runError.value = ''
  } catch (e) {
    error.value = e.response?.data?.message || e.response?.data?.detail || e.message || '解析失败'
  } finally {
    loading.value = false
  }
}

const handleRun = async () => {
  if (!curlText.value.trim()) {
    ElMessage.warning('请输入 cURL 命令')
    return
  }
  runDialogVisible.value = true
  runLoading.value = true
  runError.value = ''
  runResult.value = null
  activeRunTab.value = 'response'
  activeRunRequestTab.value = 'body'
  activeRunResponseTab.value = 'body'
  try {
    runResult.value = await executeCurl(curlText.value)
    activeRunTab.value = 'response'
  } catch (e) {
    runError.value = e.response?.data?.message || e.response?.data?.detail || e.message || '运行失败'
  } finally {
    runLoading.value = false
  }
}
</script>

<style scoped>
.curl-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 20px; align-items: stretch; }
.curl-panel { min-width: 0; display: flex; flex-direction: column; }
.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.panel-label { font-weight: 600; font-size: 14px; color: #595959; }
.panel-actions { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 8px; }
.panel-actions :deep(.el-button) { margin-left: 0; }
.curl-input { flex: 1; display: flex; }
.curl-panel :deep(.el-textarea__inner) {
  height: 470px;
  min-height: 470px;
  font-family: SFMono-Regular, Consolas, Monaco, monospace;
  font-size: 13px;
  line-height: 1.6;
}
.result-box {
  flex: 1;
  min-height: 470px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 12px;
  background: #fff;
}
.empty-result {
  height: 100%;
  min-height: 444px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #909399;
  text-align: center;
  border: 1px dashed #dcdfe6;
  border-radius: 4px;
  background: #fafafa;
}
.empty-result p { margin: 0 0 6px; color: #606266; }
.run-request-hero {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  padding: 12px 14px;
  border: 1px solid #e8edf3;
  border-radius: 8px;
  background: #f7f9fc;
  color: #303133;
  font-family: SFMono-Regular, Consolas, Monaco, monospace;
  word-break: break-all;
}
.run-error { margin: 12px 0; }
.run-detail-tabs { border: 1px solid #e8edf3; border-radius: 8px; padding: 0 12px 12px; background: #fff; }
.run-status-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
  margin-bottom: 12px;
  color: #595959;
  font-size: 13px;
}
@media (max-width: 900px) {
  .curl-layout { grid-template-columns: 1fr; }
}
</style>
