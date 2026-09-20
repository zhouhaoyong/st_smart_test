<template>
  <el-dialog
    v-model="visible"
    title="修改接口状态"
    width="min(460px, calc(100vw - 48px))"
    align-center
    append-to-body
    destroy-on-close
    class="workflow-status-dialog-wrapper"
  >
    <div class="workflow-status-dialog">
      <div class="workflow-status-current">
        <span class="workflow-status-label">当前状态</span>
        <el-tag :type="statusType(status)" effect="light">{{ statusLabel(status) }}</el-tag>
      </div>
      <div class="workflow-status-options" role="radiogroup" aria-label="接口状态">
        <label
          class="workflow-status-option workflow-status-option--pending"
          :class="{ 'is-selected': draftStatus === 'pending', 'is-disabled': saving }"
        >
          <input
            v-model="draftStatus"
            class="workflow-status-option__input"
            type="radio"
            value="pending"
            :disabled="saving"
          />
          <span class="workflow-status-option__body">
            <span class="workflow-status-option__icon" aria-hidden="true">
              <el-icon><Clock /></el-icon>
            </span>
            <span class="workflow-status-option__copy">
              <span class="workflow-status-option__title">待处理</span>
            </span>
          </span>
        </label>
        <label
          class="workflow-status-option workflow-status-option--done"
          :class="{ 'is-selected': draftStatus === 'done', 'is-disabled': saving }"
        >
          <input
            v-model="draftStatus"
            class="workflow-status-option__input"
            type="radio"
            value="done"
            :disabled="saving"
          />
          <span class="workflow-status-option__body">
            <span class="workflow-status-option__icon" aria-hidden="true">
              <el-icon><CircleCheckFilled /></el-icon>
            </span>
            <span class="workflow-status-option__copy">
              <span class="workflow-status-option__title">已处理</span>
            </span>
          </span>
        </label>
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="!canSave" @click="handleSave">
        {{ draftStatus === 'done' ? '保存并确认' : '保存' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { CircleCheckFilled, Clock } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  status: { type: String, default: 'pending' },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'save'])
const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})
const draftStatus = ref('pending')

const normalizeStatus = value => (value === 'done' ? 'done' : 'pending')
const statusLabel = value => (normalizeStatus(value) === 'done' ? '已处理' : '待处理')
const statusType = value => (normalizeStatus(value) === 'done' ? 'success' : 'warning')

watch(() => [props.modelValue, props.status], ([opened, status]) => {
  if (opened) {
    const normalizedStatus = normalizeStatus(status)
    draftStatus.value = normalizedStatus === 'pending' ? 'done' : 'pending'
  }
})

const canSave = computed(() => !props.saving && draftStatus.value !== normalizeStatus(props.status))

const handleSave = () => {
  if (!canSave.value) return
  emit('save', draftStatus.value)
}
</script>

<style scoped>
.workflow-status-dialog {
  display: flex;
  align-items: center;
  flex-direction: column;
  gap: 12px;
  padding: 0;
  color: var(--el-text-color-regular);
}
.workflow-status-current {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.workflow-status-label { color: var(--el-text-color-secondary); }
.workflow-status-current :deep(.el-tag) { min-width: 56px; justify-content: center; }
.workflow-status-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  width: min(420px, 100%);
}
.workflow-status-option {
  position: relative;
  display: block;
  margin: 0;
  padding: 0;
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  background: #fff;
  color: var(--el-text-color-regular);
  cursor: pointer;
  transition: border-color 0.2s, background-color 0.2s, box-shadow 0.2s;
}
.workflow-status-option:hover {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-fill-color-light);
}
.workflow-status-option.is-selected {
  box-shadow: 0 0 0 1px currentColor inset;
}
.workflow-status-option--pending.is-selected {
  border-color: var(--el-color-warning);
  background: var(--el-color-warning-light-9);
  color: var(--el-color-warning-dark-2);
}
.workflow-status-option--done.is-selected {
  border-color: var(--el-color-success);
  background: var(--el-color-success-light-9);
  color: var(--el-color-success-dark-2);
}
.workflow-status-option__input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
.workflow-status-option__body {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 56px;
  padding: 8px 10px;
  box-sizing: border-box;
}
.workflow-status-option__icon {
  display: inline-flex;
  flex: 0 0 26px;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
  font-size: 16px;
}
.workflow-status-option--pending.is-selected .workflow-status-option__icon {
  background: var(--el-color-warning-light-8);
  color: var(--el-color-warning-dark-2);
}
.workflow-status-option--done.is-selected .workflow-status-option__icon {
  background: var(--el-color-success-light-8);
  color: var(--el-color-success-dark-2);
}
.workflow-status-option__copy {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}
.workflow-status-option__title { font-size: 14px; font-weight: 600; color: var(--el-text-color-primary); }
.workflow-status-option:focus-within {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
}
.workflow-status-option.is-disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.workflow-status-dialog-wrapper :deep(.el-dialog__header) {
  padding: 18px 24px 12px;
}
.workflow-status-dialog-wrapper :deep(.el-dialog__body) {
  padding: 16px 24px 12px;
}
.workflow-status-dialog-wrapper :deep(.el-dialog__footer) {
  padding: 12px 24px 18px;
}
.workflow-status-dialog-wrapper :deep(.el-button--primary.is-disabled) {
  color: #ffffff;
  background: #a9cdf5;
  border-color: #a9cdf5;
}
</style>
