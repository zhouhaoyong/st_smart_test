<template>
  <p v-if="pathParameterValidationMessage" class="path-parameter-validation" role="alert">{{ pathParameterValidationMessage }}</p>
  <el-tabs v-model="tab" class="request-config-tabs">
    <el-tab-pane label="查询参数" name="query">
      <ParamEditTable
        v-model="model.query_params"
        title="查询参数"
        add-label="添加参数"
        :empty-text="queryEmptyText"
        :show-required="paramShowRequired"
        :show-type="paramShowType"
        :type-options="paramTypeOptions"
      />
    </el-tab-pane>

    <el-tab-pane label="路径参数" name="path">
      <div class="path-parameter-editor">
        <ParamEditTable
          v-model="model.path_params"
          title="路径参数"
          add-label="添加参数"
          :empty-text="pathEmptyText"
          :show-required="paramShowRequired"
          :show-type="paramShowType"
          :type-options="paramTypeOptions"
        />
      </div>
    </el-tab-pane>

    <el-tab-pane label="请求体" name="body">
      <div class="body-toolbar">
        <el-radio-group v-model="model.body_type" size="small">
          <el-radio-button value="">none</el-radio-button>
          <el-radio-button value="json">JSON</el-radio-button>
          <el-radio-button value="form">Form</el-radio-button>
          <el-radio-button value="form-data">Form-Data</el-radio-button>
          <el-radio-button value="raw">Raw</el-radio-button>
        </el-radio-group>
        <div class="body-toolbar-actions">
          <el-button-group v-if="model.body_type === 'json'" size="small">
            <el-button @click="formatBodyJson">格式化</el-button>
            <el-button @click="validateBodyJson">校验</el-button>
          </el-button-group>
          <slot name="body-toolbar-extra" :model="model" />
        </div>
      </div>
      <slot name="body-content" :model="model">
        <el-input
          v-if="model.body_type"
          v-model="model.body_content"
          type="textarea"
          :rows="bodyRows"
          :placeholder="bodyPlaceholder"
          :class="{ 'code-editor': true, 'json-error': bodyJsonError }"
        />
        <div v-else-if="bodyEmptyText" class="body-empty">{{ bodyEmptyText }}</div>
      </slot>
      <div v-if="bodyJsonError" class="json-error-text">{{ bodyJsonError }}</div>
      <slot name="body-after" :model="model" />
    </el-tab-pane>

    <el-tab-pane label="请求头" name="headers">
      <slot name="headers-toolbar" :model="model" />
      <slot name="headers-content" :model="model">
        <ParamEditTable
          v-model="model.headers"
          title="请求头参数"
          add-label="添加请求头"
          :empty-text="headersEmptyText"
          :show-type="paramShowType"
          :type-options="paramTypeOptions"
        />
      </slot>
    </el-tab-pane>

    <el-tab-pane label="前置脚本" name="prescript">
      <el-input v-model="model.pre_script" type="textarea" :rows="scriptRows" placeholder="// 请求发送前执行的 JavaScript 脚本" class="code-editor" />
    </el-tab-pane>

    <el-tab-pane label="后置脚本" name="postscript">
      <el-input v-model="model.post_script" type="textarea" :rows="scriptRows" placeholder="// 收到响应后执行的 JavaScript 脚本" class="code-editor" />
    </el-tab-pane>

    <el-tab-pane v-if="showAssertions" label="断言" name="assertions">
      <div v-for="(assertion, index) in model.assertions" :key="index" class="assertion-row">
        <el-switch
          :model-value="assertion.enabled !== false"
          @update:model-value="value => { assertion.enabled = value }"
          inline-prompt
          active-text="启用"
          inactive-text="停用"
        />
        <el-select v-model="assertion.type" style="width:110px">
          <el-option label="JSONPath" value="jsonpath" />
          <el-option label="状态码" value="status_code" />
          <el-option label="响应时间" value="response_time" />
          <el-option label="包含文本" value="contains" />
        </el-select>
        <el-autocomplete
          v-if="assertion.type === 'jsonpath'"
          v-model="assertion.expression"
          :fetch-suggestions="queryJsonPathSuggestions"
          :fit-input-width="false"
          :debounce="0"
          placeholder="$.code"
          class="assertion-expression"
          :style="{ width: responseSampleLoader ? '278px' : '150px' }"
        >
          <template v-if="responseSampleLoader" #append>
            <el-button class="assertion-pick-btn" @click="openJsonPathPicker(index)">选取</el-button>
          </template>
        </el-autocomplete>
        <el-input v-if="assertion.type === 'status_code'" v-model="assertion.expression" placeholder="200" style="width:80px" />
        <el-input v-if="assertion.type === 'response_time'" v-model="assertion.expression" placeholder="1000" style="width:80px" />
        <el-select v-model="assertion.operator" style="width:90px">
          <el-option label="==" value="eq" /><el-option label="!=" value="neq" />
          <el-option label=">" value="gt" /><el-option label="<" value="lt" />
          <el-option label=">=" value="gte" /><el-option label="<=" value="lte" />
          <el-option label="包含" value="contains" />
          <el-option label="非空" value="not_empty" />
          <el-option label="为空" value="is_empty" />
        </el-select>
        <el-input
          v-model="assertion.expected"
          :disabled="!assertionOperatorNeedsExpected(assertion.operator)"
          :placeholder="assertionOperatorNeedsExpected(assertion.operator) ? '期望值' : '无需期望值'"
          :title="assertion.expected"
          style="width:230px"
        />
        <el-button text type="danger" @click="removeAssertion(index)"><el-icon><Delete /></el-icon></el-button>
      </div>
      <el-button text type="primary" @click="addAssertion">+ 添加断言</el-button>
      <JsonPathPickerDialog
        v-if="showAssertions && responseSampleLoader"
        v-model="jsonPathPickerVisible"
        :expression="jsonPathPickerExpression"
        selection-mode
        :selected-assertions="model.assertions"
        :loader="responseSampleLoader"
        :method="model.method"
        @confirm-selection="applyPickedAssertionSelection"
      />
    </el-tab-pane>
  </el-tabs>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'
import ParamEditTable from '@/components/ParamEditTable.vue'
import JsonPathPickerDialog from '@/components/JsonPathPickerDialog.vue'
import { assertionOperatorNeedsExpected } from '@/utils/assertionOperators'
import {
  extractPathParameterNames,
  syncPathParametersFromUrl,
  syncUrlFromPathParameters,
  validatePathParameterList,
  validatePathParameterUrl,
} from '@/utils/pathParameterSync'

const props = defineProps({
  model: { type: Object, required: true },
  activeTab: { type: String, default: 'query' },
  showAssertions: { type: Boolean, default: false },
  bodyRows: { type: Number, default: 8 },
  scriptRows: { type: Number, default: 6 },
  bodyPlaceholder: { type: String, default: '{"key":"value"}' },
  bodyEmptyText: { type: String, default: '' },
  queryEmptyText: { type: String, default: '暂无查询参数' },
  pathEmptyText: { type: String, default: '暂无路径参数，请在 URL 中输入 {参数名}，系统将自动识别，或点击“添加参数”' },
  headersEmptyText: { type: String, default: '暂无请求头' },
  paramShowType: { type: Boolean, default: true },
  // 类型与是否必填都属于接口契约，只在接口定义处声明；用例侧关掉这两列
  paramShowRequired: { type: Boolean, default: true },
  paramTypeOptions: { type: Array, default: undefined },
  // 由外层提供：执行一次请求并返回响应体文本，用于断言表达式的字段选取；不传则不展示选取按钮
  responseSampleLoader: { type: Function, default: null },
})

const emit = defineEmits(['update:activeTab'])

// 断言常用响应路径：聚焦时给出候选，选中后仍可在输入框里继续改，也可直接输入清单外的路径
const COMMON_JSONPATH_EXPRESSIONS = Object.freeze(['$.code', '$.message', '$.data', '$.success'])
// 候选列表固定不变，提前构造好，避免每次弹出都重建数组
const JSONPATH_SUGGESTIONS = COMMON_JSONPATH_EXPRESSIONS.map(value => ({ value }))

const queryJsonPathSuggestions = (queryString, callback) => {
  const keyword = (queryString || '').trim()
  // 没输入内容、或当前值恰好就是某个候选时，给出全部候选，方便直接换一个
  if (!keyword || COMMON_JSONPATH_EXPRESSIONS.includes(keyword)) {
    callback(JSONPATH_SUGGESTIONS.slice())
    return
  }
  callback(JSONPATH_SUGGESTIONS.filter(item => item.value.includes(keyword)))
}

const tab = computed({
  get: () => props.activeTab,
  set: value => emit('update:activeTab', value),
})

// 请求体 JSON 格式化/校验：所有用到参数配置区的地方（接口、用例、cURL、AI 导入）都能用
const bodyJsonError = ref('')

const resetBodyJsonError = () => { bodyJsonError.value = '' }

const formatBodyJson = () => {
  try {
    props.model.body_content = JSON.stringify(JSON.parse(props.model.body_content || '{}'), null, 2)
    bodyJsonError.value = ''
  } catch (e) {
    bodyJsonError.value = 'JSON格式错误: ' + e.message
  }
}

const validateBodyJson = () => {
  try {
    JSON.parse(props.model.body_content || '{}')
    bodyJsonError.value = ''
    ElMessage.success('JSON格式正确')
  } catch (e) {
    bodyJsonError.value = 'JSON格式错误: ' + e.message
  }
}

// 换一份数据或换请求体类型时，上一次的格式错误提示不应残留
watch(() => props.model, resetBodyJsonError)
watch(() => props.model?.body_type, resetBodyJsonError)

const pathParameterValidationMessage = computed(() => {
  const urlValidation = validatePathParameterUrl(props.model?.url)
  if (!urlValidation.valid) return urlValidation.message
  return validatePathParameterList(props.model?.path_params).message
})

let pathSyncInitialized = false
let previousPathParams = []
let pathSyncModel = null

function resetPathSyncStateIfNeeded() {
  if (pathSyncModel === props.model) return
  pathSyncModel = props.model
  pathSyncInitialized = false
  previousPathParams = []
}

function syncPathParamsWithUrl() {
  resetPathSyncStateIfNeeded()
  const currentParams = Array.isArray(props.model?.path_params) ? props.model.path_params : []
  const url = String(props.model?.url ?? '')
  if (!validatePathParameterUrl(url).valid) return

  if (!pathSyncInitialized && extractPathParameterNames(url).length === 0 && currentParams.some(item => String(item?.key ?? '').trim())) {
    const syncedUrl = syncUrlFromPathParameters(url, currentParams, currentParams)
    if (syncedUrl !== url) props.model.url = syncedUrl
  } else {
    const syncedParams = syncPathParametersFromUrl(url, currentParams)
    const currentKeys = currentParams.map(item => String(item?.key ?? '').trim())
    const syncedKeys = syncedParams.map(item => String(item?.key ?? '').trim())
    if (currentKeys.join('\u0000') !== syncedKeys.join('\u0000')) props.model.path_params = syncedParams
  }
  previousPathParams = Array.isArray(props.model.path_params) ? props.model.path_params.map(item => ({ key: item?.key })) : []
  pathSyncInitialized = true
}

watch(() => props.model?.url, syncPathParamsWithUrl, { immediate: true })
watch(() => props.model?.path_params, currentParams => {
  resetPathSyncStateIfNeeded()
  if (!pathSyncInitialized) {
    previousPathParams = Array.isArray(currentParams) ? currentParams.map(item => ({ key: item?.key })) : []
    return
  }
  const url = String(props.model?.url ?? '')
  if (validatePathParameterUrl(url).valid) {
    const syncedUrl = syncUrlFromPathParameters(url, previousPathParams, currentParams)
    if (syncedUrl !== url) props.model.url = syncedUrl
  }
  previousPathParams = Array.isArray(currentParams) ? currentParams.map(item => ({ key: item?.key })) : []
}, { deep: true })

const addAssertion = () => {
  if (!Array.isArray(props.model.assertions)) props.model.assertions = []
  props.model.assertions.push({ type: 'jsonpath', expression: '', operator: 'eq', expected: '', enabled: true })
}

// 字段选取弹窗：打开时回显当前用例的 JSONPath 断言，确认后按勾选结果同步当前表单
const jsonPathPickerVisible = ref(false)
const jsonPathPickerExpression = ref('')

const openJsonPathPicker = (index) => {
  jsonPathPickerExpression.value = props.model.assertions?.[index]?.expression || ''
  jsonPathPickerVisible.value = true
}

// 选取弹窗的勾选结果是当前表单中 JSONPath 断言的完整集合；未勾选的断言临时移除
const applyPickedAssertionSelection = (items) => {
  if (!Array.isArray(props.model.assertions)) props.model.assertions = []
  const selectedByExpression = new Map(
    items
      .filter(item => item?.expression)
      .map(item => [String(item.expression).trim(), item])
  )
  const nextAssertions = []
  const keptExpressions = new Set()

  props.model.assertions.forEach(assertion => {
    const isJsonPath = !assertion?.type || assertion.type === 'jsonpath'
    if (!isJsonPath) {
      nextAssertions.push(assertion)
      return
    }
    const expression = String(assertion?.expression || '').trim()
    if (!expression || !selectedByExpression.has(expression) || keptExpressions.has(expression)) return
    // 重新请求后，同一路径的期望值应以本次响应为准；其余断言配置继续沿用。
    nextAssertions.push({
      ...assertion,
      expected: selectedByExpression.get(expression).fill?.expected ?? '',
    })
    keptExpressions.add(expression)
  })

  selectedByExpression.forEach((item, expression) => {
    if (keptExpressions.has(expression)) return
    nextAssertions.push({
      type: 'jsonpath',
      expression,
      operator: 'eq',
      expected: item.fill?.expected ?? '',
      enabled: true,
    })
    keptExpressions.add(expression)
  })
  props.model.assertions = nextAssertions
}

const removeAssertion = index => {
  props.model.assertions.splice(index, 1)
}

defineExpose({ resetBodyJsonError })
</script>

<style scoped>
.body-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.body-toolbar-actions { display: flex; align-items: center; gap: 8px; }
.code-editor { margin-top: 8px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.code-editor :deep(.el-textarea__inner) { font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 13px; }
.json-error :deep(.el-textarea__inner) { border-color: var(--el-color-danger); }
.body-empty {
  height: 150px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  font-size: 13px;
  background: #fafcff;
}
.json-error-text {
  padding: 6px 10px;
  color: #f56c6c;
  font-size: 12px;
  border-top: 1px solid #fef0f0;
  background: #fff7f7;
}
.assertion-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
/* 选取按钮做成表达式框尾部的附加按钮：整行总宽度不变，输入区反而比独立按钮时更宽 */
.assertion-expression { flex-shrink: 0; }
.assertion-expression :deep(.el-input-group__append) {
  padding: 0 12px;
  border-top: 1px solid var(--el-input-border-color);
  border-bottom: 1px solid var(--el-input-border-color);
}
/* 附加区里的按钮会被去掉底色，用主色文字提示可点 */
.assertion-expression :deep(.el-input-group__append .el-button) { color: var(--el-color-primary); }
.path-parameter-validation { margin: 8px 0 0; color: var(--el-color-danger); font-size: 12px; line-height: 1.5; }
@media (max-width: 1440px) {
  .assertion-row { flex-wrap: wrap; }
  .assertion-row .el-input { flex: 1 1 140px; min-width: 120px; }
}
</style>
