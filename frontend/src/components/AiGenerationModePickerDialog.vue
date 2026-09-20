<template>
  <el-dialog
    v-if="!embedded"
    :model-value="modelValue"
    :title="dialogTitle"
    width="min(760px, calc(100vw - 48px))"
    align-center
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
    @open="refreshModels"
  >
    <AiGenerationModePickerPanel
      :mode-options="modeOptions"
      :draft-mode="draftMode"
      :need-model="needModel"
      :model-title-text="modelTitleText"
      :model-sub-text="modelSubText"
      :target-text="targetText"
      :cost-text-of="costTextOf"
      :interfaces="interfaces"
      :can-start="canStart"
      @update:draft-mode="draftMode = $event"
      @pick-model="modelPickerVisible = true"
      @confirm="confirm"
    />
    <template #footer>
      <div class="gen-settings-footer">
        <el-button @click="cancel">取消</el-button>
        <el-button type="primary" class="ai-generate-button" :disabled="loading || !canStart" @click="confirm">
          开始生成（{{ interfaces.length }}）
        </el-button>
      </div>
    </template>
  </el-dialog>

  <div v-else class="gen-settings-embedded">
    <AiGenerationModePickerPanel
      :mode-options="modeOptions"
      :draft-mode="draftMode"
      :need-model="needModel"
      :model-title-text="modelTitleText"
      :model-sub-text="modelSubText"
      :target-text="targetText"
      :cost-text-of="costTextOf"
      :interfaces="interfaces"
      :can-start="canStart"
      show-footer
      :show-previous="showPrevious"
      @update:draft-mode="draftMode = $event"
      @pick-model="modelPickerVisible = true"
      @confirm="confirm"
      @cancel="cancel"
      @back="emit('back')"
    />
  </div>

  <AiModelPickerDialog
    v-model="modelPickerVisible"
    feature-label="用例生成"
    :feature="modelFeature"
    :model-info="draftModelInfo"
    :model-candidates="modelCandidates"
    :selected-model-id="draftModelId"
    @confirm="draftModelId = $event"
    @models-refreshed="onModelsRefreshed"
  />
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import AiGenerationModePickerPanel from '@/components/AiGenerationModePickerPanel.vue'
import AiModelPickerDialog from '@/components/AiModelPickerDialog.vue'
import { getAiModelsForFeature } from '@/api/ai'
import { estimateGeneration } from '@/utils/aiImportGeneration'
import { pickPreferredAiModelId } from '@/utils/aiModelPreference'

const props = defineProps({
  modelValue: Boolean,
  embedded: { type: Boolean, default: false },
  showPrevious: { type: Boolean, default: false },
  title: { type: String, default: '' },
  modelFeature: { type: String, default: '' },
  modeOptions: { type: Array, default: () => [] },
  selectedMode: { type: String, default: 'normal' },
  interfaces: { type: Array, default: () => [] },
  modelCandidates: { type: Array, default: () => [] },
  selectedModelId: { type: [Number, String], default: null },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'confirm', 'cancel', 'models-refreshed', 'back'])

const draftMode = ref(props.selectedMode)
const draftModelId = ref(props.selectedModelId)
const modelPickerVisible = ref(false)
const refreshedCandidates = ref(null)
let refreshSequence = 0

const currentCandidates = computed(() => (
  Array.isArray(refreshedCandidates.value) ? refreshedCandidates.value : props.modelCandidates
))

function onModelsRefreshed(candidates) {
  refreshedCandidates.value = Array.isArray(candidates) ? candidates : []
  emit('models-refreshed', refreshedCandidates.value)
  syncDraft()
}

const needModel = computed(() => draftMode.value !== 'main')
const draftModelInfo = computed(() =>
  currentCandidates.value.find(item => Number(item.id) === Number(draftModelId.value)) || null,
)
const modelTitleText = computed(() => {
  if (!needModel.value) return '本模式无需模型'
  return draftModelInfo.value?.name || '未选择模型'
})
const modelSubText = computed(() => {
  if (!needModel.value) return '主流程用例由系统按接口定义生成，全程不调用模型'
  if (!draftModelInfo.value) return '点击右侧按钮选择本次用例生成模型'
  const name = draftModelInfo.value.name || ''
  const model = draftModelInfo.value.model || ''
  return model && model !== name ? model : ''
})
const isSingle = computed(() => props.interfaces.length === 1)
const dialogTitle = computed(() => props.title || (isSingle.value ? '重新生成用例' : '生成设置'))
const targetText = computed(() => (
  isSingle.value
    ? `接口「${props.interfaces[0]?.name || props.interfaces[0]?.url || '未命名接口'}」`
    : `${props.interfaces.length} 个接口`
))
const canStart = computed(() =>
  props.interfaces.length > 0 && (!needModel.value || !!draftModelId.value),
)

function costTextOf(mode) {
  const { cases, aiCalls } = estimateGeneration(props.interfaces, mode)
  return aiCalls
    ? `预计约 ${cases} 个用例 · 消耗 ${aiCalls} 次 AI 配额次数`
    : `预计 ${cases} 个用例 · 不消耗 AI 配额次数`
}

function syncDraft() {
  draftMode.value = props.modeOptions.some(item => item.value === props.selectedMode)
    ? props.selectedMode
    : (props.modeOptions[0]?.value || 'normal')
  draftModelId.value = pickPreferredAiModelId(currentCandidates.value, props.selectedModelId)
}

async function refreshModels() {
  const sequence = ++refreshSequence
  refreshedCandidates.value = []
  draftModelId.value = null
  if (!props.modelFeature) {
    syncDraft()
    return
  }
  try {
    const result = await getAiModelsForFeature(props.modelFeature, {
      skipErrorToast: true,
      skipSuccessToast: true,
    })
    if (sequence !== refreshSequence || !props.modelValue) return
    refreshedCandidates.value = Array.isArray(result?.candidates) ? result.candidates : []
    emit('models-refreshed', refreshedCandidates.value)
    syncDraft()
  } catch {
    if (sequence !== refreshSequence || !props.modelValue) return
    refreshedCandidates.value = []
    emit('models-refreshed', [])
  }
}

watch(() => [props.modelValue, props.loading], ([open, loading]) => {
  if (open && !loading && refreshedCandidates.value === null) syncDraft()
  if (!open) {
    refreshSequence += 1
    refreshedCandidates.value = null
  }
})

function cancel() {
  emit('cancel')
  if (!props.embedded) emit('update:modelValue', false)
}

function confirm() {
  if (!canStart.value) return
  emit('confirm', { mode: draftMode.value, modelId: needModel.value ? draftModelId.value : null })
  if (!props.embedded) emit('update:modelValue', false)
}
</script>

<style scoped>
.gen-settings-footer { display: flex; justify-content: flex-end; gap: 8px; }
:global(.el-dialog.ai-generation-settings-dialog) { border-radius: 16px; overflow: hidden; }
</style>
