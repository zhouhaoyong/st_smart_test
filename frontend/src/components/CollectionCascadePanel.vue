<template>
  <div class="collection-cascade-panel">
    <el-input
      v-if="filterable"
      v-model="keyword"
      clearable
      :placeholder="filterPlaceholder"
      class="collection-cascade-panel__search"
    />

    <div v-if="!filteredTree.length" class="collection-cascade-panel__empty">
      {{ emptyText }}
    </div>
    <div v-else class="collection-cascade-panel__viewport" :class="{ 'is-tree': displayMode === 'tree' }">
      <div v-if="displayMode === 'tree'" class="collection-cascade-panel__tree-wrap">
        <el-tree
          ref="treeRef"
          :data="treeData"
          node-key="id"
          :props="treeProps"
          :default-expanded-keys="treeExpandedKeys"
          :expand-on-click-node="false"
          class="collection-cascade-panel__tree"
        >
          <template #default="{ data }">
            <div
              class="collection-cascade-panel__tree-option"
              :class="{
                'is-selected': isSelected(data),
                'is-disabled': isDisabled(data),
              }"
              :title="getCollectionStatusHint(data)"
              @click.stop="selectNode(data)"
            >
              <button
                type="button"
                class="collection-cascade-panel__selection"
                :class="{ 'is-multiple': multiple }"
                :role="multiple ? 'checkbox' : 'radio'"
                :aria-checked="isSelected(data)"
                :aria-label="`选择${data.name || '接口集'}`"
                :disabled="isDisabled(data)"
                @click.stop="selectNode(data)"
              >
                <Check v-if="multiple && isSelected(data)" class="collection-cascade-panel__selection-check" aria-hidden="true" />
                <span v-else-if="isSelected(data)" class="collection-cascade-panel__selection-dot" aria-hidden="true" />
              </button>
              <button
                type="button"
                class="collection-cascade-panel__tree-label"
                :disabled="isDisabled(data)"
                @click.stop="selectNode(data)"
              >
                <CollectionNodeLabel
                  :node="data"
                  :show-count="showCount"
                  :show-tooltip="false"
                  :disabled="isDisabled(data)"
                />
              </button>
            </div>
          </template>
        </el-tree>
      </div>
      <div v-else class="collection-cascade-panel__content">
        <div v-if="activePathNodes.length" class="collection-cascade-panel__breadcrumb" aria-label="当前接口集路径">
          <button
            type="button"
            class="collection-cascade-panel__breadcrumb-back"
            aria-label="返回上一级"
            @click="goBack"
          ><ArrowLeft /></button>
          <button
            type="button"
            class="collection-cascade-panel__breadcrumb-item"
            @click="goToPath(-1)"
          >根目录</button>
          <template v-for="(node, index) in activePathNodes" :key="node.id">
            <span class="collection-cascade-panel__breadcrumb-separator" aria-hidden="true">/</span>
            <button
              type="button"
              class="collection-cascade-panel__breadcrumb-item"
              :class="{ 'is-current': index === activePathNodes.length - 1 }"
              :title="node.name"
              @click="goToPath(index)"
            >{{ node.name }}</button>
          </template>
        </div>

        <Transition name="collection-cascade-panel__slide" mode="out-in">
          <div :key="activePathIds.join('/') || 'root'" class="collection-cascade-panel__level">
            <div v-if="!currentNodes.length" class="collection-cascade-panel__empty">
              {{ activePathNodes.length ? '暂无下级接口集' : emptyText }}
            </div>
            <template v-else>
              <div
                v-for="node in currentNodes"
                :key="node.id"
                class="collection-cascade-panel__option"
                :class="{
                  'is-selected': isSelected(node),
                  'is-disabled': isDisabled(node),
                }"
                :title="getCollectionStatusHint(node)"
              >
                <button
                  type="button"
                  class="collection-cascade-panel__selection"
                  :class="{ 'is-multiple': multiple }"
                  :role="multiple ? 'checkbox' : 'radio'"
                  :aria-checked="isSelected(node)"
                  :aria-label="`选择${node.name || '接口集'}`"
                  :disabled="isDisabled(node)"
                  @click="selectNode(node)"
                >
                  <Check v-if="multiple && isSelected(node)" class="collection-cascade-panel__selection-check" aria-hidden="true" />
                  <span v-else-if="isSelected(node)" class="collection-cascade-panel__selection-dot" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  class="collection-cascade-panel__label"
                  :disabled="isDisabled(node)"
                  @click="selectNode(node)"
                >
                  <CollectionNodeLabel
                    :node="node"
                    :show-count="showCount"
                    :show-tooltip="false"
                    :disabled="isDisabled(node)"
                  />
                </button>
                <button
                  v-if="hasChildren(node)"
                  type="button"
                  class="collection-cascade-panel__arrow"
                  :aria-label="`进入${node.name || '下一级接口集'}`"
                  :disabled="isDisabled(node)"
                  @click="expandNode(node)"
                ><ArrowRight /></button>
              </div>
            </template>
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { ArrowLeft, ArrowRight, Check } from '@element-plus/icons-vue'
import CollectionNodeLabel from './CollectionNodeLabel.vue'
import { findCollectionPath, getCollectionStatusHint } from '@/utils/interfaceCollections'

const props = defineProps({
  modelValue: { type: [Number, String, Array], default: null },
  collectionTree: { type: Array, default: () => [] },
  disabledIds: { type: Array, default: () => [] },
  multiple: { type: Boolean, default: false },
  showCount: { type: Boolean, default: true },
  displayMode: { type: String, default: 'cascade' },
  filterable: { type: Boolean, default: false },
  filterPlaceholder: { type: String, default: '搜索接口集名称' },
  emptyText: { type: String, default: '暂无接口集' },
})

const emit = defineEmits(['update:modelValue', 'select'])

const keyword = ref('')
const activePathIds = ref([])
const internalSelectionId = ref(null)
const treeRef = ref(null)

const disabledIdSet = computed(() => new Set((props.disabledIds || []).map(id => String(id))))
const selectedId = computed(() => (props.modelValue == null ? '' : String(props.modelValue)))
const selectedIds = computed(() => new Set(
  (Array.isArray(props.modelValue) ? props.modelValue : []).map(id => String(id)),
))
const treeProps = { children: 'children', label: 'name', disabled: 'disabled' }

function filterNodes(nodes, searchText) {
  const result = []
  for (const node of nodes || []) {
    const children = filterNodes(node.children || [], searchText)
    const matches = !searchText || String(node.name || '').toLowerCase().includes(searchText)
    if (matches || children.length) result.push({ ...node, children })
  }
  return result
}

const filteredTree = computed(() => filterNodes(props.collectionTree, keyword.value.trim().toLowerCase()))

function decorateTree(nodes) {
  return (nodes || []).map(node => ({
    ...node,
    disabled: isDisabled(node),
    children: decorateTree(node.children || []),
  }))
}

function collectExpandableIds(nodes, result = []) {
  for (const node of nodes || []) {
    if (node.children?.length) {
      result.push(node.id)
      collectExpandableIds(node.children, result)
    }
  }
  return result
}

const treeData = computed(() => decorateTree(filteredTree.value))
const treeExpandedKeys = computed(() => collectExpandableIds(treeData.value))

const activePathNodes = computed(() => {
  const path = []
  let nodes = filteredTree.value
  for (const pathId of activePathIds.value) {
    const node = nodes.find(item => String(item.id) === String(pathId))
    if (!node) break
    path.push(node)
    nodes = node.children || []
  }
  return path
})

const currentNodes = computed(() => {
  const currentNode = activePathNodes.value[activePathNodes.value.length - 1]
  return currentNode?.children || filteredTree.value
})

function syncNavigation() {
  if (props.multiple) {
    activePathIds.value = []
    return
  }
  const path = findCollectionPath(props.collectionTree, props.modelValue)
  const selectedNode = path[path.length - 1]
  const navigationPath = hasChildren(selectedNode) ? path : path.slice(0, -1)
  activePathIds.value = navigationPath.map(node => node.id)
}

watch(() => props.collectionTree, syncNavigation, { deep: true, immediate: true })
watch(() => props.modelValue, value => {
  if (internalSelectionId.value === (value == null ? '' : String(value))) {
    internalSelectionId.value = null
    return
  }
  syncNavigation()
})
watch([() => props.collectionTree, keyword, () => props.displayMode], () => {
  if (props.displayMode !== 'tree') return
  nextTick(() => treeRef.value?.setExpandedKeys(treeExpandedKeys.value))
}, { deep: true, immediate: true })

function hasChildren(node) {
  return Boolean(node?.children?.length)
}

function isDisabled(node) {
  return disabledIdSet.value.has(String(node?.id))
}

function isSelected(node) {
  if (props.multiple) return selectedIds.value.has(String(node?.id))
  return selectedId.value !== '' && selectedId.value === String(node?.id)
}

function expandNode(node) {
  if (isDisabled(node)) return
  activePathIds.value = [...activePathIds.value, node.id]
}

function goToPath(index) {
  activePathIds.value = index < 0 ? [] : activePathIds.value.slice(0, index + 1)
}

function goBack() {
  goToPath(activePathIds.value.length - 2)
}

function selectNode(node) {
  if (isDisabled(node)) return
  if (props.multiple) {
    const currentIds = Array.isArray(props.modelValue) ? props.modelValue : []
    const nodeId = String(node.id)
    const nextIds = selectedIds.value.has(nodeId)
      ? currentIds.filter(id => String(id) !== nodeId)
      : [...currentIds, node.id]
    emit('update:modelValue', nextIds)
    emit('select', node)
    return
  }
  internalSelectionId.value = String(node.id)
  emit('update:modelValue', node.id)
  emit('select', node)
}

function resetNavigation() {
  keyword.value = ''
  if (props.multiple) {
    activePathIds.value = []
    return
  }
  syncNavigation()
}

defineExpose({ resetNavigation })
</script>

<style scoped>
.collection-cascade-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 10px;
}

.collection-cascade-panel__search { flex: 0 0 auto; width: 100%; min-width: 220px; }

.collection-cascade-panel__viewport {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  max-height: 360px;
  overflow-x: hidden;
  overflow-y: auto;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: var(--el-bg-color);
}

.collection-cascade-panel__content { width: 100%; min-width: 0; overflow: hidden; }

.collection-cascade-panel__level {
  width: 100%;
  min-width: 0;
  padding: 6px;
  box-sizing: border-box;
}

.collection-cascade-panel__breadcrumb {
  display: flex;
  align-items: center;
  gap: 3px;
  min-width: 0;
  padding: 7px 8px 3px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
}

.collection-cascade-panel__breadcrumb-back {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--el-text-color-secondary);
  cursor: pointer;
}

.collection-cascade-panel__breadcrumb-back:hover {
  background: var(--el-fill-color-light);
  color: var(--el-color-primary);
}

.collection-cascade-panel__breadcrumb-item {
  min-width: 0;
  max-width: 140px;
  overflow: hidden;
  padding: 2px 4px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: inherit;
  font: inherit;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.collection-cascade-panel__breadcrumb-item:hover,
.collection-cascade-panel__breadcrumb-item.is-current {
  color: var(--el-color-primary);
}

.collection-cascade-panel__breadcrumb-item.is-current { font-weight: 600; }
.collection-cascade-panel__breadcrumb-separator { flex: 0 0 auto; color: var(--el-text-color-placeholder); }

.collection-cascade-panel__slide-enter-active,
.collection-cascade-panel__slide-leave-active { transition: opacity .16s ease, transform .16s ease; }
.collection-cascade-panel__slide-enter-from { opacity: 0; transform: translateX(12px); }
.collection-cascade-panel__slide-leave-to { opacity: 0; transform: translateX(-12px); }

.collection-cascade-panel__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 160px;
  color: var(--el-text-color-placeholder);
}

.collection-cascade-panel__option {
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0;
  gap: 8px;
  box-sizing: border-box;
  padding: 8px 9px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--el-text-color-primary);
  font: inherit;
  text-align: left;
  cursor: default;
}

.collection-cascade-panel__option:hover:not(:disabled),
.collection-cascade-panel__option.is-selected {
  background: var(--el-fill-color-light);
}

.collection-cascade-panel__option.is-selected { background: var(--el-color-primary-light-9); }

.collection-cascade-panel__option.is-disabled { cursor: not-allowed; }

.collection-cascade-panel__selection,
.collection-cascade-panel__label,
.collection-cascade-panel__arrow {
  border: 0;
  background: transparent;
  font: inherit;
}

.collection-cascade-panel__selection {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 16px;
  height: 16px;
  box-sizing: border-box;
  border: 1px solid var(--el-border-color);
  border-radius: 50%;
  background: var(--el-bg-color);
  cursor: pointer;
}

.collection-cascade-panel__selection.is-multiple {
  border-radius: 3px;
}

.collection-cascade-panel__selection:disabled,
.collection-cascade-panel__label:disabled,
.collection-cascade-panel__arrow:disabled { cursor: not-allowed; }

.collection-cascade-panel__option.is-selected .collection-cascade-panel__selection {
  border-color: var(--el-color-primary);
}

.collection-cascade-panel__selection-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--el-color-primary);
}

.collection-cascade-panel__selection-check {
  width: 12px;
  height: 12px;
  color: var(--el-color-primary);
}

.collection-cascade-panel__option.is-selected .collection-cascade-panel__selection.is-multiple {
  background: var(--el-color-primary-light-9);
}

.collection-cascade-panel__arrow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  padding: 0;
  border-radius: 4px;
  color: var(--el-text-color-secondary);
  cursor: pointer;
}

.collection-cascade-panel__arrow:hover:not(:disabled) {
  background: var(--el-fill-color-light);
  color: var(--el-color-primary);
}

.collection-cascade-panel__label {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  min-width: 0;
  padding: 4px 0;
  color: var(--el-text-color-primary);
  text-align: left;
  cursor: pointer;
}

.collection-cascade-panel__label :deep(.collection-node-label) {
  width: 100%;
  min-width: 0;
}

.collection-cascade-panel__viewport.is-tree {
  min-height: 320px;
  max-height: 400px;
  box-sizing: border-box;
  padding: 6px 0;
}

.collection-cascade-panel__tree-wrap,
.collection-cascade-panel__tree {
  width: 100%;
  min-width: 0;
}

.collection-cascade-panel__tree :deep(.el-tree-node__content) {
  height: auto;
  min-height: 38px;
  padding-right: 8px;
}

.collection-cascade-panel__tree :deep(.el-tree-node__expand-icon) {
  flex: 0 0 auto;
  margin-left: 4px;
}

.collection-cascade-panel__tree-option {
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0;
  min-height: 36px;
  box-sizing: border-box;
  gap: 8px;
  padding: 5px 8px 5px 8px;
  border-radius: 5px;
  cursor: pointer;
}

.collection-cascade-panel__tree-option:hover,
.collection-cascade-panel__tree-option.is-selected {
  background: var(--el-color-primary-light-9);
}

.collection-cascade-panel__tree-option.is-disabled {
  cursor: not-allowed;
}

.collection-cascade-panel__tree-option:focus-within {
  outline: 2px solid var(--el-color-primary-light-5);
  outline-offset: -2px;
}

.collection-cascade-panel__tree-label {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  min-width: 0;
  padding: 4px 0;
  border: 0;
  background: transparent;
  color: var(--el-text-color-primary);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.collection-cascade-panel__tree-label:disabled {
  cursor: not-allowed;
}

.collection-cascade-panel__tree-label :deep(.collection-node-label) {
  width: 100%;
  min-width: 0;
}
</style>
