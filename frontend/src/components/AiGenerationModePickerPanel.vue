<template>
  <div class="gen-settings-body">
    <div class="gen-settings-section">
      <span class="gen-settings-label">生成模式</span>
      <div class="mode-picker-options" role="radiogroup" aria-label="生成模式">
        <button
          v-for="mode in modeOptions"
          :key="mode.value"
          type="button"
          class="mode-picker-option"
          :class="{ active: draftMode === mode.value }"
          role="radio"
          :aria-checked="draftMode === mode.value"
          @click="emit('update:draftMode', mode.value)"
        >
          <span class="mode-picker-option-head">
            <strong>{{ mode.title }}</strong>
            <el-tag size="small" :type="mode.tagType">{{ mode.badge }}</el-tag>
          </span>
          <span class="mode-picker-option-desc">{{ mode.desc }}</span>
          <span class="mode-picker-option-scope">{{ mode.scope }}</span>
          <span v-if="mode.estimate" class="mode-picker-option-estimate">{{ mode.estimate }}</span>
          <span class="mode-picker-option-cost">{{ costTextOf(mode.value) }}</span>
        </button>
      </div>
    </div>

    <div class="gen-settings-section">
      <span class="gen-settings-label">用例生成模型</span>
      <div class="gen-settings-model" :class="{ 'is-system': !needModel }">
        <div class="gsm-copy">
          <strong>{{ modelTitleText }}</strong>
          <small v-if="modelSubText">{{ modelSubText }}</small>
        </div>
        <el-button type="primary" class="gsm-pick" :disabled="!needModel" @click="emit('pick-model')">选择模型</el-button>
      </div>
    </div>

    <div class="gen-settings-summary">
      <span class="gss-target">本次目标：{{ targetText }}</span>
      <span class="gss-cost">{{ costTextOf(draftMode) }}</span>
    </div>

    <div v-if="showFooter" class="gen-settings-footer">
      <el-button @click="emit('cancel')">取消</el-button>
      <el-button v-if="showPrevious" @click="emit('back')">上一步</el-button>
      <el-button type="primary" class="ai-generate-button" :disabled="loading || !canStart" @click="emit('confirm')">
        开始生成（{{ interfaces.length }}）
      </el-button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  modeOptions: { type: Array, default: () => [] },
  draftMode: { type: String, default: 'normal' },
  needModel: { type: Boolean, default: false },
  modelTitleText: { type: String, default: '' },
  modelSubText: { type: String, default: '' },
  targetText: { type: String, default: '' },
  costTextOf: { type: Function, default: () => '' },
  interfaces: { type: Array, default: () => [] },
  canStart: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  showFooter: { type: Boolean, default: false },
  showPrevious: { type: Boolean, default: false },
})
const emit = defineEmits(['update:draftMode', 'pick-model', 'confirm', 'cancel', 'back'])
</script>

<style scoped>
.gen-settings-body { display: flex; flex-direction: column; gap: 14px; min-width: 0; min-height: 0; }
.gen-settings-section { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.gen-settings-label { color: var(--el-text-color-secondary); font-size: 13px; }
.mode-picker-options { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.mode-picker-option {
  display: flex; min-width: 0; padding: 12px; border: 1px solid var(--el-border-color); border-radius: 8px;
  background: var(--el-bg-color); color: inherit; cursor: pointer; flex-direction: column; align-items: stretch;
  gap: 6px; text-align: left; transition: border-color .2s, box-shadow .2s;
}
.mode-picker-option:hover { border-color: var(--el-color-primary-light-3); }
.mode-picker-option.active { border: 2px solid var(--el-color-primary); padding: 11px; background: var(--el-color-primary-light-9); box-shadow: 0 0 0 3px var(--el-color-primary-light-8); }
.mode-picker-option-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.mode-picker-option-head strong { color: var(--el-text-color-primary); font-size: 14px; }
.mode-picker-option-desc, .mode-picker-option-scope, .mode-picker-option-cost { color: var(--el-text-color-regular); font-size: 12px; line-height: 1.45; }
.mode-picker-option-scope { color: var(--el-text-color-secondary); }
.mode-picker-option-estimate { color: var(--el-color-primary-dark-2); font-weight: 500; }
.mode-picker-option-cost { color: var(--el-color-primary-dark-2); }
.gen-settings-model { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-width: 0; padding: 9px 12px; border: 1px solid #79BBFF; border-radius: 8px; background: #ECF5FF; }
.gen-settings-model.is-system { border-color: var(--el-border-color-lighter); background: var(--el-fill-color-lighter); }
.gsm-copy { display: flex; min-width: 0; flex-direction: column; gap: 3px; }
.gsm-copy strong { overflow: hidden; color: var(--el-text-color-primary); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.gsm-copy small { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.45; }
.gsm-pick { flex: 0 0 auto; }
.gen-settings-summary { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px; border-radius: 7px; background: var(--el-fill-color-light); color: var(--el-text-color-secondary); font-size: 13px; }
.gss-target { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gss-cost { flex: 0 0 auto; color: var(--el-color-primary); font-weight: 600; }
.gen-settings-footer { display: flex; flex: 0 0 auto; justify-content: flex-end; gap: 8px; min-width: 0; margin-top: auto; padding-top: 14px; border-top: 1px solid var(--el-border-color-lighter); white-space: nowrap; }
@media (max-width: 680px) {
  .mode-picker-options { grid-template-columns: 1fr; }
  .gen-settings-summary { align-items: flex-start; flex-direction: column; }
  .gss-target { white-space: normal; }
}
</style>
