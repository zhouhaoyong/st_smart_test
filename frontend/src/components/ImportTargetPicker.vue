<template>
  <div class="import-target-picker" :class="{ 'is-inline': !!labelWidth }">
    <div
      v-if="label"
      class="import-target-label"
      :style="labelWidth ? { width: labelWidth } : null"
    >
      <span v-if="required" class="import-target-required" aria-hidden="true">*</span>{{ label }}
    </div>
    <button
      type="button"
      class="collection-target-card"
      :class="{ 'is-empty': !targetReady }"
      :title="displayPath || placeholder"
      @click="openPicker"
      @keydown.enter.prevent="openPicker"
      @keydown.space.prevent="openPicker"
    >
      <span class="collection-target-main">
        <el-icon class="collection-target-icon"><FolderOpened /></el-icon>
        <span class="collection-target-copy">
          <span class="collection-target-path">{{ displayPath || placeholder }}</span>
        </span>
      </span>
      <span class="collection-target-action">{{ targetReady ? '更换' : '选择' }}<el-icon><ArrowRight /></el-icon></span>
    </button>

    <el-dialog
      v-model="pickerVisible"
      title="选择导入目标"
      width="680px"
      append-to-body
      destroy-on-close
      class="collection-picker-dialog"
      @opened="focusNewPathInput"
    >
      <div class="collection-picker-content">
        <div class="collection-picker-mode collection-picker-segmented" role="tablist" aria-label="接口集目标类型">
          <button
            type="button"
            class="collection-picker-mode-item"
            :class="{ active: pickerMode === 'existing' }"
            role="tab"
            :aria-selected="pickerMode === 'existing'"
            :disabled="!hasExistingCollections"
            :title="hasExistingCollections ? '' : '当前项目还没有接口集'"
            @click="pickerMode = 'existing'"
          >选择已有接口集</button>
          <button
            type="button"
            class="collection-picker-mode-item"
            :class="{ active: pickerMode === 'new' }"
            role="tab"
            :aria-selected="pickerMode === 'new'"
            @click="switchPickerMode('new')"
          >新建接口集</button>
        </div>
        <div v-if="pickerMode === 'existing'" class="collection-picker-panel">
          <CollectionCascadePanel
            v-model="pickerPendingId"
            :collection-tree="props.collectionTree"
            display-mode="tree"
            filterable
            empty-text="暂无已有接口集，请切换到“新建接口集”"
          />
        </div>
        <div v-else class="collection-picker-panel collection-picker-new-panel">
          <div class="collection-picker-new-title">输入接口集路径</div>
          <div class="collection-picker-new-description">使用 <code>||</code> 分隔层级。同一层级下已有同名接口集时直接复用，不会重复创建。</div>
          <el-input
            v-model="pickerNewPath"
            clearable
            autofocus
            ref="pickerNewInput"
            placeholder="例如：系统||模块||功能"
            class="collection-picker-new-input"
            @keyup.enter="confirmNewPath"
          />
          <div v-if="pickerPreviewNodes.length" class="collection-picker-create-preview">
            <span class="collection-picker-create-title">将使用此层级：</span>
            <template v-for="(node, index) in pickerPreviewNodes" :key="`${index}-${node.name}`">
              <span v-if="index" class="collection-picker-create-sep">/</span>
              <span class="collection-picker-create-node">
                {{ node.name }}
                <span class="collection-picker-create-flag" :class="node.exists ? 'is-reuse' : 'is-new'">
                  {{ node.exists ? '复用已有' : '新建' }}
                </span>
              </span>
            </template>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="collection-picker-footer">
          <span class="collection-picker-selected">
            当前目标：{{ pickerTargetPath || '未选择接口集' }}
          </span>
          <div>
            <el-button @click="pickerVisible = false">取消</el-button>
            <el-button
              type="primary"
              :disabled="!pickerCanConfirm"
              @click="confirmPickerTarget"
            >确定目标</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * 导入目标选择器：文件导入与 cURL 导入共用。
 * 三条导入链路的目标选择交互一致，用户不必先在左侧选中接口集再打开弹窗。
 * 目标状态由调用方持有（已有接口集 / 新建路径），本组件只负责挑选与回显。
 */
import { computed, nextTick, ref } from 'vue'
import { ArrowRight, FolderOpened } from '@element-plus/icons-vue'
import { formatCollectionPath, splitCollectionPathInput } from '@/utils/interfaceCollections'
import CollectionCascadePanel from './CollectionCascadePanel.vue'

const props = defineProps({
  // 'existing' 选已有接口集，'new' 按路径新建
  mode: { type: String, default: 'existing' },
  collectionId: { type: [Number, String], default: null },
  newPath: { type: String, default: '' },
  collectionTree: { type: Array, default: () => [] },
  // 当前选中的接口集可能不在树里（如树尚未加载完），用它补名称
  targetCollection: { type: Object, default: null },
  label: { type: String, default: '导入到接口集' },
  // 给了宽度就走「左文案 + 右选择框」的行内布局，留空则文案在上、选择框在下
  labelWidth: { type: String, default: '' },
  required: { type: Boolean, default: false },
  placeholder: { type: String, default: '请选择接口集或新建接口集' },
})
const emit = defineEmits(['update:mode', 'update:collectionId', 'update:newPath'])

const pickerVisible = ref(false)
const pickerMode = ref('existing')
const pickerNewPath = ref('')
const pickerPendingId = ref(null)
const pickerNewInput = ref(null)

const hasExistingCollections = computed(() => (props.collectionTree || []).length > 0)
const newPathSegments = computed(() => splitCollectionPathInput(props.newPath))
const targetReady = computed(() => (
  props.mode === 'new' ? newPathSegments.value.length > 0 : !!props.collectionId
))
const selectedPath = computed(() => {
  if (!props.collectionId) return ''
  const isTargetCollection = props.targetCollection?.id === props.collectionId
  return formatCollectionPath(props.collectionTree, {
    id: props.collectionId,
    name: isTargetCollection ? props.targetCollection?.name : undefined,
  })
})
const displayPath = computed(() => (
  props.mode === 'new' ? newPathSegments.value.join(' / ') : selectedPath.value
))

const pendingPath = computed(() => {
  if (!pickerPendingId.value) return ''
  const isTargetCollection = props.targetCollection?.id === pickerPendingId.value
  return formatCollectionPath(props.collectionTree, {
    id: pickerPendingId.value,
    name: isTargetCollection ? props.targetCollection?.name : undefined,
  })
})
const pickerPathSegments = computed(() => splitCollectionPathInput(pickerNewPath.value))
const pickerCreatePreview = computed(() => pickerPathSegments.value.join(' / '))
// 逐级判断这一层在当前项目里是否已经有同名接口集，让用户知道哪几级是复用、哪几级才真的新建
const pickerPreviewNodes = computed(() => {
  let siblings = props.collectionTree || []
  let broken = false
  return pickerPathSegments.value.map(name => {
    const hit = broken
      ? null
      : (siblings || []).find(node => String(node?.name || '').trim() === name)
    if (hit) siblings = hit.children || []
    else { broken = true; siblings = [] }
    return { name, exists: !!hit }
  })
})
const pickerTargetPath = computed(() => (
  pickerMode.value === 'new' ? pickerCreatePreview.value : pendingPath.value
))
const pickerCanConfirm = computed(() => (
  pickerMode.value === 'new' ? pickerPathSegments.value.length > 0 : !!pickerPendingId.value
))

function focusNewPathInput() {
  nextTick(() => pickerNewInput.value?.focus())
}

function switchPickerMode(mode) {
  pickerMode.value = mode
  if (mode === 'new') focusNewPathInput()
}

function openPicker() {
  // 项目里一个接口集都没有时，"选择已有"必然是空的，直接落在"新建接口集"，
  // 省掉用户先看到空列表再自己切页签这一步。
  pickerMode.value = (props.mode === 'new' || !hasExistingCollections.value) ? 'new' : 'existing'
  pickerPendingId.value = props.collectionId || null
  pickerNewPath.value = props.mode === 'new' ? props.newPath : ''
  pickerVisible.value = true
}

function confirmPickerTarget() {
  if (pickerMode.value === 'new') {
    confirmNewPath()
    return
  }
  if (!pickerPendingId.value) return
  emit('update:collectionId', pickerPendingId.value)
  emit('update:newPath', '')
  emit('update:mode', 'existing')
  pickerVisible.value = false
}

function confirmNewPath() {
  if (!pickerPathSegments.value.length) return
  emit('update:newPath', pickerNewPath.value.trim())
  emit('update:collectionId', null)
  emit('update:mode', 'new')
  pickerPendingId.value = null
  pickerVisible.value = false
}

defineExpose({ openPicker })
</script>

<style scoped>
.import-target-picker { min-width: 0; }
.import-target-label { margin-bottom: 8px; color: var(--el-text-color-regular); font-size: 14px; line-height: 20px; }
.import-target-required { margin-right: 4px; color: var(--el-color-danger); }
/* 行内布局：文案宽度固定右对齐，和同一弹窗里 el-form 的标签列对齐 */
.import-target-picker.is-inline { display: flex; align-items: center; }
.import-target-picker.is-inline .import-target-label {
  flex: 0 0 auto; box-sizing: border-box; margin-bottom: 0; padding-right: 12px;
  text-align: right; white-space: nowrap;
}
.import-target-picker.is-inline .collection-target-card { flex: 1 1 auto; min-width: 0; }
.collection-target-card {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  width: 100%; min-height: 40px; box-sizing: border-box; padding: 7px 12px;
  border: 1px solid var(--el-border-color); border-radius: 6px;
  background: var(--el-fill-color-blank); color: var(--el-text-color-primary);
  font: inherit; text-align: left; cursor: pointer;
  transition: border-color .2s, background-color .2s, box-shadow .2s;
}
.collection-target-card:hover,
.collection-target-card:focus-visible {
  border-color: var(--el-color-primary); background: var(--el-color-primary-light-9);
  outline: none; box-shadow: 0 0 0 2px var(--el-color-primary-light-8);
}
.collection-target-card.is-empty .collection-target-path { color: var(--el-text-color-placeholder); }
.collection-target-main { display: flex; flex: 1 1 0; align-items: center; gap: 10px; min-width: 0; }
.collection-target-icon { flex: 0 0 auto; color: var(--el-color-primary); font-size: 16px; }
.collection-target-copy { display: block; flex: 1 1 auto; width: 0; min-width: 0; }
.collection-target-path { display: block; min-width: 0; max-width: 100%; overflow: hidden; color: var(--el-text-color-primary); text-overflow: ellipsis; white-space: nowrap; }
.collection-target-action { display: inline-flex; align-items: center; gap: 4px; flex: 0 0 auto; color: var(--el-color-primary); font-size: 13px; }

.collection-picker-content { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.collection-picker-mode {
  display: flex; gap: 2px; width: min(100%, 320px); box-sizing: border-box;
  padding: 3px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px;
  background: var(--el-fill-color-light);
}
.collection-picker-mode-item {
  flex: 1 1 0; min-width: 0; padding: 7px 12px; border: 0; border-radius: 6px;
  background: transparent; color: var(--el-text-color-secondary); font: inherit;
  cursor: pointer; white-space: nowrap; transition: color .2s, background-color .2s, box-shadow .2s;
}
.collection-picker-mode-item:hover:not(:disabled) { color: var(--el-color-primary); }
.collection-picker-mode-item:disabled { color: var(--el-text-color-disabled); cursor: not-allowed; }
.collection-picker-mode-item.active {
  background: var(--el-bg-color); color: var(--el-color-primary);
  box-shadow: 0 1px 3px rgb(0 0 0 / 8%);
}
.collection-picker-panel { display: flex; flex-direction: column; gap: 12px; min-height: 320px; }
.collection-picker-panel :deep(.collection-cascade-panel__viewport) {
  align-self: stretch;
  width: 100%;
}
.collection-picker-new-panel { min-height: 0; justify-content: flex-start; padding: 4px 0 8px; }
.collection-picker-new-title { color: var(--el-text-color-primary); font-size: 14px; font-weight: 600; }
.collection-picker-new-description { color: var(--el-text-color-secondary); font-size: 12px; }
.collection-picker-new-description code { padding: 1px 4px; border-radius: 3px; background: var(--el-fill-color); color: var(--el-color-primary); font-family: inherit; }
.collection-picker-new-input { margin-top: 4px; }
.collection-picker-create-preview { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 6px; font-size: 13px; }
.collection-picker-create-title { color: var(--el-text-color-regular); }
.collection-picker-create-sep { color: var(--el-text-color-placeholder); }
.collection-picker-create-node { display: inline-flex; align-items: center; gap: 4px; color: var(--el-text-color-primary); }
.collection-picker-create-flag { padding: 0 6px; border-radius: 9px; font-size: 12px; line-height: 18px; }
.collection-picker-create-flag.is-reuse { background: var(--el-fill-color); color: var(--el-text-color-secondary); }
.collection-picker-create-flag.is-new { background: var(--el-color-primary-light-9); color: var(--el-color-primary); }
.collection-picker-footer { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px 16px; }
.collection-picker-selected {
  flex: 1 1 240px; min-width: 0; overflow: hidden; color: var(--el-text-color-secondary);
  text-overflow: ellipsis; white-space: nowrap; font-size: 12px;
}

/* append-to-body 后弹窗根节点被 teleport，scoped 选择器命中不到，故用 :global */
:global(.collection-picker-dialog) { max-width: min(680px, calc(100vw - 32px)); }
:global(.collection-picker-dialog .el-dialog__body) { padding-top: 8px; }
</style>
