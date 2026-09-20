<template>
  <div class="model-selection-panel">
    <div v-if="displayModelInfo" class="model-summary">
      <div class="model-summary-main">
        <span class="model-summary-label">{{ summaryLabel }}</span>
        <strong
          class="model-summary-alias"
          :title="displayModelInfo.name || '未命名模型'"
        >{{ displayModelInfo.name || '未命名模型' }}</strong>
        <small
          class="model-summary-name"
          :title="displayModelInfo.model || '未填写模型名称'"
        >{{ displayModelInfo.model || '未填写模型名称' }}</small>
        <el-tag class="model-summary-scope" :type="modelScopeTagType(displayModelInfo)" size="small">
          {{ modelScopeText(displayModelInfo) }}
        </el-tag>
      </div>
      <div class="model-summary-capabilities">
        <el-tag
          class="model-summary-connectivity"
          :type="displayModelInfo.connectivity_status === 'passed' ? 'success' : 'warning'"
          size="small"
        >
          {{ connectivityText(displayModelInfo) }}
        </el-tag>
        <el-tag
          class="model-summary-reasoning"
          :type="displayModelInfo.reasoning_status === 'supported' ? 'success' : 'info'"
          size="small"
        >
          {{ reasoningText(displayModelInfo) }}
        </el-tag>
      </div>
    </div>

    <div v-if="modelCandidates.length" class="model-selector">
      <span>{{ selectionLabel }}</span>
      <el-select
        :model-value="displaySelectedModelId"
        :disabled="disableSingle && modelCandidates.length <= 1"
        placeholder="请选择模型"
        @update:model-value="onModelChange"
      >
        <el-option
          v-for="item in modelCandidates"
          :key="item.id"
          :label="modelOptionLabel(item)"
          :value="item.id"
        >
          <div class="model-option">
            <div class="model-option-main">
              <span class="model-option-scope">{{ modelScopeText(item) }}</span>
              <strong>{{ item.name || '未命名模型' }}</strong>
              <small>{{ item.model || '未填写模型名称' }}</small>
            </div>
            <span class="model-option-quota">{{ modelOptionQuotaLabel(item) }}</span>
          </div>
        </el-option>
      </el-select>
      <small>{{ hint }}</small>
    </div>

    <p v-else class="model-empty">暂无可用模型，请先配置并启用额度可用的模型。</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { findAiModel, rememberAiModel } from '@/utils/aiModelPreference'

const props = defineProps({
  modelInfo: { type: Object, default: null },
  modelCandidates: { type: Array, default: () => [] },
  selectedModelId: { type: [Number, String], default: null },
  summaryLabel: { type: String, default: '本次模型' },
  selectionLabel: { type: String, default: '本次使用模型' },
  hint: { type: String, default: '仅本次使用，不会修改已保存的模型配置。' },
  requireExplicitSelection: Boolean,
  disableSingle: { type: Boolean, default: true },
})
const emit = defineEmits(['update:selectedModelId'])

function onModelChange(modelId) {
  rememberAiModel(modelId)
  emit('update:selectedModelId', modelId)
}

const displaySelectedModelId = computed(() => (
  props.requireExplicitSelection
    ? props.selectedModelId
    : (props.selectedModelId || props.modelInfo?.id)
))
const displayModelInfo = computed(() => (
  findAiModel(props.modelCandidates, displaySelectedModelId.value) || props.modelInfo
))

const modelScopeText = item => item?.scope === 'platform' ? '平台模型' : '我的模型'
const modelScopeTagType = item => item?.scope === 'platform' ? 'success' : 'primary'
const connectivityText = item => item?.connectivity_status === 'passed' ? '连通已验证' : '未验证连通性'
const reasoningText = item => ({
  supported: '有思考模式',
  unsupported: '无思考模式',
  unknown: '未检测思考模式',
}[item?.reasoning_status] || '未检测思考模式')
const modelOptionQuotaLabel = item => {
  const quotaLimit = Number(item?.quota_limit)
  if (quotaLimit < 0) return '额度不限'
  if (!Number.isFinite(quotaLimit) || quotaLimit <= 0) return '额度未配置'
  const quotaRemaining = Math.max(
    0,
    Number(item?.quota_remaining ?? quotaLimit - Number(item?.quota_used || 0)),
  )
  return `今日剩余 ${quotaRemaining} / ${quotaLimit} 次`
}
const modelOptionLabel = item => (
  `${modelScopeText(item)}｜${item?.name || '未命名模型'}｜${modelOptionQuotaLabel(item)}`
)
</script>

<style scoped>
.model-selection-panel {
  display: flex;
  width: 100%;
  padding: 14px 16px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
  box-sizing: border-box;
  flex-direction: column;
  text-align: left;
}
.model-summary {
  order: 2;
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 8px;
  width: 100%;
  overflow: hidden;
  flex-wrap: nowrap;
  padding: 10px 0 0;
  border: 0;
  border-top: 1px solid var(--el-border-color-light);
  background: transparent;
  text-align: left;
  box-sizing: border-box;
}
.model-summary-main,
.model-summary-capabilities {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 8px;
  width: 100%;
  overflow: hidden;
  flex-wrap: nowrap;
}
.model-summary-label {
  flex: 0 0 56px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  white-space: nowrap;
}
.model-summary :deep(.el-tag) {
  flex: 0 0 auto;
  white-space: nowrap;
}
.model-summary-alias,
.model-summary-name {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-summary-alias {
  flex: 0 0 140px;
  width: 140px;
  color: var(--el-text-color-primary);
}
.model-summary-name {
  flex: 0 0 160px;
  width: 160px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.model-summary-scope { flex: 0 0 auto; }
.model-summary-capabilities { padding-left: 64px; box-sizing: border-box; }
.model-summary-connectivity,
.model-summary-reasoning { flex: 0 0 auto; }
.model-selector {
  order: 1;
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  align-items: center;
  gap: 8px 12px;
  width: 100%;
  margin-top: 0;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  text-align: left;
  box-sizing: border-box;
}
.model-selector > span { color: var(--el-text-color-regular); font-size: 13px; }
.model-selector > :deep(.el-select) { width: 100%; }
.model-selector small { grid-column: 2; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.model-option { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 12px; width: 100%; white-space: nowrap; }
.model-option-main { display: flex; flex: 1 1 auto; min-width: 0; align-items: baseline; gap: 8px; overflow: hidden; }
.model-option-scope { flex: none; color: var(--el-color-primary); font-size: 12px; }
.model-option-main strong,
.model-option-main small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.model-option-main strong { flex: 1 1 auto; min-width: 0; color: var(--el-text-color-primary); }
.model-option-main small { flex: 1 1 auto; min-width: 0; color: var(--el-text-color-secondary); }
.model-option-quota { flex: 0 1 40%; min-width: 0; overflow: hidden; color: var(--el-text-color-secondary); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.model-empty { order: 1; margin: 0; color: var(--el-text-color-secondary); font-size: 13px; }
@media (max-width: 720px) {
  .model-summary-alias { flex-basis: 120px; width: 120px; }
  .model-summary-name { flex-basis: 120px; width: 120px; }
  .model-summary-capabilities { padding-left: 0; }
  .model-option { gap: 8px; }
}
</style>
