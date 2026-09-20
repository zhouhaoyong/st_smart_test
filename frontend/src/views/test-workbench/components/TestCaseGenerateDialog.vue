<template>
  <el-dialog
    v-model="visible"
    title="AI 生成测试用例"
    width="1080px"
    top="4vh"
    :close-on-click-modal="false"
    :before-close="onBeforeClose"
    @closed="reset"
  >
    <el-steps :active="activeStep" finish-status="success" simple class="generate-steps wizard-steps-green">
      <el-step title="选择需求" description="选择已确认的需求" />
      <el-step title="确认模型" description="确认模型与生成规则" />
      <el-step title="AI 对话" description="确认边界、生成并保存用例" />
    </el-steps>

    <!-- 步骤一：选择需求。整体居中，需求类型置顶，下方选择来源需求。 -->
    <section v-show="activeStep === 0" class="step-panel select-panel">
      <el-alert v-if="sourceError" :title="sourceError" type="error" show-icon :closable="false" class="inline-alert" />
      <div class="select-body">
        <TestCaseSourceSelector
          ref="sourceSelectorRef"
          v-model:source-type="sourceType"
          v-model:selected-sources="selectedSources"
          :project-id="projectId"
          :scope="scope"
          @error="sourceError = $event"
        />
      </div>
    </section>

    <!-- 步骤二：确认模型。复用开始确认组件，仅确认模型与生成规则，本步不调用模型。 -->
    <RefinementStartConfirm
      v-show="activeStep === 1"
      class="step-panel confirm-panel"
      :model-info="modelInfo"
      :model-candidates="modelCandidates"
      :selected-model-id="selectedModelId"
      :model-load-error="modelLoadError"
      :can-start="canStart"
      title="确认本次模型"
      description="确认本次用于生成测试用例的模型与生成规则；点击「进入 AI 对话」后，AI 才会发起第一次调用。"
      start-label="进入 AI 对话"
      cancel-label="上一步"
      :rule-title="workflow.ruleTitle"
      :rule-text="workflow.ruleText"
      :usage-text="workflow.usageText"
      @cancel="activeStep = 0"
      @start="enterConversation"
      @update:selected-model-id="selectModel($event)"
    />

    <!-- 步骤三：AI 对话 + 预览保存。对话内嵌于当前弹窗：先边界确认，用户确认后 AI 在对话内生成用例，
         点击气泡「查看并保存测试用例」后，同一步内切换为预览表格进行勾选与保存。 -->
    <section v-show="activeStep === 2 && !previewMode" class="step-panel conversation-step">
      <AiConversationFrame>
        <div class="ai-status">
        <el-tag class="ai-status-tag" :type="statusType" effect="light" size="small" round>
          <span v-if="streaming" class="status-dot" />{{ statusLabel }}
        </el-tag>
        <span class="ai-status-hint">{{ workflow.sessionHint }}</span>
        </div>

        <div class="conversation-wrap">
        <el-scrollbar ref="scrollRef" class="conversation-body" @scroll="onScroll">
          <RefinementMessageCard
            v-for="(message, index) in messages"
            :key="message.id"
            :message="message"
            :copyable="messageCopyable(message, index)"
            :supports-reasoning="!!modelInfo?.supports_reasoning"
            :active-action-id="composeMsgId"
            :end-action-id="endActionMsgId"
            :end-label="workflow.endActionLabel"
            :end-loading="composing"
            :merge-mode="false"
            :active-question-id="activeQuestionMsgId"
            :answer-draft="answerDraft"
            :can-submit="canSend"
            :can-end="canEnd"
            :retry-selection-required="retrySelectionRequired"
            :retry-model-loading="retryModelLoading"
            :is-latest-message="index === messages.length - 1"
            @copy="copyText"
            @case-preview="openGeneratedCases"
            @end="endConversation"
            @answer-change="onAnswerChange"
            @submit="send"
            @supplement="sendSupplement"
            @retry-open="refreshRetryCandidates"
            @retry="retry"
          />
          <el-empty v-if="!messages.length && !streaming" description="正在发起首次生成规则确认…" :image-size="72" />
        </el-scrollbar>

        <div v-show="messages.length" class="scroll-nav-actions">
          <el-button v-show="!stickTop" class="scroll-nav-btn" circle :icon="ArrowUp" aria-label="回到顶部" @click="scrollToTopManually" />
          <el-button v-show="!stickBottom" class="scroll-nav-btn" circle :icon="ArrowDown" aria-label="回到底部" @click="scrollToBottomManually" />
        </div>
        </div>
      </AiConversationFrame>

      <div v-if="streaming" class="stream-action-bar">
        <AiStopStreamButton @confirm="stopStream" />
      </div>
      <p v-else class="ai-quota-tip">{{ workflow.actionHint }}</p>
    </section>

    <section v-show="activeStep === 2 && previewMode" class="step-panel preview-panel">
      <div class="step-heading">
        <div>
          <h4>预览生成结果</h4>
          <p>默认全选。取消勾选的用例不会保存；可先查看详情或编辑，再保存所选用例。</p>
        </div>
        <el-tag type="success" effect="plain">已生成 {{ cases.length }} 条</el-tag>
      </div>
      <div v-if="qualitySummary" class="quality-summary">
        <span>类型：{{ qualitySummary.case_type_text }}</span>
        <span>优先级：{{ qualitySummary.priority_text }}</span>
        <span v-for="warning in qualitySummary.warnings" :key="warning" class="quality-summary__warning">{{ warning }}</span>
      </div>
      <el-table :data="cases" height="440" row-key="_key" class="preview-table">
        <el-table-column width="50">
          <template #header><el-checkbox v-model="allChecked" /></template>
          <template #default="{ row }"><el-checkbox v-model="row.checked" /></template>
        </el-table-column>
        <el-table-column label="关联需求" min-width="190" show-overflow-tooltip>
          <template #default="{ row }"><el-button link type="primary" class="preview-table-link" :title="row.source_title || '—'" @click="openSourceRequirement(row)">{{ row.source_title }}</el-button></template>
        </el-table-column>
        <el-table-column label="用例标题" min-width="280" show-overflow-tooltip>
          <template #default="{ row }"><el-button link type="primary" class="preview-table-link" :title="row.title || '—'" @click="openPreviewCase(row)">{{ row.title }}</el-button></template>
        </el-table-column>
        <el-table-column prop="case_type" label="用例类型" width="110" show-overflow-tooltip />
        <el-table-column label="优先级" width="90"><template #default="{ row }">{{ displayPriority(row.priority) }}</template></el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openPreviewCase(row, true)">编辑用例</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button v-if="activeStep === 0" type="primary" :disabled="!sourceIds.length || !!sourceError" @click="activeStep = 1">下一步</el-button>
      <el-button v-else-if="activeStep === 2 && !previewMode" :disabled="streaming || composing" @click="backFromConversation">上一步</el-button>
      <template v-else-if="activeStep === 2 && previewMode">
        <el-button @click="previewMode = false">返回对话</el-button>
        <el-button type="primary" :loading="saving" :disabled="!selectedCount || hasIncompletePriority" @click="save">保存所选（{{ selectedCount }}）</el-button>
      </template>
    </template>
  </el-dialog>

  <el-dialog v-model="previewCaseDialog.visible" :title="previewCaseDialog.editing ? '编辑生成用例' : '测试用例详情'" width="720px" append-to-body>
    <template v-if="previewCaseDialog.editing">
      <el-form label-width="88px" class="preview-case-form">
        <el-form-item label="用例标题"><el-input v-model="previewCaseDraft.title" /></el-form-item>
        <el-form-item label="场景"><el-input v-model="previewCaseDraft.scenario" /></el-form-item>
        <el-form-item label="用例类型"><el-input v-model="previewCaseDraft.case_type" /></el-form-item>
        <el-form-item label="前置条件"><el-input v-model="previewCaseDraft.precondition" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="测试数据"><el-input v-model="previewCaseDraft.test_data_text" type="textarea" :rows="3" placeholder="请输入合法 JSON 对象" /></el-form-item>
        <el-form-item label="操作步骤"><el-input v-model="previewCaseDraft.steps_text" type="textarea" :rows="5" placeholder="每行一步" /></el-form-item>
        <el-form-item label="预期结果"><el-input v-model="previewCaseDraft.expected_result" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="优先级"><el-select v-model="previewCaseDraft.priority" style="width: 100%"><el-option v-for="item in ['P0', 'P1', 'P2', 'P3']" :key="item" :label="item" :value="item" /></el-select></el-form-item>
      </el-form>
    </template>
    <template v-else>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="关联需求" :span="2">{{ previewCaseDialog.item?.source_title || '—' }}</el-descriptions-item>
        <el-descriptions-item label="优先级">{{ displayPriority(previewCaseDialog.item?.priority) }}</el-descriptions-item>
        <el-descriptions-item label="用例标题" :span="2">{{ previewCaseDialog.item?.title || '—' }}</el-descriptions-item>
        <el-descriptions-item label="场景">{{ previewCaseDialog.item?.scenario || '—' }}</el-descriptions-item>
        <el-descriptions-item label="用例类型">{{ previewCaseDialog.item?.case_type || '—' }}</el-descriptions-item>
      </el-descriptions>
      <div class="preview-case-detail"><strong>前置条件</strong><p>{{ previewCaseDialog.item?.precondition || '无' }}</p></div>
      <div class="preview-case-detail"><strong>测试数据</strong><pre>{{ formatJson(previewCaseDialog.item?.test_data || {}) }}</pre></div>
      <div class="preview-case-detail"><strong>操作步骤</strong><ol><li v-for="(step, index) in caseSteps(previewCaseDialog.item)" :key="index">{{ step }}</li></ol></div>
      <div class="preview-case-detail"><strong>预期结果</strong><p>{{ previewCaseDialog.item?.expected_result || '无' }}</p></div>
    </template>
    <template #footer>
      <el-button @click="previewCaseDialog.visible = false">关闭</el-button>
      <el-button v-if="!previewCaseDialog.editing" type="primary" @click="openPreviewCase(previewCaseDialog.item, true)">编辑用例</el-button>
      <el-button v-else type="primary" @click="savePreviewCase">保存修改</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, inject, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  askWorkbenchTestCasePreflightStream,
  batchCreateWorkbenchTestCases,
  generateWorkbenchTestCases,
  getWorkbenchTestCaseAiModel,
} from '@/api/testWorkbench'
import RefinementStartConfirm from '@/views/test-workbench/components/RefinementStartConfirm.vue'
import RefinementMessageCard from '@/views/test-workbench/components/RefinementMessageCard.vue'
import AiConversationFrame from '@/views/test-workbench/components/AiConversationFrame.vue'
import AiStopStreamButton from '@/views/test-workbench/components/AiStopStreamButton.vue'
import TestCaseSourceSelector from '@/views/test-workbench/components/TestCaseSourceSelector.vue'
import { useRequirementRefinement } from '@/views/test-workbench/composables/useRequirementRefinement.js'

const props = defineProps({ modelValue: Boolean, projectId: { type: Number, required: true } })
const router = useRouter()
const emit = defineEmits(['update:modelValue', 'saved'])
const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const { scope } = inject('workbenchContext')

const activeStep = ref(0)
// 第三步内的子态：false = AI 对话，true = 预览并保存（对话生成用例后切换，保持在同一步）。
const previewMode = ref(false)
const sourceType = ref('merged_requirement')
const selectedSources = ref([])
const sourceSelectorRef = ref(null)
const sourceTypeOrder = ['merged_requirement', 'completed_requirement', 'requirement']
const sourceIds = computed(() => selectedSources.value.map(item => item.id))
const cases = ref([])
const sourceError = ref('')
const saving = ref(false)
const serverQualitySummary = ref(null)
const previewCaseDialog = ref({ visible: false, editing: false, item: null })
const previewCaseDraft = ref({})

// 用例生成的场景文案（复用 RequirementRefinementDrawer 的 test_case 分支）。
const workflow = {
  ruleTitle: '生成规则',
  ruleText: '首轮尽可能一次问全关键疑点；已明确内容直接用于生成，不会要求逐条确认测试点。',
  usageText: '进入 AI 对话后先确认必要信息；确认完成后再生成用例。',
  endActionLabel: '确认并开始生成测试用例',
  sessionHint: '本次生成对话仅用于生成测试用例，不会保存中间需求或测试点资产。',
  actionHint: '请在本轮集中确认关键疑点；跳过的内容不会被当作业务规则或确定预期。',
}

const sourceByRef = computed(() => new Map(selectedSources.value.map(item => [`${item.source_type}:${item.id}`, item])))
const selectedCount = computed(() => cases.value.filter(item => item.checked).length)
const allChecked = computed({
  get: () => cases.value.length > 0 && cases.value.every(item => item.checked),
  set: value => cases.value.forEach(item => { item.checked = value }),
})
const VALID_PRIORITIES = ['P0', 'P1', 'P2', 'P3']
const displayPriority = value => VALID_PRIORITIES.includes(value) ? value : '待补充'
const hasIncompletePriority = computed(() => cases.value.some(item => item.checked && !VALID_PRIORITIES.includes(item.priority)))
const qualitySummary = computed(() => {
  if (!cases.value.length) return null
  const countBy = key => cases.value.reduce((result, item) => {
    const value = key === 'priority' ? displayPriority(item[key]) : (item[key] || '待补充')
    result[value] = (result[value] || 0) + 1
    return result
  }, {})
  const toText = counts => Object.entries(counts).map(([key, value]) => `${key} ${value}`).join('，')
  const priorityCounts = countBy('priority')
  const typeCounts = countBy('case_type')
  const warnings = [...new Set(serverQualitySummary.value?.warnings || [])]
  if (priorityCounts['待补充']) warnings.push(`有 ${priorityCounts['待补充']} 条用例缺少优先级，请补充后保存`)
  if (Object.keys(priorityCounts).length === 1 && cases.value.length > 1) warnings.push('优先级完全一致，请核对是否遗漏核心用例')
  if (!priorityCounts.P1 && cases.value.some(item => /功能主流程|功能测试/.test(String(item.case_type || '')))) warnings.push('存在功能主流程但没有 P1，请核对优先级')
  return { case_type_text: toText(typeCounts), priority_text: toText(priorityCounts), warnings: [...new Set(warnings)] }
})

const caseSteps = item => (item?.steps || item?.steps_json || []).map(step => (
  typeof step === 'string' ? step : step.action || step.step || JSON.stringify(step)
))
const normalizeSteps = value => (Array.isArray(value) ? value : []).map(step => {
  if (typeof step === 'string') {
    const text = step.trim()
    return text ? { step: text } : null
  }
  if (step && typeof step === 'object') return step
  return null
}).filter(Boolean)
const formatJson = value => {
  try { return JSON.stringify(value || {}, null, 2) } catch { return String(value || '') }
}
const openPreviewCase = (item, editing = false) => {
  previewCaseDialog.value = { visible: true, editing, item }
  previewCaseDraft.value = {
    title: item?.title || '', scenario: item?.scenario || '', case_type: item?.case_type || '',
    precondition: item?.precondition || '', test_data_text: formatJson(item?.test_data || {}), steps_text: caseSteps(item).join('\n'),
    expected_result: item?.expected_result || '', priority: VALID_PRIORITIES.includes(item?.priority) ? item.priority : '',
  }
}
const openSourceRequirement = row => {
  const source = sourceByRef.value.get(row.source_ref) || {}
  const rowSourceType = row.source_type || source.source_type || 'requirement'
  const query = {
    system_id: source.system_id || row.system_id,
    version_id: source.version_id || row.version_id,
  }
  if (rowSourceType === 'completed_requirement') query.requirement_type = 'completed'
  router.push({
    name: rowSourceType === 'merged_requirement' ? 'TestWorkbenchMergedRequirements' : 'TestWorkbenchRequirements',
    params: { id: props.projectId },
    query,
  })
  visible.value = false
}
const savePreviewCase = () => {
  let testData
  try { testData = previewCaseDraft.value.test_data_text.trim() ? JSON.parse(previewCaseDraft.value.test_data_text) : {} } catch {
    ElMessage.error('测试数据必须是合法 JSON 对象')
    return
  }
  if (!testData || Array.isArray(testData) || typeof testData !== 'object') {
    ElMessage.error('测试数据必须是 JSON 对象')
    return
  }
  Object.assign(previewCaseDialog.value.item, {
    title: previewCaseDraft.value.title.trim(), scenario: previewCaseDraft.value.scenario.trim(),
    case_type: previewCaseDraft.value.case_type.trim(), precondition: previewCaseDraft.value.precondition.trim(), test_data: testData,
    steps: previewCaseDraft.value.steps_text.split('\n').map(step => step.trim()).filter(Boolean).map(step => ({ step })),
    expected_result: previewCaseDraft.value.expected_result.trim(), priority: previewCaseDraft.value.priority,
  })
  previewCaseDialog.value.visible = false
}

const scopeIds = value => String(value || '').split(',').map(Number).filter(Boolean)
// 生成来源受当前项目筛选范围约束，允许在已选系统、版本中跨范围批量选择。
const sourceScope = () => ({
  project_id: props.projectId,
  system_ids: scopeIds(scope.value.system_ids),
  version_ids: scopeIds(scope.value.version_ids),
  source_type: sourceType.value,
  source_ids: sourceIds.value,
})
const preflightScope = () => ({
  ...sourceScope(),
  source_snapshots: selectedSources.value.map(source => {
    return {
      title: source.title || source.source_title || '',
      req_no: source.req_no || '',
      content: source.markdown_content || source.original_content || '',
    }
  }),
})
// 对接测试用例生成对话 AI 接口的适配器（保留内部接口兼容），交给通用对话状态机复用。
const preflightApi = {
  conversationKind: 'test_case',
  feature: 'test_workbench_test_case_generate',
  getModel: getWorkbenchTestCaseAiModel,
  askStream: (_id, data, onEvent, signal) => askWorkbenchTestCasePreflightStream(data, onEvent, signal),
  getOriginal: () => '',
  getStartContent: () => '',
  generateTestCases: (_id, payload) => generateWorkbenchTestCases({
    ...sourceScope(),
    history: payload.history || [],
    supplements: payload.supplements || [],
    selected_model_id: payload.selected_model_id,
    call_group_id: payload.call_group_id,
  }),
}

const {
  streaming,
  composing,
  conversationStarted,
  modelInfo,
  modelCandidates,
  selectedModelId,
  modelLoadError,
  messages,
  scrollRef,
  statusType,
  statusLabel,
  canStart,
  canEnd,
  canSend,
  retrySelectionRequired,
  retryModelLoading,
  stickBottom,
  stickTop,
  composeMsgId,
  endActionMsgId,
  activeQuestionMsgId,
  answerDraft,
  onAnswerChange,
  selectModel,
  scrollToTopManually,
  scrollToBottomManually,
  onScroll,
  copyText,
  messageCopyable,
  start,
  send,
  sendSupplement,
  retry,
  refreshRetryCandidates,
  stopStream,
  endConversation,
  handleBeforeClose,
  open,
} = useRequirementRefinement({
  getRequirement: () => ({ id: props.projectId, original_content: '' }),
  close: () => { visible.value = false },
  emit: () => {}, // test_case 场景下的用例查看走 @case-preview 直连 openGeneratedCases，无需 composable 转发
  api: preflightApi,
  getScope: () => preflightScope(),
})

// 「进入 AI 对话」：只在此时发起首次模型调用（确认模型这一步不调用）。
const enterConversation = () => {
  if (!canStart.value) return
  previewMode.value = false
  activeStep.value = 2
  if (!conversationStarted.value) start()
}
// 对话步「上一步」：已发起过调用需二次确认，随后清空对话并回到确认模型步。
const backFromConversation = async () => {
  if (conversationStarted.value) {
    try {
      await ElMessageBox.confirm('返回将清空当前 AI 对话，是否继续？', '返回上一步', { type: 'warning', confirmButtonText: '返回', cancelButtonText: '取消' })
    } catch { return }
  }
  stopStream()
  await open() // 重置对话状态并重新加载模型信息，供确认模型步展示
  activeStep.value = 1
}

// 对话内点击气泡「查看并保存测试用例」：把生成结果落到预览子态（仍在第三步）。
const openGeneratedCases = result => {
  serverQualitySummary.value = result?.quality_summary || null
  const sources = new Map((result?.sources || []).map(item => [item.source_ref, item]))
  cases.value = (result?.test_cases || []).map((item, index) => {
    const source = sources.get(item.source_ref) || sourceByRef.value.get(item.source_ref)
    return {
      ...item,
      priority: VALID_PRIORITIES.includes(item.priority) ? item.priority : '',
      source_title: source?.title || '未识别来源',
      checked: true,
      _key: `${item.source_ref || 'unknown'}-${index}-${item.case_no || item.title || ''}`,
    }
  })
  if (!cases.value.length) {
    ElMessage.warning('AI 未生成有效用例，请调整需求内容后重试')
    return
  }
  previewMode.value = true
}

const save = async () => {
  const chosen = cases.value.filter(item => item.checked)
  if (!chosen.length) return
  if (chosen.some(item => !VALID_PRIORITIES.includes(item.priority))) {
    ElMessage.warning('请先补充所选用例的优先级')
    return
  }
  saving.value = true
  try {
    await batchCreateWorkbenchTestCases({ cases: chosen.map(item => {
      const source = sourceByRef.value.get(item.source_ref) || {}
      return {
        project_id: props.projectId, system_id: source?.system_id, version_id: source?.version_id,
        requirement_id: item.requirement_id || null, completed_requirement_id: item.completed_requirement_id || null,
        merged_requirement_id: item.merged_requirement_id || null,
        case_no: item.case_no || null, title: item.title, scenario: item.scenario || null,
        case_type: item.case_type || null, precondition: item.precondition || null,
        test_data: item.test_data || {}, steps_json: normalizeSteps(item.steps || item.steps_json),
        expected_result: item.expected_result || null, priority: item.priority,
        source_type: 'ai_generated', source_ref: item.source_ref,
        tags: item.tags || [], business_flow_refs: item.business_flow_refs || [],
        function_point_refs: item.function_point_refs || [], requirement_structure_refs: item.requirement_structure_refs || [],
      }
    }) })
    visible.value = false
    emit('saved')
  } finally {
    saving.value = false
  }
}

// 关闭前确认：已进入对话且发起过调用时，复用状态机的关闭确认（提示对话不保留）。
const onBeforeClose = done => {
  if (activeStep.value === 2 && !previewMode.value && conversationStarted.value) {
    handleBeforeClose(done)
    return
  }
  done()
}

const reset = () => {
  activeStep.value = 0
  previewMode.value = false
  sourceType.value = sourceTypeOrder[0]
  selectedSources.value = []
  cases.value = []
  serverQualitySummary.value = null
  sourceError.value = ''
  previewCaseDialog.value = { visible: false, editing: false, item: null }
}

const loadPreferredSources = async () => {
  for (const type of sourceTypeOrder) {
    sourceType.value = type
    await nextTick()
    const result = await sourceSelectorRef.value?.load()
    if (result?.total) return
  }
}

watch(visible, async isVisible => {
  if (!isVisible) return
  reset()
  await nextTick()
  await loadPreferredSources()
  await open()
})
</script>

<style scoped>
.generate-steps { margin-bottom: 20px; }
.step-panel { min-height: 460px; }
.step-heading { display: flex; justify-content: space-between; gap: 20px; align-items: flex-start; margin-bottom: 18px; }
.step-heading h4 { margin: 0 0 6px; color: var(--el-text-color-primary); font-size: 15px; }
.step-heading p { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; line-height: 20px; }

/* 步骤一：整体居中 */
.select-panel { display: flex; flex-direction: column; }
.select-body { display: flex; flex-direction: column; align-items: stretch; gap: 20px; width: 100%; margin: 24px 0 0; }
.source-type-picker,
.source-select { display: flex; flex-direction: column; align-items: center; gap: 10px; width: 100%; }
.source-select { max-width: 480px; }
.picker-label { color: var(--el-text-color-primary); font-size: 14px; font-weight: 600; }
.select-hint { margin: 4px 0 0; color: var(--el-text-color-secondary); font-size: 12px; line-height: 20px; text-align: center; }
.inline-alert { margin-bottom: 16px; }

/* 步骤二：确认模型（复用组件，组件内部已居中） */
.confirm-panel { display: flex; }

/* 步骤三：内嵌 AI 对话 */
.conversation-step { display: flex; flex-direction: column; height: 560px; gap: 14px; }
.ai-status { display: flex; align-items: center; gap: 10px; min-height: 30px; color: var(--el-text-color-secondary); font-size: 13px; }
.ai-status-tag { max-width: 60%; }
.ai-status-tag :deep(.el-tag__content) { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ai-status-hint { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversation-wrap { position: relative; flex: 1; min-height: 0; display: flex; }
.conversation-body { flex: 1; min-height: 0; padding-right: 6px; }
.stream-action-bar { display: flex; flex-shrink: 0; width: 42px; min-height: 50px; margin-left: auto; padding: 6px 0; justify-content: center; }
.ai-quota-tip { flex-shrink: 0; margin: 0; padding-top: 10px; border-top: 1px solid var(--el-border-color-lighter); color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.6; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; animation: pulse 1s ease-in-out infinite; }
.scroll-nav-actions { position: absolute; right: 0; bottom: 14px; z-index: 5; display: flex; align-items: center; width: 42px; flex-direction: column; gap: 8px; }
.scroll-nav-btn { width: 34px; height: 34px; margin-left: 0; padding: 0; font-size: 16px; color: var(--el-color-primary); background: var(--el-bg-color); border-color: var(--el-color-primary-light-7); box-shadow: 0 2px 10px var(--el-color-primary-light-8); }
@keyframes pulse { 50% { opacity: 0.3; transform: scale(0.75); } }

/* 步骤三：预览子态 */
.quality-summary { display: flex; flex-wrap: wrap; gap: 8px 14px; margin: 10px 0; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.6; }
.quality-summary__warning { color: var(--el-color-warning); }
.preview-table :deep(.el-table__header .cell), .preview-table :deep(.el-table__body .cell) { white-space: nowrap; }
.preview-table :deep(.el-table__body .cell) { overflow: hidden; text-overflow: ellipsis; }
.preview-panel :deep(.el-table) { border-radius: 6px; overflow: hidden; }
.preview-table-link { display: inline-block; max-width: 100%; overflow: hidden; padding: 0; text-overflow: ellipsis; vertical-align: baseline; white-space: nowrap; }
.preview-case-form { padding-right: 18px; }
.preview-case-detail { margin-top: 16px; }
.preview-case-detail strong { color: var(--el-text-color-primary); }
.preview-case-detail p { margin: 6px 0 0; white-space: pre-wrap; line-height: 1.7; }
.preview-case-detail pre { margin: 6px 0 0; padding: 10px; background: var(--el-fill-color-light); border-radius: 4px; white-space: pre-wrap; word-break: break-word; }
.preview-case-detail ol { margin: 6px 0 0; padding-left: 22px; line-height: 1.8; }
</style>
