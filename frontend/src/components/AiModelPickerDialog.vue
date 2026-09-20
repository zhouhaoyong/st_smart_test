<template>
  <el-dialog
    :model-value="modelValue"
    title="选择模型"
    width="min(720px, calc(100vw - 48px))"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
    @open="refreshModels"
  >
    <p class="picker-dialog-hint">本次仅用于{{ featureLabel }}，不会修改已保存的模型配置。</p>
    <p v-if="effectiveLoading" class="picker-dialog-loading">正在获取最新可用模型…</p>

    <AiModelSelectionPanel
      v-if="currentCandidates.length"
      :model-info="currentModelInfo"
      :model-candidates="currentCandidates"
      :selected-model-id="draftModelId"
      summary-label="当前模型"
      selection-label="选择模型"
      hint="请选择一个连通已验证且额度可用的模型。"
      require-explicit-selection
      :disable-single="false"
      @update:selectedModelId="draftModelId = $event"
    />
    <el-alert
      v-else-if="!effectiveLoading"
      type="warning"
      :closable="false"
      show-icon
      :title="refreshError || '暂无可用模型，请先在 AI 模型配置中启用模型并配置可用额度。'"
    />

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button
        type="primary"
        :loading="effectiveLoading"
        :disabled="!draftModelId || effectiveLoading"
        @click="confirm"
      >确认选择</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import AiModelSelectionPanel from '@/views/test-workbench/components/AiModelSelectionPanel.vue'
import { getAiModelsForFeature } from '@/api/ai'
import { pickPreferredAiModelId, rememberAiModel } from '@/utils/aiModelPreference'

const props = defineProps({
  modelValue: Boolean,
  featureLabel: { type: String, default: '本次 AI 操作' },
  feature: { type: String, default: '' },
  modelInfo: { type: Object, default: null },
  modelCandidates: { type: Array, default: () => [] },
  selectedModelId: { type: [Number, String], default: null },
  loading: Boolean,
})
const emit = defineEmits(['update:modelValue', 'confirm', 'models-refreshed'])
const draftModelId = ref(null)
const requestLoading = ref(false)
const refreshedCandidates = ref(null)
const refreshError = ref('')
let refreshSequence = 0

const effectiveLoading = computed(() => props.loading || requestLoading.value)

const currentCandidates = computed(() => (
  Array.isArray(refreshedCandidates.value) ? refreshedCandidates.value : props.modelCandidates
))
const currentModelInfo = computed(() => (
  currentCandidates.value.find(item => Number(item.id) === Number(draftModelId.value)) || props.modelInfo
))

function syncDraft() {
  draftModelId.value = pickPreferredAiModelId(currentCandidates.value, props.selectedModelId)
}

async function refreshModels() {
  const sequence = ++refreshSequence
  refreshedCandidates.value = []
  draftModelId.value = null
  refreshError.value = ''
  if (!props.feature) {
    syncDraft()
    return
  }
  requestLoading.value = true
  try {
    const result = await getAiModelsForFeature(props.feature, {
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
    refreshError.value = '获取最新可用模型失败，请稍后重试。'
    emit('models-refreshed', [])
  } finally {
    if (sequence === refreshSequence) requestLoading.value = false
  }
}

watch(() => props.modelValue, open => {
  if (!open) {
    refreshSequence += 1
    refreshedCandidates.value = null
    requestLoading.value = false
  }
})
watch(() => props.modelCandidates, () => {
  if (props.modelValue && refreshedCandidates.value === null) syncDraft()
}, { deep: true })

function confirm() {
  if (!draftModelId.value || props.loading || requestLoading.value) return
  rememberAiModel(draftModelId.value)
  emit('confirm', draftModelId.value)
  emit('update:modelValue', false)
}
</script>

<style scoped>
.picker-dialog-hint {
  margin: 0 0 14px;
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.7;
}
.picker-dialog-loading {
  margin: 0 0 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
