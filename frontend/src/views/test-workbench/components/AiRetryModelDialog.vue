<template>
  <el-dialog
    v-model="visible"
    title="选择模型重试"
    width="min(720px, calc(100vw - 48px))"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    @open="emit('open')"
  >
    <p class="retry-dialog-hint">打开窗口时会重新获取最新可用模型并刷新各模型的实时额度。优先沿用最近一次选择且当前可用的模型，否则默认选中第一个可用模型。请切换后点“确认重试”，不会自动切换或自动重试。</p>
    <p v-if="loading" class="retry-dialog-loading">正在获取最新可用模型…</p>
    <AiModelSelectionPanel
      v-if="modelCandidates.length"
      :model-info="modelInfo"
      :model-candidates="modelCandidates"
      :selected-model-id="selectedModelId"
      selection-label="本次重试模型"
      summary-label="失败模型"
      hint="优先沿用最近一次选择且当前可用的模型，可切换后确认重试，不会自动切换模型。"
      require-explicit-selection
      :disable-single="false"
      @update:selected-model-id="selectedModelId = $event"
    />
    <el-alert
      v-if="!modelCandidates.length && !loading"
      class="retry-dialog-empty"
      type="warning"
      :closable="false"
      show-icon
      title="当前没有可用的模型。若已提升平台模型额度或新增了模型，可点“刷新可用模型”重新获取；仍为空请先在模型配置中启用模型并配置可用额度。"
    />
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button :loading="loading" @click="emit('refresh')">刷新可用模型</el-button>
      <el-button type="primary" :loading="loading" :disabled="!selectedModelId || loading" @click="confirm">
        确认重试
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import AiModelSelectionPanel from './AiModelSelectionPanel.vue'
import { pickPreferredAiModelId } from '@/utils/aiModelPreference'

const props = defineProps({
  modelValue: Boolean,
  modelInfo: { type: Object, default: null },
  modelCandidates: { type: Array, default: () => [] },
  loading: Boolean,
})
const emit = defineEmits(['update:modelValue', 'open', 'refresh', 'confirm'])
const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})
const selectedModelId = ref(null)

// 有可用模型时优先恢复最近一次选择；当前模型不可用时回落到第一个，
// 用户仍需手动点“确认重试”，不做自动切换/自动重试。
const pickDefaultModel = candidates => {
  const list = Array.isArray(candidates) ? candidates : []
  selectedModelId.value = pickPreferredAiModelId(list, selectedModelId.value)
}

watch(() => props.modelValue, value => {
  if (value) pickDefaultModel(props.modelCandidates)
})
watch(() => props.modelCandidates, pickDefaultModel, { deep: true })

const confirm = () => {
  if (!selectedModelId.value) return
  emit('confirm', selectedModelId.value)
}
</script>

<style scoped>
.retry-dialog-hint {
  margin: 0 0 14px;
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.7;
}
.retry-dialog-loading {
  margin: 0 0 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.retry-dialog-empty { margin-top: 12px; }
</style>
