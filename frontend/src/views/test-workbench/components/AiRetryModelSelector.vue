<template>
  <div class="retry-model-selector">
    <p v-if="required" class="retry-required-hint">请先选择模型重试，重试成功后才能继续当前对话。</p>
    <div v-if="candidates.length" class="retry-model-row">
      <el-select v-model="selectedId" placeholder="选择重试模型" class="retry-model-select">
        <el-option
          v-for="item in candidates"
          :key="item.id"
          :label="optionLabel(item)"
          :value="item.id"
        >
          <div class="retry-model-option">
            <el-tag :type="scopeTagType(item)" size="small">{{ scopeText(item) }}</el-tag>
            <span>{{ item.name || '未命名模型' }}</span>
            <small>{{ item.model }}</small>
            <em>{{ quotaLabel(item) }}</em>
          </div>
        </el-option>
      </el-select>
      <el-button type="primary" plain size="small" :disabled="!selectedId" @click="confirm">
        选择模型重试
      </el-button>
    </div>
    <span v-else class="retry-empty-hint">暂无其他可用模型，请检查模型启用状态和额度配置。</span>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  candidates: { type: Array, default: () => [] },
  required: Boolean,
})
const emit = defineEmits(['retry'])
const selectedId = ref(null)

watch(() => props.candidates, candidates => {
  if (!candidates.some(item => Number(item.id) === Number(selectedId.value))) selectedId.value = null
}, { immediate: true })

const scopeText = item => item?.scope === 'platform' ? '平台模型' : '我的模型'
const scopeTagType = item => item?.scope === 'platform' ? 'success' : 'primary'
const quotaLabel = item => {
  const limit = Number(item?.quota_limit)
  const used = Number(item?.quota_used || 0)
  const remaining = item?.quota_remaining == null ? null : Number(item.quota_remaining)
  if (limit < 0) return '额度不限'
  if (!Number.isFinite(limit) || limit <= 0 || remaining == null) return '额度未配置'
  return `今日 ${used}/${limit}，剩余 ${Math.max(0, remaining)}`
}
const optionLabel = item => `${scopeText(item)}｜${item?.name || '未命名模型'}｜${quotaLabel(item)}`
const confirm = () => {
  if (selectedId.value) emit('retry', selectedId.value)
}
</script>

<style scoped>
.retry-model-selector { width: 100%; }
.retry-required-hint { margin: 0 0 8px; color: var(--el-color-warning); font-size: 13px; }
.retry-model-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.retry-model-select { min-width: 300px; max-width: 520px; }
.retry-model-option { display: flex; align-items: center; gap: 8px; min-width: 0; }
.retry-model-option span,
.retry-model-option small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.retry-model-option small { color: var(--el-text-color-secondary); }
.retry-model-option em { margin-left: auto; color: var(--el-text-color-secondary); font-size: 12px; font-style: normal; white-space: nowrap; }
.retry-empty-hint { color: var(--el-text-color-secondary); font-size: 13px; }
</style>
