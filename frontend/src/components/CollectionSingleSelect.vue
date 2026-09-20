<template>
  <div class="collection-single-select-wrapper">
  <div v-if="displayMode === 'cascader'" class="collection-single-select__cascader-wrap">
    <el-cascader
      ref="cascaderRef"
      :model-value="modelValue"
      :options="collectionTree"
      :props="cascaderProps"
      :disabled="disabled"
      :clearable="clearable"
      :filterable="filterable"
      :placeholder="placeholder"
      :show-all-levels="showAllLevels"
      popper-class="collection-single-select-cascader-popper"
      class="collection-single-select__cascader"
      style="display:block;width:100%"
      @update:model-value="selectCascaderCollection"
    >
      <template #default="{ data }">
        <span class="collection-single-select__cascader-option" @click.stop="selectCascaderNode(data)">
          <CollectionNodeLabel :node="data" />
        </span>
      </template>
    </el-cascader>
    <span
      v-if="selectedNode"
      class="collection-single-select__cascader-count"
      :class="`is-${selectedStatusType}`"
      aria-hidden="true"
    >({{ selectedNode.interface_count || 0 }})</span>
  </div>
  <el-popover
    v-else
    v-model:visible="visible"
    placement="bottom-start"
    trigger="click"
    :teleported="true"
    :hide-after="0"
    popper-class="collection-single-select-popper"
    @show="resetPanel"
  >
    <template #reference>
      <div class="collection-single-select" :class="{ 'is-disabled': disabled }">
        <button
          type="button"
          class="collection-single-select__trigger"
          :disabled="disabled"
          :aria-label="selectedPath ? `当前接口集：${selectedPath}` : ariaLabel"
          :aria-expanded="visible"
          :title="selectedPath || placeholder"
          @keydown.enter.prevent.stop="toggleVisible"
          @keydown.space.prevent.stop="toggleVisible"
        >
          <el-icon class="collection-single-select__folder"><FolderOpened /></el-icon>
          <span class="collection-single-select__path" :class="{ 'is-placeholder': !selectedNode }">
            {{ selectedNode?.name || selectedPath || placeholder }}
          </span>
          <span
            v-if="selectedNode"
            class="collection-single-select__count"
            :class="`is-${selectedStatusType}`"
            :title="selectedStatusHint"
          >({{ selectedNode.interface_count || 0 }})</span>
          <el-icon v-if="loading" class="is-loading"><Loading /></el-icon>
          <el-icon v-else class="collection-single-select__arrow"><ArrowDown /></el-icon>
        </button>
        <button
          v-if="clearable && selectedNode && !disabled"
          type="button"
          class="collection-single-select__clear"
          aria-label="清空接口集"
          @click.stop="clearSelection"
        ><el-icon><Close /></el-icon></button>
      </div>
    </template>

    <CollectionCascadePanel
      ref="panelRef"
      :model-value="modelValue"
      :collection-tree="collectionTree"
      :disabled-ids="disabledIds"
      :filterable="filterable"
      :filter-placeholder="filterPlaceholder"
      :empty-text="emptyText"
      :display-mode="displayMode"
      @update:model-value="selectCollection"
    />
  </el-popover>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ArrowDown, Close, FolderOpened, Loading } from '@element-plus/icons-vue'
import CollectionCascadePanel from './CollectionCascadePanel.vue'
import CollectionNodeLabel from './CollectionNodeLabel.vue'
import {
  findCollectionPath,
  getCollectionStatusHint,
  getCollectionStatusType,
  formatCollectionPath,
} from '@/utils/interfaceCollections'

const props = defineProps({
  modelValue: { type: [Number, String], default: null },
  collectionTree: { type: Array, default: () => [] },
  disabledIds: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  clearable: { type: Boolean, default: true },
  filterable: { type: Boolean, default: false },
  filterPlaceholder: { type: String, default: '搜索接口集名称' },
  emptyText: { type: String, default: '暂无接口集' },
  displayMode: { type: String, default: 'cascade' },
  showAllLevels: { type: Boolean, default: true },
  placeholder: { type: String, default: '请选择接口集' },
  ariaLabel: { type: String, default: '选择接口集' },
})

const emit = defineEmits(['update:modelValue', 'change'])

const visible = ref(false)
const panelRef = ref(null)
const cascaderRef = ref(null)
const cascaderProps = {
  value: 'id',
  label: 'name',
  children: 'children',
  multiple: false,
  checkStrictly: true,
  emitPath: false,
  showPrefix: false,
  checkOnClickNode: false,
}

const selectedPathNodes = computed(() => findCollectionPath(props.collectionTree, props.modelValue))
const selectedNode = computed(() => selectedPathNodes.value[selectedPathNodes.value.length - 1] || null)
const selectedPath = computed(() => formatCollectionPath(props.collectionTree, selectedNode.value))
const selectedStatusType = computed(() => getCollectionStatusType(selectedNode.value))
const selectedStatusHint = computed(() => getCollectionStatusHint(selectedNode.value))

function resetPanel() {
  panelRef.value?.resetNavigation()
}

function toggleVisible() {
  if (!props.disabled) visible.value = !visible.value
}

function close() {
  visible.value = false
  cascaderRef.value?.togglePopperVisible?.(false)
}

defineExpose({ close })

function selectCollection(id) {
  emit('update:modelValue', id)
  emit('change', id)
  close()
}

function selectCascaderCollection(id) {
  selectCollection(id == null ? null : id)
}

function selectCascaderNode(node) {
  selectCascaderCollection(node?.id)
}

function clearSelection() {
  emit('update:modelValue', null)
  emit('change', null)
}
</script>

<style scoped>
.collection-single-select-wrapper { display: block; width: 100%; min-width: 0; }
.collection-single-select__cascader-wrap { position: relative; width: 100%; min-width: 0; }
.collection-single-select__cascader :deep(.el-input__wrapper) { padding-right: 66px; }
.collection-single-select__cascader-count {
  position: absolute;
  top: 50%;
  right: 30px;
  transform: translateY(-50%);
  pointer-events: none;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
}
.collection-single-select__cascader-count.is-empty { color: var(--el-text-color-placeholder); }
.collection-single-select__cascader-count.is-pending { color: var(--el-color-warning); }
.collection-single-select__cascader-count.is-done { color: var(--el-color-success); }

.collection-single-select {
  display: flex;
  align-items: stretch;
  width: 100%;
  min-width: 0;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  background: var(--el-fill-color-blank);
  transition: border-color .2s, box-shadow .2s;
}

.collection-single-select:hover:not(.is-disabled),
.collection-single-select:focus-within:not(.is-disabled) {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary-light-8);
}

.collection-single-select.is-disabled {
  background: var(--el-disabled-bg-color);
  cursor: not-allowed;
}

.collection-single-select__trigger {
  display: flex;
  align-items: center;
  min-width: 0;
  flex: 1 1 auto;
  gap: 8px;
  box-sizing: border-box;
  min-height: 32px;
  padding: 5px 10px;
  border: 0;
  border-radius: 6px;
  outline: 0;
  background: transparent;
  color: var(--el-text-color-primary);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.collection-single-select__trigger:disabled { cursor: not-allowed; }
.collection-single-select__folder { flex: 0 0 auto; color: var(--el-color-primary); }
.collection-single-select__path { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.collection-single-select__path.is-placeholder { color: var(--el-text-color-placeholder); }
.collection-single-select__count { flex: 0 0 auto; font-size: 12px; font-weight: 600; }
.collection-single-select__count.is-empty { color: var(--el-text-color-placeholder); }
.collection-single-select__count.is-pending { color: var(--el-color-warning); }
.collection-single-select__count.is-done { color: var(--el-color-success); }
.collection-single-select__arrow { flex: 0 0 auto; margin-left: auto; color: var(--el-text-color-placeholder); }
.collection-single-select__trigger .is-loading { flex: 0 0 auto; margin-left: auto; }

.collection-single-select__clear {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 28px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--el-text-color-placeholder);
  cursor: pointer;
}

.collection-single-select__clear:hover { color: var(--el-text-color-secondary); }

:global(.collection-single-select-popper) {
  width: max-content !important;
  min-width: 240px;
  max-width: min(720px, calc(100vw - 32px));
  padding: 10px;
}

.collection-single-select__cascader {
  display: block;
  width: 100%;
  min-width: 0;
}

.collection-single-select__cascader :deep(.el-cascader),
.collection-single-select__cascader :deep(.el-input) {
  display: block;
  width: 100% !important;
  min-width: 0;
}

.collection-single-select__cascader-option {
  display: block;
  width: 100%;
  min-width: 0;
  cursor: pointer;
}

:global(.collection-single-select-cascader-popper) {
  max-width: min(720px, calc(100vw - 48px));
}

:global(.collection-single-select-cascader-popper .el-cascader-panel) {
  max-width: min(720px, calc(100vw - 48px));
  overflow-x: auto;
}

:global(.collection-single-select-cascader-popper .el-cascader-menu) {
  min-width: 180px;
  max-height: 320px;
}

:global(.collection-single-select-cascader-popper .el-cascader-menu__wrap) {
  max-height: 320px;
}

:global(.collection-single-select-cascader-popper .el-cascader-node) {
  white-space: nowrap;
}

:global(.collection-single-select-cascader-popper .el-cascader-node__postfix) {
  right: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 100%;
}

</style>
