<template>
  <el-dialog
    :model-value="modelValue"
    :title="wizardTitle"
    width="min(1120px, calc(100vw - 48px))"
    align-center
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    class="ai-generation-wizard-dialog"
    :class="{ 'is-scope-step': wizardStep === 1, 'is-mode-step': wizardStep === 2, 'is-progress-step': wizardStep === 3 && generating, 'is-failure-step': wizardStep === 3 && !generating, 'is-result-step': wizardStep === 4, 'is-saved-step': wizardStep === 5 }"
    :before-close="handleWizardBeforeClose"
  >
    <div class="ai-generation-wizard">
      <el-steps :active="wizardStep - 1" finish-status="success" align-center class="ai-generation-wizard-steps wizard-steps-green">
        <el-step title="选择接口" description="确定本次生成范围" />
        <el-step title="生成模式" description="选择覆盖模式和模型" />
        <el-step title="生成中" description="等待生成结果" />
        <el-step title="预览确认" description="查看结果并选择保存" />
        <el-step title="保存成功" description="用例已保存" />
      </el-steps>

      <div class="ai-generation-wizard-body">
        <div v-show="wizardStep === 1" class="ai-generation-scope-step">
          <InterfaceCaseGenerationScopePanel
            :project-id="projectId"
            :collection-tree="collectionTree"
            :interface-ids="interfaceIds"
            :fixed-interface-ids="fixedScope ? interfaceIds : []"
            :fixed-interfaces="fixedScope ? interfaces : []"
            @confirm="onScopeConfirmed"
            @cancel="closeAll"
            @view-interface="openInterfaceDetail"
          />
        </div>

        <div v-show="wizardStep === 2" class="ai-generation-mode-step">
          <AiGenerationModePickerDialog
            :model-value="true"
            embedded
            :show-previous="true"
            title="AI生成用例"
            feature-label="接口批量生成用例"
            model-feature="api_interface_case_generate"
            :mode-options="GENERATION_MODE_OPTIONS"
            :selected-mode="selectedMode"
            :interfaces="generationTargetInterfaces"
            :model-candidates="modelCandidates"
            :selected-model-id="selectedModelId"
            :loading="preparing"
            @confirm="requestStartGeneration"
            @cancel="closeAll"
            @back="goToScopeStep"
            @models-refreshed="onModelsRefreshed"
          />
        </div>

        <div v-if="wizardStep === 3 && generating" class="generation-progress-dialog-body">
          <AiOperationProgress
            :kind="selectedMode === 'main' ? 'system' : 'ai'"
            :status-label="selectedMode === 'main' ? '系统生成中' : 'AI生成中'"
            :title="generationLoadingTitle"
            :hint="generationLoadingHint"
            :elapsed-text="generationElapsedText"
            :percentage="progressPercentage"
            :progress-text="batchGeneration.progressText.value"
            :meta-text="generationModelCallsText"
            timer-aria-label="生成耗时"
            :show-cancel="false"
            :embedded="true"
            @cancel="batchGeneration.stop"
          />
        </div>

        <div v-else-if="wizardStep === 3" class="generation-failure-body">
          <div class="generation-failure-content">
            <div class="generation-failure-card" :class="`is-${resultStatus}`" role="alert" aria-live="polite">
              <span class="generation-result-message-icon">
                <el-icon>
                  <CircleCloseFilled v-if="resultStatus === 'error'" />
                  <WarningFilled v-else />
                </el-icon>
              </span>
              <div class="generation-result-message-copy">
                <strong>{{ resultTitle }}</strong>
                <span>{{ generationFailureSummary }}</span>
              </div>
            </div>
            <div class="generation-failure-details" aria-label="失败原因">
              <div class="generation-failure-details-title">失败详情</div>
              <template v-if="generationFailureDetails.length">
                <div
                  v-for="(failure, index) in generationFailureDetails"
                  :key="`${failure.temp_id || failure.name || 'failure'}-${index}`"
                  class="generation-failure-detail"
                >
                  <strong class="generation-failure-detail-name">{{ failure.name || '未知接口' }}</strong>
                  <div class="generation-failure-detail-reason">
                    <span>{{ failure.reason || failure.detail || '未获取到具体失败原因' }}</span>
                    <span v-if="failure.detail && failure.detail !== failure.reason" class="generation-failure-detail-raw">{{ failure.detail }}</span>
                  </div>
                </div>
              </template>
              <div v-else class="generation-failure-detail generation-failure-detail-empty">
                <strong class="generation-failure-detail-name">本次生成</strong>
                <span class="generation-failure-detail-reason">{{ generationResult?.errorMessage || '未获取到具体失败原因' }}</span>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="wizardStep === 4" class="generation-result-body">
          <div class="generation-result-content">
            <div class="generation-result-runtime" aria-label="生成耗时">
              <el-icon><Timer /></el-icon>
              <span>生成耗时</span>
              <strong>{{ generationElapsedText }}</strong>
            </div>
            <div class="generation-result-stats">
              <div class="result-stat">
                <span>本次接口</span>
                <strong>{{ preparedInterfaces.length }}</strong>
                <small>个</small>
              </div>
              <button
                type="button"
                class="result-stat result-stat-primary result-stat-clickable"
                :disabled="!generatedCaseCount"
                @click="openCasePreview('all')"
              >
                <span>本次生成</span>
                <strong>{{ generatedCaseCount }}</strong>
                <small>个用例 · 点击查看</small>
              </button>
              <button
                type="button"
                class="result-stat result-stat-clickable"
                :disabled="!saveableCaseCount"
                @click="openCasePreview('selected')"
              >
                <span>预计新增</span>
                <strong>{{ saveableCaseCount }}</strong>
                <small>个用例 · 点击查看</small>
              </button>
              <div class="result-stat result-stat-saved">
                <span>实际新增</span>
                <strong>{{ saved ? (saveReport?.new_case_count || 0) : '-' }}</strong>
                <small>保存后显示</small>
              </div>
              <div class="result-stat">
                <span>已有用例</span>
                <strong>{{ existingCaseCount }}</strong>
                <small>个，全部保留</small>
              </div>
              <div class="result-stat">
                <span>生成批次</span>
                <strong>{{ batchGeneration.totalBatches.value || 0 }}</strong>
                <small>批</small>
              </div>
            </div>
            <div class="generation-result-message-stack">
              <div
                class="generation-result-message"
                :class="`is-${resultStatus}`"
                role="status"
                aria-live="polite"
              >
                <span class="generation-result-message-icon">
                  <el-icon>
                    <CircleCheckFilled v-if="resultStatus === 'success'" />
                    <CircleCloseFilled v-else-if="resultStatus === 'error'" />
                    <WarningFilled v-else />
                  </el-icon>
                </span>
                <div class="generation-result-message-copy">
                  <strong>{{ resultStatus === 'success' ? '用例生成完成' : resultTitle }}</strong>
                  <span v-if="resultStatus !== 'success'">{{ generationFailureSummary }}</span>
                  <span v-else>已生成 {{ generatedCaseCount }} 个用例，请点击统计卡片查看并选择需要保存的用例。</span>
                </div>
                <el-button
                  v-if="canRetryGeneration"
                  type="primary"
                  plain
                  size="small"
                  @click="retryFailedGeneration"
                >重试失败接口</el-button>
              </div>
              <div v-if="resultStatus !== 'success' && generationFailureDetails.length" class="generation-failure-details" aria-label="失败原因">
                <div class="generation-failure-details-title">失败详情</div>
                <div
                  v-for="(failure, index) in generationFailureDetails"
                  :key="`${failure.temp_id || failure.name || 'failure'}-${index}`"
                  class="generation-failure-detail"
                >
                  <strong class="generation-failure-detail-name">{{ failure.name || '未知接口' }}</strong>
                  <div class="generation-failure-detail-reason">
                    <span>{{ failure.reason || failure.detail || '未获取到具体失败原因' }}</span>
                    <span v-if="failure.detail && failure.detail !== failure.reason" class="generation-failure-detail-raw">{{ failure.detail }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="wizardStep === 5" class="generation-save-success-body" role="status" aria-live="polite">
          <el-result icon="success" title="用例保存成功">
            <template #sub-title>
              <div class="generation-save-success-summary">
                <ImportResultSummary :stats="saveResultStats">
                  <div>已新增 {{ saveReport?.new_case_count || 0 }} 个用例</div>
                </ImportResultSummary>
              </div>
            </template>
          </el-result>
        </div>
      </div>
    </div>

    <template #footer v-if="wizardStep >= 3">
      <div v-if="wizardStep === 3 && generating" class="generation-progress-dialog-footer">
        <el-button @click="batchGeneration.stop">停止生成</el-button>
      </div>
      <div v-else-if="wizardStep === 3" class="generation-result-footer">
        <div class="generation-result-footer-left">
          <el-button @click="goToModeStep">上一步</el-button>
        </div>
        <div class="generation-result-footer-right">
          <el-button @click="closeAll">关闭</el-button>
          <el-button
            v-if="canRetryGeneration"
            type="primary"
            @click="retryFailedGeneration"
          >重试生成</el-button>
        </div>
      </div>
      <div v-else-if="wizardStep === 4" class="generation-result-footer">
        <div class="generation-result-footer-left">
          <el-button @click="goToModeStep">上一步</el-button>
        </div>
        <div class="generation-result-footer-right">
          <el-button @click="closeAll">关闭</el-button>
          <el-button
            type="primary"
            :loading="saving"
            :disabled="generating || !previewId || !selectedCaseCount"
            @click="saveResults"
          >保存新增用例（{{ selectedCaseCount }}）</el-button>
        </div>
      </div>
      <div v-else-if="wizardStep === 5" class="generation-result-footer">
        <div class="generation-result-footer-right">
          <el-button type="primary" @click="closeAll">完成</el-button>
        </div>
      </div>
    </template>
  </el-dialog>

  <el-dialog
    v-model="casePreviewVisible"
    :title="casePreviewTitle"
    width="min(960px, calc(100vw - 64px))"
    top="8vh"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    class="ai-case-preview-dialog"
    @closed="resetCasePreview"
  >
    <div class="case-preview-dialog-body">
      <div class="case-preview-toolbar">
        <div class="case-preview-search-group">
          <el-input
            v-model="casePreviewKeyword"
            clearable
            placeholder="搜索用例名称、接口名称或 URL"
            class="case-preview-search"
            @keyup.enter="searchCasePreview"
          />
          <el-button type="primary" :loading="casePreviewLoading" @click="searchCasePreview">搜索</el-button>
        </div>
        <div class="case-preview-toolbar-actions">
          <el-checkbox
            :model-value="casePreviewAllSelected"
            :indeterminate="casePreviewSomeSelected"
            :disabled="saved || !casePreviewSelectableKeys.length"
            @change="toggleAllCaseSelection"
          >全选</el-checkbox>
          <span class="case-preview-total">已选 {{ selectedCaseCount }} / 共 {{ casePreviewTotal }} 个用例</span>
        </div>
      </div>

      <div class="case-preview-list">
        <div v-if="casePreviewLoading" class="case-preview-empty">正在查询用例…</div>
        <div v-else-if="!casePreviewTotal" class="case-preview-empty">暂无符合条件的用例</div>
        <div
          v-for="group in casePreviewGroups"
          :key="group.key"
          class="case-preview-group"
          :style="casePreviewGroupStyle(group.key)"
        >
          <div
            class="case-preview-group-header"
            :class="{ 'is-expanded': isCasePreviewGroupExpanded(group.key) }"
            role="button"
            tabindex="0"
            :aria-expanded="isCasePreviewGroupExpanded(group.key)"
            @click="toggleCasePreviewGroup(group.key)"
            @keydown.enter.space.prevent="toggleCasePreviewGroup(group.key)"
          >
            <el-icon class="case-preview-group-chevron" aria-hidden="true"><ArrowRight /></el-icon>
            <span class="case-preview-group-main">
              <strong>{{ group.iface.name || group.iface.url || '未命名接口' }}</strong>
              <el-button
                link
                type="primary"
                size="small"
                class="case-preview-interface-detail"
                @click.stop="openInterfaceDetail(group.iface)"
              >查看详情</el-button>
              <span>{{ group.iface.method || 'GET' }} {{ group.iface.url || '-' }}</span>
            </span>
            <span class="case-preview-group-count">本页 {{ group.entries.length }} 个用例</span>
          </div>

          <div v-if="isCasePreviewGroupExpanded(group.key)" class="case-preview-group-cases">
            <div v-for="entry in group.entries" :key="entry.key" class="case-preview-row">
              <el-checkbox
                :model-value="isCaseSelected(entry.iface, entry.caseIndex)"
                :disabled="!isCaseSavable(entry.iface, entry.caseItem) || saved"
                @change="toggleCaseSelection(entry.iface, entry.caseIndex, $event)"
              />
              <div class="case-preview-main" @click="openCaseEdit(entry.iface, entry.caseIndex)">
                <div class="case-preview-title">
                  <el-tag :type="caseTypeTag(entry.caseItem.case_type)" size="small">{{ caseTypeText(entry.caseItem.case_type) }}</el-tag>
                  <strong>{{ entry.caseItem.name || '未命名用例' }}</strong>
                  <el-button
                    link
                    type="primary"
                    size="small"
                    class="case-preview-case-detail"
                    :disabled="saved"
                    @click.stop="openCaseEdit(entry.iface, entry.caseIndex)"
                  >查看详情</el-button>
                  <span v-if="!isCaseSavable(entry.iface, entry.caseItem)" class="case-preview-status">已有基础用例，不重复保存</span>
                </div>
                <p>{{ entry.caseItem.description || '暂无描述' }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="casePreviewTotal" class="case-preview-pagination">
        <el-pagination
          :current-page="casePreviewPage"
          :page-size="casePreviewPageSize"
          :page-sizes="[10, 50, 100]"
          :total="casePreviewTotal"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="handleCasePreviewPageChange"
          @size-change="handleCasePreviewPageSizeChange"
        />
      </div>
    </div>

    <TestCaseEditDialog
      v-model="caseEditVisible"
      title="查看用例详情"
      :model="editingForm"
      :show-info="false"
      :show-pending-notice="false"
      :active-tab="caseEditTab"
      :saving="caseEditSaving"
      :run-loading="caseRunLoading"
      :response-sample-loader="loadResponseSampleForAssertion"
      @update:active-tab="caseEditTab = $event"
      @run="runEditingCase"
      @save="onCaseSaved"
    />
  </el-dialog>

  <InterfaceDetailDialog
    v-model="interfaceDetailVisible"
    :interface-data="interfaceDetail"
    :readonly="true"
    :show-info="false"
    :show-pending-notice="false"
    :show-debug="false"
  />

  <DebugPanel
    v-model="caseRunVisible"
    append-to-body
    title="运行结果"
    :loading="caseRunLoading"
    :error="caseRunError"
    :steps="caseRunSteps"
    :status-code="0"
    :duration="0"
  />
</template>

<script setup>
import { computed, inject, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, CircleCheckFilled, CircleCloseFilled, Timer, WarningFilled } from '@element-plus/icons-vue'
import AiGenerationModePickerDialog from '@/components/AiGenerationModePickerDialog.vue'
import AiOperationProgress from '@/components/AiOperationProgress.vue'
import DebugPanel from '@/components/DebugPanel.vue'
import InterfaceDetailDialog from '@/components/InterfaceDetailDialog.vue'
import InterfaceCaseGenerationScopePanel from '@/components/InterfaceCaseGenerationScopePanel.vue'
import ImportResultSummary from '@/components/ImportResultSummary.vue'
import TestCaseEditDialog from '@/components/TestCaseEditDialog.vue'
import { getAiModelsForFeature } from '@/api/ai'
import {
  interfaceCaseGenerationEditCase,
  prepareInterfaceCaseGeneration,
  searchInterfaceCaseGenerationCases,
  saveInterfaceCaseGeneration,
  discardInterfaceCaseGeneration,
} from '@/api/aiImport'
import { runTestCase } from '@/api/executor'
import { useAiImportBatchGeneration } from '@/composables/useAiImportGeneration'
import { useAiOperationTimer } from '@/composables/useAiOperationTimer'
import { pickPreferredAiModelId, readLastAiModelId } from '@/utils/aiModelPreference'
import { buildPreviewRunPayload, toCaseEditorForm, toPreviewCase } from '@/utils/aiImportCase'
import { estimateGeneration } from '@/utils/aiImportGeneration'
import { normalizeExecutionStep, pickResponseBodyText } from '@/utils/executionResult'

const INTERFACE_CASE_GENERATE_FEATURE = 'api_interface_case_generate'

const GENERATION_MODE_OPTIONS = [
  {
    value: 'main',
    title: '基础用例',
    badge: '快速生成',
    tagType: 'success',
    desc: '由系统按接口定义生成一条基础请求用例。',
    scope: '已有用例接口不会重复新增基础用例',
    estimate: '每个接口 1 条基础用例',
  },
  {
    value: 'normal',
    title: '常规覆盖',
    badge: '推荐',
    tagType: 'primary',
    desc: '追加基础用例之外的参数校验类逆向场景。',
    scope: '必填缺失、类型/格式/范围错误',
    estimate: '通常每个接口约 3～5 条用例',
  },
  {
    value: 'full',
    title: '全面覆盖',
    badge: '覆盖最广',
    tagType: 'warning',
    desc: '追加逆向、业务异常与边界场景。',
    scope: '越权、资源不存在、极值边界等',
    estimate: '通常每个接口约 5～8 条用例',
  },
]

const props = defineProps({
  modelValue: Boolean,
  projectId: { type: [Number, String], default: null },
  interfaces: { type: Array, default: () => [] },
  interfaceIds: { type: Array, default: () => [] },
  collectionTree: { type: Array, default: () => [] },
  fixedScope: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'done'])
const selectedEnvironment = inject('selectedEnvironment', computed(() => null))
const selectedParameterSet = inject('selectedParameterSet', computed(() => null))

const preparing = ref(false)
const wizardStep = ref(1)
const previewId = ref('')
const interfaceIds = ref([])
const generationTargetIds = ref([])
const preparedInterfaces = ref([])
const modelCandidates = ref([])
const selectedModelId = ref(null)
const selectedMode = ref('normal')
const generationStarted = ref(false)
const generationResult = ref(null)
const saving = ref(false)
const saved = ref(false)
const saveReport = ref(null)
const closing = ref(false)
const selectedCaseKeys = ref(new Set())
const interfaceDetailVisible = ref(false)
const interfaceDetail = ref(null)
const caseEditVisible = ref(false)
const caseEditTab = ref('query')
const editingIface = ref(null)
const editingCaseIndex = ref(-1)
const editingForm = ref(toCaseEditorForm({}, {}))
const caseEditSaving = ref(false)
const caseRunVisible = ref(false)
const caseRunLoading = ref(false)
const caseRunError = ref(null)
const caseRunSteps = ref([])
const casePreviewVisible = ref(false)
const casePreviewMode = ref('all')
const casePreviewKeyword = ref('')
const casePreviewPage = ref(1)
const casePreviewPageSize = ref(10)
const casePreviewItems = ref([])
const casePreviewTotal = ref(0)
const casePreviewSelectableKeys = ref([])
const casePreviewLoading = ref(false)
const expandedCasePreviewGroups = ref(new Set())
const removedCaseKeys = ref(new Set())
let casePreviewRequestSequence = 0
let openSequence = 0

const batchGeneration = useAiImportBatchGeneration({
  previewId: () => previewId.value,
  projectId: () => props.projectId,
  mode: () => selectedMode.value,
  modelId: () => selectedModelId.value,
  nameOf: (tempId) => preparedInterfaces.value.find(i => i.temp_id === tempId)?.name || tempId,
  onBatchDone: (data) => {
    const returned = new Map((Array.isArray(data?.interfaces) ? data.interfaces : [])
      .map(item => [String(item?.temp_id || ''), item]))
    preparedInterfaces.value = preparedInterfaces.value.map(item => (
      returned.has(String(item.temp_id)) ? { ...item, ...returned.get(String(item.temp_id)) } : item
    ))
    syncSelectedCaseKeys()
  },
  onBatchFailed: (ids, failure) => {
    const failedIds = new Set(ids)
    preparedInterfaces.value = preparedInterfaces.value.map(item => (
      failedIds.has(item.temp_id)
        ? {
            ...item,
            gen_status: (item.generated_cases || []).length ? 'partial' : 'failed',
            gen_error: failure?.message || '本批接口处理失败',
          }
        : item
    ))
  },
})

const generating = batchGeneration.generating
const generationTimer = useAiOperationTimer()
const generationElapsedText = generationTimer.elapsedText
const generationHintIndex = ref(0)
let generationHintTimer = null
const GENERATION_HINTS = [
  '正在分析接口定义和请求参数…',
  '正在按当前模式补充校验、异常与边界场景…',
  '正在整理可执行的用例名称、步骤和断言…',
  '接口按批依次生成，每完成一批就会更新结果…',
]
const SYSTEM_GENERATION_HINTS = [
  '正在根据接口定义整理请求参数和基础断言…',
  '正在生成基础请求用例…',
  '正在校验接口方法、路径和参数结构…',
]
const generatedCaseCount = computed(() => preparedInterfaces.value.reduce(
  (sum, item) => sum + (Array.isArray(item.generated_cases)
    ? item.generated_cases.filter((_, index) => !removedCaseKeys.value.has(caseKey(item, index))).length
    : 0),
  0,
))
const generationTargetInterfaces = computed(() => {
  const targetKeys = new Set(generationTargetIds.value.map(id => String(id)))
  if (!targetKeys.size) return preparedInterfaces.value
  return preparedInterfaces.value.filter(item => targetKeys.has(String(item.temp_id)))
})
const existingCaseCount = computed(() => preparedInterfaces.value.reduce(
  (sum, item) => sum + Number(item.existing_case_count || 0),
  0,
))
const saveResultStats = computed(() => ([
  { key: 'interface-count', label: '本次接口', value: preparedInterfaces.value.length, unit: '个' },
  { key: 'new-case-count', label: '新增用例', value: saveReport.value?.new_case_count || 0, unit: '个' },
  { key: 'existing-case-count', label: '已有用例', value: existingCaseCount.value, unit: '个保持不变' },
]))
const selectableCaseCount = computed(() => preparedInterfaces.value.reduce(
  (sum, item) => sum + (Array.isArray(item.generated_cases)
    ? item.generated_cases.filter((caseItem, index) => (
        !removedCaseKeys.value.has(caseKey(item, index)) && isCaseSavable(item, caseItem)
      )).length
    : 0),
  0,
))
const selectedCaseCount = computed(() => preparedInterfaces.value.reduce(
  (sum, item) => sum + (Array.isArray(item.generated_cases)
    ? item.generated_cases.filter((caseItem, index) => (
      !removedCaseKeys.value.has(caseKey(item, index))
      && isCaseSavable(item, caseItem)
      && selectedCaseKeys.value.has(caseKey(item, index))
    )).length
    : 0),
  0,
))
const saveableCaseCount = computed(() => selectedCaseCount.value)
const selectedCasesPayload = computed(() => {
  const payload = {}
  preparedInterfaces.value.forEach(item => {
    if (!Array.isArray(item.generated_cases)) return
    payload[item.temp_id] = item.generated_cases
      .filter((caseItem, index) => (
        !removedCaseKeys.value.has(caseKey(item, index))
        && isCaseSavable(item, caseItem)
        && selectedCaseKeys.value.has(caseKey(item, index))
      ))
  })
  return payload
})
const casePreviewPagedCases = computed(() => casePreviewItems.value)
const casePreviewGroups = computed(() => {
  const groups = new Map()
  casePreviewPagedCases.value.forEach(entry => {
    const key = String(entry?.iface?.temp_id || entry?.iface?.id || entry?.key || '')
    if (!key) return
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        iface: entry.iface,
        entries: [],
      })
    }
    groups.get(key).entries.push(entry)
  })
  return [...groups.values()]
})
const casePreviewAllSelected = computed(() => (
  casePreviewSelectableKeys.value.length > 0
  && casePreviewSelectableKeys.value.every(key => selectedCaseKeys.value.has(key))
))
const casePreviewSomeSelected = computed(() => (
  !casePreviewAllSelected.value
  && casePreviewSelectableKeys.value.some(key => selectedCaseKeys.value.has(key))
))
const casePreviewTitle = computed(() => (
  casePreviewMode.value === 'selected'
    ? `预计新增用例（${casePreviewTotal.value}）`
    : `本次生成用例（${casePreviewTotal.value}）`
))
const generatedInterfaceCount = computed(() => preparedInterfaces.value.filter(
  item => Array.isArray(item.generated_cases)
    && item.generated_cases.some((_, index) => !removedCaseKeys.value.has(caseKey(item, index))),
).length)
const failedInterfaceCount = computed(() => preparedInterfaces.value.filter(
  item => ['failed', 'partial'].includes(item.gen_status),
).length)
const retryGenerationIds = computed(() => {
  const resultRetryIds = Array.isArray(generationResult.value?.retryIds)
    ? generationResult.value.retryIds.filter(Boolean)
    : []
  if (resultRetryIds.length) return resultRetryIds
  return preparedInterfaces.value
    .filter(item => ['failed', 'partial'].includes(item.gen_status))
    .map(item => item.temp_id)
    .filter(Boolean)
})
const canRetryGeneration = computed(() => (
  !saved.value && !generating.value && retryGenerationIds.value.length > 0
))
const hasNoGeneratedCases = computed(() => (
  !!generationResult.value && selectedMode.value !== 'main' && generatedCaseCount.value === 0
))
const isGenerationCanceled = computed(() => generationResult.value?.outcome === 'canceled')
const progressPercentage = computed(() => {
  const targetCount = generationTargetInterfaces.value.length
  if (!targetCount) return 0
  return Math.min(100, Math.round((batchGeneration.doneInterfaces.value / targetCount) * 100))
})
const resultStatus = computed(() => {
  if (isGenerationCanceled.value) return 'warning'
  if (generationResult.value?.outcome === 'failed' || hasNoGeneratedCases.value) return 'error'
  if (generationResult.value?.outcome === 'partial' || generationResult.value?.outcome === 'canceled' || failedInterfaceCount.value) return 'warning'
  return 'success'
})
const generationModelCallsText = computed(() => {
  const { aiCalls } = estimateGeneration(generationTargetInterfaces.value, selectedMode.value)
  return aiCalls ? `预计消耗 ${aiCalls} 次 AI 配额次数` : '不消耗 AI 配额次数'
})
const generationLoadingTitle = computed(() => (
  selectedMode.value === 'main' ? '系统正在生成基础用例' : 'AI 正在生成接口用例'
))
const generationLoadingHint = computed(() => {
  const hints = selectedMode.value === 'main' ? SYSTEM_GENERATION_HINTS : GENERATION_HINTS
  return hints[generationHintIndex.value % hints.length]
})
const wizardTitle = computed(() => (
  wizardStep.value >= 4 ? 'AI生成用例结果' : 'AI生成用例'
))
const resultTitle = computed(() => {
  const source = selectedMode.value === 'main' ? '系统' : 'AI'
  if (!generationResult.value) return `${source}正在生成用例`
  if (generationResult.value.outcome === 'canceled') return `${source}用例生成已停止`
  if (generationResult.value.outcome === 'failed' || hasNoGeneratedCases.value) return `${source}用例生成失败`
  if (failedInterfaceCount.value) return `${source}用例生成完成，部分接口未完整生成`
  return `${source}用例生成完成`
})
const resultSubtitle = computed(() => {
  if (!generationResult.value) return '每完成一批，结果会立即汇总到本页。'
  if (isGenerationCanceled.value) {
    return `已处理 ${generatedInterfaceCount.value} 个接口，已生成 ${generatedCaseCount.value} 个用例；已完成结果仍保留在当前预览中。`
  }
  if (generationResult.value.outcome === 'failed' || hasNoGeneratedCases.value) {
    return generationResult.value.errorMessage || '本次未生成可保存用例，请根据下方失败原因调整模型后重试。'
  }
  return `已处理 ${generatedInterfaceCount.value} 个接口，生成 ${generatedCaseCount.value} 个用例；已有 ${existingCaseCount.value} 个用例保持不变。`
})
const generationFailureDetails = computed(() => (
  Array.isArray(generationResult.value?.failedDetails)
    ? generationResult.value.failedDetails.filter(item => item && (item.detail || item.reason))
    : []
))
const generationFailureSummary = computed(() => {
  const firstFailure = generationFailureDetails.value[0]
  if (firstFailure) {
    const reason = firstFailure.detail || firstFailure.reason || '未获取到具体失败原因'
    return generationFailureDetails.value.length > 1
      ? `${reason}（另有 ${generationFailureDetails.value.length - 1} 个接口失败，详见下方）`
      : reason
  }
  return generationResult.value?.errorMessage || resultSubtitle.value
})
function startGenerationFeedback() {
  generationTimer.start()
  generationHintIndex.value = 0
  if (generationHintTimer) clearInterval(generationHintTimer)
  generationHintTimer = setInterval(() => {
    generationHintIndex.value += 1
  }, 1800)
}

function stopGenerationFeedback() {
  if (generationHintTimer) {
    clearInterval(generationHintTimer)
    generationHintTimer = null
  }
  generationTimer.stop()
}

async function openCasePreview(mode) {
  if (!generatedCaseCount.value || (mode === 'selected' && !saveableCaseCount.value)) return
  casePreviewMode.value = mode === 'selected' ? 'selected' : 'all'
  casePreviewKeyword.value = ''
  casePreviewPage.value = 1
  expandedCasePreviewGroups.value = new Set()
  casePreviewVisible.value = true
  await searchCasePreview({ resetPage: false })
  if (generatedInterfaceCount.value === 1 && casePreviewGroups.value.length === 1) {
    expandedCasePreviewGroups.value = new Set([casePreviewGroups.value[0].key])
  }
}

function resetCasePreview() {
  casePreviewRequestSequence += 1
  casePreviewKeyword.value = ''
  casePreviewPage.value = 1
  casePreviewItems.value = []
  casePreviewTotal.value = 0
  casePreviewSelectableKeys.value = []
  casePreviewLoading.value = false
  expandedCasePreviewGroups.value = new Set()
}

async function searchCasePreview({ resetPage = true } = {}) {
  if (!previewId.value || saved.value) return
  if (resetPage) casePreviewPage.value = 1
  const requestSequence = ++casePreviewRequestSequence
  casePreviewLoading.value = true
  try {
    let requestedPage = casePreviewPage.value
    let result = null
    while (true) {
      result = await searchInterfaceCaseGenerationCases({
        preview_id: previewId.value,
        project_id: Number(props.projectId),
        keyword: casePreviewKeyword.value.trim(),
        scope: casePreviewMode.value,
        page: requestedPage,
        page_size: casePreviewPageSize.value,
        selected_keys: [...selectedCaseKeys.value],
        excluded_keys: [...removedCaseKeys.value],
      })
      if (requestSequence !== casePreviewRequestSequence) return
      const total = Number(result?.total || 0)
      const maxPage = Math.max(1, Math.ceil(total / casePreviewPageSize.value))
      if (requestedPage > maxPage) {
        requestedPage = maxPage
        casePreviewPage.value = maxPage
        continue
      }
      casePreviewTotal.value = total
      casePreviewItems.value = (Array.isArray(result?.items) ? result.items : [])
        .map(toCasePreviewEntry)
        .filter(Boolean)
      casePreviewSelectableKeys.value = Array.isArray(result?.selectable_keys)
        ? result.selectable_keys.map(key => String(key))
        : []
      break
    }
  } catch (error) {
    if (requestSequence === casePreviewRequestSequence) {
      ElMessage.error(errorMessage(error, '查询用例列表失败，请重试'))
    }
  } finally {
    if (requestSequence === casePreviewRequestSequence) casePreviewLoading.value = false
  }
}

function toCasePreviewEntry(item) {
  const iface = preparedInterfaces.value.find(candidate => (
    String(candidate?.temp_id || '') === String(item?.temp_id || '')
  ))
  const caseIndex = Number(item?.case_index)
  const caseItem = iface?.generated_cases?.[caseIndex]
  if (!iface || !Number.isInteger(caseIndex) || !caseItem) return null
  return {
    key: String(item?.key || caseKey(iface, caseIndex)),
    iface,
    caseItem,
    caseIndex,
  }
}

function handleCasePreviewPageChange(page) {
  casePreviewPage.value = page
  searchCasePreview({ resetPage: false })
}

function handleCasePreviewPageSizeChange(size) {
  casePreviewPageSize.value = size
  casePreviewPage.value = 1
  searchCasePreview({ resetPage: false })
}

function isCasePreviewGroupExpanded(key) {
  return expandedCasePreviewGroups.value.has(String(key))
}

const CASE_PREVIEW_GROUP_PALETTE = Object.freeze([
  { bg: '#f4f9ff', border: '#d9ecff', hover: '#edf6ff' },
  { bg: '#f6fbf6', border: '#dff0df', hover: '#eef9ee' },
  { bg: '#fff9f1', border: '#f6e5c7', hover: '#fff5e5' },
  { bg: '#faf7ff', border: '#eadcff', hover: '#f6f0ff' },
])

function casePreviewGroupStyle(key) {
  let hash = 0
  for (const character of String(key || '')) {
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0
  }
  const color = CASE_PREVIEW_GROUP_PALETTE[hash % CASE_PREVIEW_GROUP_PALETTE.length]
  return {
    '--case-preview-group-bg': color.bg,
    '--case-preview-group-border': color.border,
    '--case-preview-group-hover': color.hover,
  }
}

function toggleCasePreviewGroup(key) {
  const groupKey = String(key)
  const next = new Set(expandedCasePreviewGroups.value)
  if (next.has(groupKey)) next.delete(groupKey)
  else next.add(groupKey)
  expandedCasePreviewGroups.value = next
}

function openInterfaceDetail(iface) {
  if (!iface) return
  interfaceDetail.value = iface
  interfaceDetailVisible.value = true
}

function toggleAllCaseSelection(checked) {
  const next = new Set(selectedCaseKeys.value)
  casePreviewSelectableKeys.value.forEach(key => {
    if (checked) next.add(key)
    else next.delete(key)
  })
  selectedCaseKeys.value = next
  if (casePreviewMode.value === 'selected') searchCasePreview({ resetPage: false })
}

function removeCase(iface, index) {
  if (saved.value || !iface?.generated_cases?.[index]) return
  const key = caseKey(iface, index)
  removedCaseKeys.value = new Set([...removedCaseKeys.value, key])
  const next = new Set(selectedCaseKeys.value)
  next.delete(key)
  selectedCaseKeys.value = next
  searchCasePreview({ resetPage: false })
}

function caseKey(iface, index) {
  return `${String(iface?.temp_id || '')}:${index}`
}

function isCaseSavable(iface, caseItem) {
  return Number(iface?.existing_case_count || 0) <= 0 || caseItem?.case_type !== 'main'
}

function syncSelectedCaseKeys() {
  const next = new Set(selectedCaseKeys.value)
  preparedInterfaces.value.forEach(item => {
    if (!Array.isArray(item.generated_cases)) return
    item.generated_cases.forEach((caseItem, index) => {
      if (!removedCaseKeys.value.has(caseKey(item, index)) && isCaseSavable(item, caseItem)) {
        next.add(caseKey(item, index))
      }
    })
  })
  selectedCaseKeys.value = next
}

function isCaseSelected(iface, index) {
  return selectedCaseKeys.value.has(caseKey(iface, index))
}

function toggleCaseSelection(iface, index, checked) {
  const next = new Set(selectedCaseKeys.value)
  const key = caseKey(iface, index)
  if (checked) next.add(key)
  else next.delete(key)
  selectedCaseKeys.value = next
  if (casePreviewMode.value === 'selected') searchCasePreview({ resetPage: false })
}

function caseTypeTag(type) {
  return { main: 'success', reverse: 'warning', abnormal: 'danger' }[type] || 'info'
}

function caseTypeText(type) {
  return { main: '基础用例', reverse: '逆向', abnormal: '异常' }[type] || '基础用例'
}

function caseEditDefaultTab(method) {
  return ['POST', 'PUT', 'PATCH'].includes(String(method || '').toUpperCase()) ? 'body' : 'query'
}

function openCaseEdit(iface, index) {
  const caseItem = iface?.generated_cases?.[index]
  if (!caseItem) return
  editingIface.value = iface
  editingCaseIndex.value = index
  editingForm.value = toCaseEditorForm(caseItem, iface)
  caseEditTab.value = caseEditDefaultTab(editingForm.value.method)
  caseEditVisible.value = true
}

async function onCaseSaved(form) {
  const iface = editingIface.value
  const index = editingCaseIndex.value
  const original = iface?.generated_cases?.[index]
  if (!iface || index < 0 || !original || caseEditSaving.value) return
  const updated = toPreviewCase(form || editingForm.value, original)
  caseEditSaving.value = true
  try {
    const data = await interfaceCaseGenerationEditCase({
      preview_id: previewId.value,
      project_id: Number(props.projectId),
      temp_id: iface.temp_id,
      case_index: index,
      case: updated,
    })
    const savedCase = data?.case && typeof data.case === 'object' ? data.case : updated
    Object.assign(original, savedCase)
    caseEditVisible.value = false
    ElMessage.success('用例详情已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error, '用例详情保存失败，请重试'))
  } finally {
    caseEditSaving.value = false
  }
}

async function runEditingCase() {
  const iface = editingIface.value
  const original = iface?.generated_cases?.[editingCaseIndex.value]
  if (!iface || !original) return
  const current = toPreviewCase(editingForm.value, original)
  const payload = buildPreviewRunPayload({
    environment: selectedEnvironment.value,
    parameterSet: selectedParameterSet.value,
    iface,
    caseData: current,
  })
  if (!payload) {
    ElMessage.warning('请先在页面左下角选择运行环境')
    return
  }
  caseRunVisible.value = true
  caseRunLoading.value = true
  caseRunError.value = null
  caseRunSteps.value = []
  try {
    const result = await runTestCase(payload)
    caseRunSteps.value = (result?.steps || []).map(step => normalizeExecutionStep(step, current.name))
  } catch (error) {
    caseRunError.value = errorMessage(error, '运行失败')
  } finally {
    caseRunLoading.value = false
  }
}

// 断言字段选取：按编辑中的内容现场跑一次，只取响应体文本
async function loadResponseSampleForAssertion() {
  const iface = editingIface.value
  const original = iface?.generated_cases?.[editingCaseIndex.value]
  if (!iface || !original) return ''
  const payload = buildPreviewRunPayload({
    environment: selectedEnvironment.value,
    parameterSet: selectedParameterSet.value,
    iface,
    caseData: toPreviewCase(editingForm.value, original),
  })
  if (!payload) {
    ElMessage.warning('请先在页面左下角选择运行环境')
    return ''
  }
  const result = await runTestCase(payload)
  const step = (result?.steps || [])[0]
  const text = pickResponseBodyText(step?.response)
  if (!text) ElMessage.warning(step?.msg || '本次请求没有返回可解析的响应内容')
  return text
}

function errorMessage(error, fallback) {
  return error?.data?.message || error?.response?.data?.message || error?.message || fallback
}

function resetGenerationSession() {
  interfaceDetailVisible.value = false
  interfaceDetail.value = null
  generationStarted.value = false
  generationResult.value = null
  saved.value = false
  saveReport.value = null
  previewId.value = ''
  generationTargetIds.value = []
  preparedInterfaces.value = []
  selectedCaseKeys.value = new Set()
  removedCaseKeys.value = new Set()
  resetCasePreview()
  batchGeneration.reset()
}

async function open() {
  const sequence = ++openSequence
  interfaceIds.value = Array.from(new Set(
    (props.interfaceIds.length ? props.interfaceIds : props.interfaces.map(item => item?.id))
      .map(id => Number(id)).filter(id => Number.isInteger(id) && id > 0),
  ))
  wizardStep.value = 1
  preparing.value = false
  resetGenerationSession()
}

async function onScopeConfirmed(ids) {
  const normalizedIds = Array.from(new Set(
    (ids || []).map(Number).filter(id => Number.isInteger(id) && id > 0),
  ))
  if (!normalizedIds.length) return
  interfaceIds.value = normalizedIds
  wizardStep.value = 2
  await prepareGeneration(normalizedIds)
}

function goToScopeStep() {
  if (wizardStep.value !== 2 || preparing.value || generating.value || saved.value) return
  const previousPreviewId = previewId.value
  resetGenerationSession()
  if (previousPreviewId) {
    discardInterfaceCaseGeneration(previousPreviewId, Number(props.projectId)).catch(() => {})
  }
  wizardStep.value = 1
}

function goToModeStep() {
  if (generating.value || saved.value) return
  const allTargetIds = preparedInterfaces.value.map(item => item.temp_id).filter(Boolean)
  const targetKeys = new Set(allTargetIds.map(id => String(id)))
  preparedInterfaces.value = preparedInterfaces.value.map(item => (
    targetKeys.has(String(item.temp_id))
      ? { ...item, generated_cases: [], gen_status: 'pending', gen_error: '' }
      : item
  ))
  generationTargetIds.value = allTargetIds
  generationStarted.value = false
  generationResult.value = null
  saveReport.value = null
  selectedCaseKeys.value = new Set()
  removedCaseKeys.value = new Set()
  resetCasePreview()
  batchGeneration.reset()
  wizardStep.value = 2
}

async function prepareGeneration(ids) {
  const sequence = openSequence
  preparing.value = true
  try {
    const [prepared, models] = await Promise.all([
      prepareInterfaceCaseGeneration({
        project_id: Number(props.projectId),
        interface_ids: ids,
      }),
      getAiModelsForFeature(INTERFACE_CASE_GENERATE_FEATURE, { skipErrorToast: true }).catch(() => null),
    ])
    previewId.value = prepared?.preview_id || ''
    preparedInterfaces.value = (prepared?.interfaces || []).map(item => ({
      ...item,
      generated_cases: Array.isArray(item.generated_cases) ? item.generated_cases : [],
      gen_status: item.gen_status || 'pending',
    }))
    generationTargetIds.value = preparedInterfaces.value.map(item => item.temp_id).filter(Boolean)
    modelCandidates.value = models?.candidates || []
    selectedModelId.value = pickPreferredAiModelId(
      modelCandidates.value,
      null,
      readLastAiModelId(),
    )
    if (!previewId.value || !preparedInterfaces.value.length) throw new Error('接口准备结果为空，请刷新后重试')
    if (sequence !== openSequence || !props.modelValue) return
    preparing.value = false
  } catch (error) {
    if (sequence !== openSequence || !props.modelValue) return
    preparing.value = false
    ElMessage.error(errorMessage(error, '准备接口用例生成失败，请重试'))
    closeAll()
  }
}

async function requestStartGeneration(options) {
  const targetInterfaces = generationTargetInterfaces.value
  const targetExistingCaseCount = targetInterfaces.filter(item => Number(item.existing_case_count || 0) > 0).length
  if (targetExistingCaseCount > 0) {
    try {
      await ElMessageBox.confirm(
        `已选 ${targetInterfaces.length} 个接口，其中 ${targetExistingCaseCount} 个接口下已有用例，继续生成可能会生成重复的用例，确定继续 AI 生成测试用例吗？`,
        '生成确认',
        { confirmButtonText: '确定继续', cancelButtonText: '返回修改', type: 'warning' },
      )
    } catch {
      return
    }
  }
  await startGeneration(options)
}

async function startGeneration({ mode, modelId }) {
  const isRetry = generationStarted.value && !!generationResult.value
  selectedMode.value = mode
  selectedModelId.value = modelId
  generationStarted.value = true
  wizardStep.value = 3
  generationResult.value = null
  if (!isRetry) selectedCaseKeys.value = new Set()
  startGenerationFeedback()
  try {
    const result = await batchGeneration.run(
      generationTargetIds.value.length
        ? generationTargetIds.value
        : preparedInterfaces.value.map(item => item.temp_id),
    )
    generationResult.value = result
    const staysOnGenerationStep = result?.outcome === 'failed'
      || (result?.outcome === 'canceled' && generatedCaseCount.value === 0)
    if (result && !staysOnGenerationStep) wizardStep.value = 4
  } finally {
    stopGenerationFeedback()
  }
}

function retryFailedGeneration() {
  if (generating.value || saved.value) return
  const retryIds = retryGenerationIds.value
  if (!retryIds.length) return
  generationTargetIds.value = Array.from(new Set(retryIds))
  wizardStep.value = 2
}

function onModelsRefreshed(candidates) {
  modelCandidates.value = Array.isArray(candidates) ? candidates : []
  selectedModelId.value = pickPreferredAiModelId(modelCandidates.value, selectedModelId.value, readLastAiModelId())
}

async function saveResults() {
  if (saving.value || generating.value || !previewId.value || !saveableCaseCount.value) return
  saving.value = true
  try {
    const result = await saveInterfaceCaseGeneration({
      preview_id: previewId.value,
      project_id: Number(props.projectId),
      selected_cases: selectedCasesPayload.value,
    })
    saveReport.value = result || {}
    saved.value = true
    previewId.value = ''
    wizardStep.value = 5
    emit('done', result)
  } catch (error) {
    ElMessage.error(errorMessage(error, '保存生成用例失败，请重试'))
  } finally {
    saving.value = false
  }
}

async function closeAll({ emitUpdate = true } = {}) {
  if (closing.value) return false
  closing.value = true
  try {
    const shouldConfirm = !!previewId.value && !saved.value && (
      generating.value || generatedCaseCount.value > 0
    )
    if (shouldConfirm && !saved.value) {
      try {
        await ElMessageBox.confirm(
          '本次生成结果尚未保存，关闭后将丢失，确定关闭吗？',
          '关闭确认',
          { confirmButtonText: '确定关闭', cancelButtonText: '继续查看', type: 'warning' },
        )
      } catch {
        return false
      }
    }
    // 先关闭界面，再异步清理预览，避免清理接口的网络耗时阻塞弹窗关闭。
    if (emitUpdate) emit('update:modelValue', false)
    if (previewId.value && !saved.value) {
      await discardInterfaceCaseGeneration(previewId.value, Number(props.projectId)).catch(() => {})
    }
    casePreviewVisible.value = false
    interfaceDetailVisible.value = false
    interfaceDetail.value = null
    caseEditVisible.value = false
    caseRunVisible.value = false
    caseRunError.value = null
    caseRunSteps.value = []
    stopGenerationFeedback()
    if (generating.value) batchGeneration.stop()
    batchGeneration.reset()
    openSequence += 1
    preparing.value = false
    wizardStep.value = 1
    generationStarted.value = false
    previewId.value = ''
    selectedCaseKeys.value = new Set()
    removedCaseKeys.value = new Set()
    resetCasePreview()
    return true
  } finally {
    closing.value = false
  }
}

async function handleWizardBeforeClose(done) {
  const closed = await closeAll()
  if (closed) done()
}

watch(() => props.modelValue, visible => {
  if (visible) open()
  else {
    preparing.value = false
    wizardStep.value = 1
    interfaceDetailVisible.value = false
    interfaceDetail.value = null
    if (generating.value) batchGeneration.stop()
  }
})
</script>

<style scoped>
.ai-generation-wizard { display: flex; flex-direction: column; gap: 18px; width: 100%; height: 100%; min-width: 0; min-height: 0; overflow: hidden; }
.ai-generation-wizard-steps { display: flex; padding: 0 12px; }
.ai-generation-wizard-steps :deep(.el-step) { flex: 1 1 0; min-width: 0; }
.ai-generation-wizard-steps :deep(.el-step__title) { font-size: 15px; font-weight: 600; line-height: 1.35; }
.ai-generation-wizard-steps :deep(.el-step__description) { min-height: 18px; font-size: 12px; line-height: 1.4; }
.ai-generation-wizard-body { display: flex; flex: 1 1 auto; flex-direction: column; width: 100%; min-width: 0; min-height: 0; overflow: hidden; }
.ai-generation-scope-step,
.ai-generation-mode-step { display: flex; flex: 1 1 auto; flex-direction: column; width: 100%; min-width: 0; min-height: 0; }
.generation-result-body { display: flex; flex: 1 1 auto; flex-direction: column; gap: 12px; min-width: 0; min-height: 0; overflow: visible; }
.generation-result-content { display: flex; flex: 0 0 auto; flex-direction: column; gap: 12px; min-width: 0; }
.generation-result-runtime { display: inline-flex; align-items: center; align-self: flex-start; gap: 8px; color: var(--el-text-color-secondary); font-size: 14px; font-weight: 600; }
.generation-result-runtime .el-icon { color: var(--el-color-primary); font-size: 18px; }
.generation-result-runtime strong { color: var(--el-text-color-primary); font-size: 18px; font-variant-numeric: tabular-nums; }
.generation-result-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.result-stat {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: space-between;
  gap: 4px;
  min-width: 0;
  min-height: 78px;
  box-sizing: border-box;
  padding: 10px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: #fff;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  position: relative;
  overflow: hidden;
}
.result-stat-clickable {
  width: 100%;
  appearance: none;
  cursor: pointer;
  font: inherit;
  text-align: left;
  transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease;
}
.result-stat-clickable:not(:disabled) { border-color: #93c5fd; background: #eef6ff; }
.result-stat-clickable:hover:not(:disabled) { border-color: #93c5fd; box-shadow: 0 6px 16px rgba(37, 99, 235, .08); transform: translateY(-1px); }
.result-stat-clickable:disabled { cursor: default; opacity: .62; }
.result-stat-clickable:focus { outline: none; }
.result-stat-clickable:focus-visible { outline: 2px solid #93c5fd; outline-offset: -3px; }
.result-stat::before { content: ''; position: absolute; inset: 0 auto 0 0; width: 3px; background: #cbd5e1; }
.result-stat > span { color: var(--el-text-color-secondary); }
.result-stat strong { color: var(--el-text-color-primary); font-size: 27px; line-height: 1; font-variant-numeric: tabular-nums; }
.result-stat small { color: var(--el-text-color-secondary); font-size: 12px; white-space: nowrap; }
.result-stat-primary { border-color: #93c5fd; background: linear-gradient(145deg, #e4f0ff 0%, #f0f7ff 100%); color: var(--el-color-primary-dark-2); }
.result-stat-primary.result-stat-clickable:not(:disabled) { background: linear-gradient(145deg, #dcecff 0%, #edf6ff 100%); }
.result-stat-primary::before { background: var(--el-color-primary); }
.result-stat-primary > span, .result-stat-primary small { color: var(--el-color-primary-dark-2); }
.result-stat-primary strong { color: var(--el-color-primary); }
.result-stat-saved::before { background: var(--el-color-success); }
.generation-progress-dialog-body {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  min-width: 0;
  min-height: 0;
  box-sizing: border-box;
}
.generation-failure-body {
  display: flex;
  flex: 1 1 auto;
  align-items: stretch;
  min-width: 0;
  min-height: 0;
  overflow: visible;
}
.generation-failure-content { display: flex; flex: 1 1 auto; align-items: stretch; flex-direction: column; gap: 12px; width: 100%; min-width: 0; min-height: 0; }
.generation-failure-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 22px 24px;
  border: 1px solid #fecaca;
  border-radius: 12px;
  background: #fef2f2;
}
.generation-failure-card.is-warning { border-color: #fde68a; background: #fffbeb; }
.generation-failure-card.is-warning .generation-result-message-icon { background: #fef3c7; color: #d97706; }
.generation-failure-card.is-error .generation-result-message-icon { background: #fee2e2; color: #dc2626; }
.generation-failure-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  height: auto;
  max-height: min(300px, 34vh);
  min-height: 0;
  box-sizing: border-box;
  overflow-y: auto;
  padding: 10px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}
.generation-failure-details-title { flex: 0 0 auto; color: var(--el-text-color-primary); font-size: 13px; font-weight: 600; line-height: 1.5; }
.generation-failure-detail { display: flex; align-items: flex-start; gap: 10px; min-width: 0; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.5; }
.generation-failure-detail-name { flex: 0 1 180px; min-width: 120px; color: var(--el-text-color-primary); overflow-wrap: anywhere; }
.generation-failure-detail-reason { display: flex; flex: 1 1 auto; flex-direction: column; gap: 2px; min-width: 0; overflow-wrap: anywhere; white-space: pre-wrap; }
.generation-failure-detail-raw { color: var(--el-text-color-secondary); }
.generation-failure-detail-empty { padding-top: 2px; }
.generation-progress-dialog-footer {
  display: flex;
  justify-content: center;
  width: 100%;
}
.generation-result-message {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  box-sizing: border-box;
  padding: 10px 14px;
  border: 1px solid #dbe4ee;
  border-radius: 12px;
  background: #f8fafc;
}
.generation-result-message-stack { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.generation-result-message.is-warning { border-color: #fde68a; background: #fffbeb; }
.generation-result-message.is-error { border-color: #fecaca; background: #fef2f2; }
.generation-result-message-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #e0f2fe;
  color: #2563eb;
  font-size: 21px;
}
.generation-result-message.is-warning .generation-result-message-icon { background: #fef3c7; color: #d97706; }
.generation-result-message.is-error .generation-result-message-icon { background: #fee2e2; color: #dc2626; }
.generation-result-message-copy { display: flex; flex: 1 1 auto; flex-direction: column; gap: 4px; min-width: 0; }
.generation-result-message-copy strong { color: var(--el-text-color-primary); font-size: 16px; line-height: 1.35; }
.generation-result-message-copy span {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow-wrap: anywhere;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
}
.generation-failure-card .generation-result-message-copy span { display: block; overflow: visible; -webkit-line-clamp: unset; }
.generation-save-result { border-color: #86efac; background: linear-gradient(145deg, #ecfdf3 0%, #f7fff9 100%); }
.generation-save-result-icon { background: #dcfce7; color: #16a34a; }
.generation-save-result-copy strong { color: #166534; font-size: 20px; }
.generation-save-result-copy span { color: #4b5563; }
.generation-save-success-body { display: flex; flex: 0 1 auto; align-items: center; justify-content: center; min-width: 0; padding: 0 0 4px; }
.generation-save-success-body :deep(.el-result) { padding: 0; }
.generation-save-success-body :deep(.el-result__subtitle) { width: 100%; margin-top: 8px; }
.generation-save-success-summary { width: min(100%, 820px); margin: 0 auto; }
.generation-save-success-summary :deep(.import-result-stats) { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.case-preview-dialog-body { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.case-preview-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.case-preview-search-group { display: flex; align-items: center; gap: 8px; min-width: 0; }
.case-preview-search { max-width: 420px; }
.case-preview-toolbar-actions { display: flex; align-items: center; justify-content: flex-end; gap: 14px; min-width: 0; }
.case-preview-total { flex: 0 0 auto; color: var(--el-text-color-secondary); font-size: 13px; }
.case-preview-list { max-height: min(58vh, 540px); overflow-y: auto; border-top: 1px solid #e5e7eb; border-bottom: 1px solid #e5e7eb; }
.case-preview-empty { padding: 64px 16px; color: var(--el-text-color-secondary); font-size: 13px; text-align: center; }
.case-preview-group {
  overflow: hidden;
  border: 1px solid var(--case-preview-group-border);
  border-radius: 9px;
  background: var(--case-preview-group-bg);
}
.case-preview-group + .case-preview-group { margin-top: 10px; }
.case-preview-group-header {
  display: flex; align-items: center; gap: 10px; width: 100%; min-width: 0;
  padding: 14px 6px; border: 0; background: transparent; color: inherit; text-align: left; cursor: pointer;
}
.case-preview-group-header:hover { background: var(--case-preview-group-hover); }
.case-preview-group-chevron { flex: 0 0 auto; color: var(--el-text-color-secondary); transition: transform .18s ease; }
.case-preview-group-header.is-expanded .case-preview-group-chevron { transform: rotate(90deg); }
.case-preview-group-main { display: flex; align-items: baseline; gap: 8px; min-width: 0; flex: 1; }
.case-preview-group-main strong { overflow: hidden; color: var(--el-text-color-primary); font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.case-preview-group-main span { overflow: hidden; color: var(--el-text-color-secondary); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.case-preview-group-count { flex: 0 0 auto; color: var(--el-text-color-secondary); font-size: 12px; }
.case-preview-interface-detail,
.case-preview-case-detail { flex: 0 0 auto; margin: 0; padding: 0; }
.case-preview-group-cases { background: transparent; }
.case-preview-row { display: grid; grid-template-columns: 20px minmax(0, 1fr); align-items: center; gap: 12px; min-width: 0; padding: 14px 6px; border-top: 1px solid var(--case-preview-group-border); }
.case-preview-group-cases .case-preview-row { padding-left: 34px; }
.case-preview-row:first-child { border-top: 1px solid var(--case-preview-group-border); }
.case-preview-main { min-width: 0; cursor: pointer; }
.case-preview-title { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-width: 0; }
.case-preview-title strong { overflow: hidden; color: var(--el-text-color-primary); font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.case-preview-status { flex: 0 0 auto; color: var(--el-text-color-secondary); font-size: 12px; }
.case-preview-interface { overflow: hidden; margin-top: 5px; color: var(--el-text-color-secondary); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.case-preview-main p { overflow: hidden; margin: 5px 0 0; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; text-overflow: ellipsis; white-space: nowrap; }
.case-preview-pagination { display: flex; justify-content: flex-end; padding-top: 2px; }
.generation-result-footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; width: 100%; }
.generation-result-footer-left,
.generation-result-footer-right { display: flex; align-items: center; gap: 8px; }
:global(.el-dialog.ai-generation-dialog) { border-radius: 16px; overflow: hidden; box-shadow: 0 24px 70px rgba(15, 23, 42, .18); }
:global(.el-dialog.ai-generation-dialog .el-dialog__header) { padding: 22px 28px 16px; margin-right: 0; border-bottom: 1px solid #edf1f6; }
:global(.el-dialog.ai-generation-dialog .el-dialog__title) { color: #1e293b; font-size: 20px; font-weight: 700; }
:global(.el-dialog.ai-generation-dialog .el-dialog__body) { padding: 8px 28px 0; }
:global(.el-dialog.ai-generation-dialog .el-dialog__footer) { padding: 14px 28px 20px; border-top: 1px solid #edf1f6; }
:global(.el-dialog.ai-batch-result-dialog) { border-radius: 16px; overflow: hidden; box-shadow: 0 24px 70px rgba(15, 23, 42, .18); }
:global(.el-dialog.ai-batch-result-dialog .el-dialog__header) { padding: 22px 28px 16px; margin-right: 0; border-bottom: 1px solid #edf1f6; }
:global(.el-dialog.ai-batch-result-dialog .el-dialog__title) { color: #1e293b; font-size: 20px; font-weight: 700; }
:global(.el-dialog.ai-batch-result-dialog) { max-height: calc(100vh - 48px); display: flex; flex-direction: column; }
:global(.el-dialog.ai-batch-result-dialog .el-dialog__body) { flex: 1; min-height: 0; padding: 20px 28px 16px; overflow-y: auto; }
:global(.el-dialog.ai-batch-result-dialog .el-dialog__footer) { padding: 14px 28px 20px; border-top: 1px solid #edf1f6; }
:global(.el-dialog.ai-case-preview-dialog) { border-radius: 16px; overflow: hidden; box-shadow: 0 24px 70px rgba(15, 23, 42, .18); }
:global(.el-dialog.ai-case-preview-dialog .el-dialog__header) { padding: 22px 28px 16px; margin-right: 0; border-bottom: 1px solid #edf1f6; }
:global(.el-dialog.ai-case-preview-dialog .el-dialog__title) { color: #1e293b; font-size: 20px; font-weight: 700; }
:global(.el-dialog.ai-case-preview-dialog .el-dialog__body) { padding: 20px 28px 22px; }
:global(.el-dialog.ai-generation-wizard-dialog) { max-height: calc(100vh - 48px); margin: 24px auto; display: flex; flex-direction: column; box-sizing: border-box; border-radius: 16px; overflow: hidden; box-shadow: 0 24px 70px rgba(15, 23, 42, .18); }
:global(.el-dialog.ai-generation-wizard-dialog .el-dialog__header) { flex: 0 0 auto; box-sizing: border-box; padding: 22px 28px 16px; margin-right: 0; border-bottom: 1px solid #edf1f6; }
:global(.el-dialog.ai-generation-wizard-dialog .el-dialog__title) { color: #1e293b; font-size: 20px; font-weight: 700; }
:global(.el-dialog.ai-generation-wizard-dialog .el-dialog__body) { display: flex; flex: 1 1 auto; box-sizing: border-box; min-height: 0; padding: 20px 28px 16px; overflow: hidden; }
:global(.el-dialog.ai-generation-wizard-dialog .el-dialog__footer) { flex: 0 0 auto; box-sizing: border-box; min-height: 0; padding: 14px 28px 20px; border-top: 1px solid #edf1f6; }
:global(.el-dialog.ai-generation-wizard-dialog.is-scope-step),
:global(.el-dialog.ai-generation-wizard-dialog.is-mode-step),
:global(.el-dialog.ai-generation-wizard-dialog.is-progress-step),
:global(.el-dialog.ai-generation-wizard-dialog.is-failure-step),
:global(.el-dialog.ai-generation-wizard-dialog.is-result-step),
:global(.el-dialog.ai-generation-wizard-dialog.is-saved-step) { width: min(1120px, calc(100vw - 48px)) !important; max-height: calc(100vh - 48px); }
:global(.el-dialog.ai-generation-wizard-dialog.is-scope-step) { height: min(720px, calc(100vh - 48px)); }
:global(.el-dialog.ai-generation-wizard-dialog.is-mode-step) { height: min(580px, calc(100vh - 48px)); }
:global(.el-dialog.ai-generation-wizard-dialog.is-progress-step) { height: min(620px, calc(100vh - 48px)); }
:global(.el-dialog.ai-generation-wizard-dialog.is-failure-step) { height: min(600px, calc(100vh - 48px)); }
:global(.el-dialog.ai-generation-wizard-dialog.is-result-step) { height: min(620px, calc(100vh - 48px)); }
:global(.el-dialog.ai-generation-wizard-dialog.is-saved-step) { height: min(520px, calc(100vh - 48px)); }
:global(.el-dialog.ai-generation-wizard-dialog.is-scope-step .el-dialog__body) { flex: 1; padding-bottom: 16px; overflow: hidden; }
:global(.el-dialog.ai-generation-wizard-dialog.is-scope-step .ai-generation-wizard) { height: 100%; gap: 14px; }
:global(.el-dialog.ai-generation-wizard-dialog.is-scope-step .ai-generation-wizard-body) { flex: 1 1 auto; overflow: hidden; }
:global(.el-dialog.ai-generation-wizard-dialog.is-scope-step .scope-panel) { width: 100%; height: 100%; align-self: stretch; overflow: hidden; }
:global(.el-dialog.ai-generation-wizard-dialog.is-scope-step .scope-table-scroll) { flex: 1 1 auto; min-height: 0; }
:global(.el-dialog.ai-generation-wizard-dialog.is-scope-step .el-dialog__footer) { padding-top: 10px; padding-bottom: 12px; }
:global(.el-dialog.ai-generation-wizard-dialog.is-mode-step .el-dialog__body) { flex: 1; padding-bottom: 16px; overflow: hidden; }
:global(.el-dialog.ai-generation-wizard-dialog.is-mode-step .ai-generation-wizard) { height: 100%; gap: 12px; }
:global(.el-dialog.ai-generation-wizard-dialog.is-mode-step .ai-generation-wizard-body) { flex: 1 1 auto; justify-content: center; overflow: hidden; }
:global(.el-dialog.ai-generation-wizard-dialog.is-mode-step .ai-generation-mode-step) { flex: 0 1 auto; }
:global(.el-dialog.ai-generation-wizard-dialog.is-mode-step .gen-settings-embedded) { display: flex; flex: 0 1 auto; min-height: 0; }
:global(.el-dialog.ai-generation-wizard-dialog.is-mode-step .gen-settings-body) { width: 100%; min-height: 0; }
:global(.el-dialog.ai-generation-wizard-dialog.is-mode-step .gen-settings-footer) { flex: 0 0 auto; padding-top: 10px; }
:global(.el-dialog.ai-generation-wizard-dialog.is-failure-step .ai-generation-wizard-body) { justify-content: flex-start; overflow-y: auto; }
:global(.el-dialog.ai-generation-wizard-dialog.is-failure-step .generation-failure-body) { min-height: 0; flex: 1 1 auto; }
:global(.el-dialog.ai-generation-wizard-dialog.is-result-step .el-dialog__body) { flex: 1; padding-bottom: 16px; overflow: hidden; }
:global(.el-dialog.ai-generation-wizard-dialog.is-result-step .ai-generation-wizard) { height: 100%; gap: 12px; }
:global(.el-dialog.ai-generation-wizard-dialog.is-result-step .ai-generation-wizard-body) { flex: 1 1 auto; justify-content: center; overflow: hidden; }
:global(.el-dialog.ai-generation-wizard-dialog.is-result-step .generation-result-body) { flex: 0 1 auto; min-height: 0; overflow: visible; }
:global(.el-dialog.ai-generation-wizard-dialog.is-result-step .generation-progress-dialog-body) { min-height: 0; }
:global(.el-dialog.ai-generation-wizard-dialog.is-result-step .el-dialog__footer) { padding-top: 10px; padding-bottom: 12px; }
:global(.el-dialog.ai-generation-wizard-dialog.is-saved-step .el-dialog__body) { flex: 1; padding-bottom: 16px; overflow: hidden; }
:global(.el-dialog.ai-generation-wizard-dialog.is-saved-step .ai-generation-wizard) { height: 100%; gap: 12px; }
:global(.el-dialog.ai-generation-wizard-dialog.is-saved-step .ai-generation-wizard-body) { flex: 1 1 auto; justify-content: center; overflow: hidden; }
:global(.el-dialog.ai-generation-wizard-dialog.is-saved-step .el-dialog__footer) { padding-top: 10px; padding-bottom: 12px; }
:global(.el-dialog.ai-generation-wizard-dialog.is-saved-step .generation-result-footer) { justify-content: flex-end; }
@media (max-width: 680px) {
  .generation-result-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .generation-save-success-summary :deep(.import-result-stats) { grid-template-columns: 1fr; }
  .generation-result-footer { align-items: stretch; flex-direction: column; }
  .case-preview-toolbar { align-items: stretch; flex-direction: column; gap: 8px; }
  .case-preview-search-group { align-items: stretch; }
  .case-preview-search { max-width: none; }
  .case-preview-toolbar-actions { justify-content: space-between; }
  .generation-failures { align-items: stretch; flex-direction: column; }
  .generation-failure-detail { flex-direction: column; gap: 4px; }
  .generation-failure-detail-name { flex: 0 0 auto; min-width: 0; }
  .case-preview-row { grid-template-columns: 20px minmax(0, 1fr); }
  .case-preview-group-cases .case-preview-row { padding-left: 34px; }
  .generation-result-footer-right { justify-content: flex-end; }
}
</style>
