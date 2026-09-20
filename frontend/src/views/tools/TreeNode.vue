<template>
  <li class="tree-node">
    <div
      class="node-row"
      :class="{
        selected: isSelected || (checkable && isChecked),
        expandable: hasChildren,
        'search-match': isSearchMatch,
        'search-active': isSearchActive,
        'preview-active': isPreviewActive,
      }"
      :data-search-path="node.path"
      :data-preview-path="node.path"
    >
      <!-- 复选框默认不显示，只有明确开启批量选取的地方才出现，避免影响 JSONPath 提取工具 -->
      <el-checkbox
        v-if="checkable"
        class="node-check"
        :model-value="isChecked"
        @click.stop
        @update:model-value="onCheck"
      />
      <button
        v-if="hasChildren"
        type="button"
        class="arrow"
        :class="{ expanded }"
        :aria-label="expanded ? '收起字段' : '展开字段'"
        @click.stop="toggleExpanded"
      >
        <el-icon :size="12"><ArrowRight /></el-icon>
      </button>
      <span v-else class="arrow-placeholder"></span>
      <span class="node-content" @click.stop="handleContentClick">
        <span class="node-label">{{ node.label }}</span>
        <span class="node-type">{{ displayType }}</span>
        <span v-if="!hasChildren" class="node-preview">{{ preview }}</span>
      </span>
    </div>
    <ul v-if="expanded && hasChildren" class="children">
      <TreeNode
        v-for="(child, index) in node.children"
        :key="index"
        :node="child"
        :selected-path="selectedPath"
        :checkable="checkable"
        :checked-paths="checkedPaths"
        :search-text="searchText"
        :search-match-paths="searchMatchPaths"
        :search-active-path="searchActivePath"
        :preview-active-path="previewActivePath"
        @select="$emit('select', $event)"
        @check="$emit('check', $event)"
      />
    </ul>
  </li>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'

const props = defineProps({
  node: { type: Object, required: true },
  selectedPath: { type: String, default: '' },
  // 批量选取能力：默认关闭，保持 JSONPath 提取工具原有的单选行为不变
  checkable: { type: Boolean, default: false },
  checkedPaths: { type: Array, default: () => [] },
  searchText: { type: String, default: '' },
  searchMatchPaths: { type: Array, default: () => [] },
  searchActivePath: { type: String, default: '' },
  previewActivePath: { type: String, default: '' },
})

const emit = defineEmits(['select', 'check'])

const expanded = ref(true)

const hasChildren = computed(() => props.node.children && props.node.children.length > 0)
const isSelected = computed(() => props.selectedPath === props.node.path)
const isChecked = computed(() => props.checkedPaths.includes(props.node.path))
const hasSearch = computed(() => Boolean(props.searchText.trim()))
const isSearchMatch = computed(() => hasSearch.value && props.searchMatchPaths.includes(props.node.path))
const isSearchActive = computed(() => isSearchMatch.value && props.searchActivePath === props.node.path)
const isPreviewActive = computed(() => props.previewActivePath === props.node.path)
const isPreviewPathInside = computed(() => {
  const activePath = String(props.previewActivePath || '')
  const nodePath = String(props.node.path || '')
  return Boolean(activePath && nodePath && (
    activePath === nodePath
    || activePath.startsWith(`${nodePath}.`)
    || activePath.startsWith(`${nodePath}[`)
  ))
})

watch(() => props.searchText, value => {
  if (value.trim()) expanded.value = true
})

watch(isPreviewPathInside, inside => {
  if (inside && hasChildren.value) expanded.value = true
}, { immediate: true })

// 勾选要把节点本身带出去：批量生成断言时需要它的值和类型
function onCheck(checked) {
  emit('check', { node: props.node, checked: Boolean(checked) })
}

const displayType = computed(() => {
  const t = props.node.type
  if (t === 'dict') return '{}'
  if (t === 'list') return '[]'
  if (t === 'str') return 'string'
  if (t === 'int' || t === 'float') return 'number'
  if (t === 'bool') return 'bool'
  if (t === 'NoneType') return 'null'
  return t
})

const preview = computed(() => {
  if (props.node.preview) return props.node.preview
  return ''
})

const toggleExpanded = () => {
  expanded.value = !expanded.value
  if (!props.checkable) emit('select', props.node)
}

const handleContentClick = () => {
  if (props.checkable) {
    emit('check', { node: props.node, checked: !isChecked.value })
    return
  }
  emit('select', props.node)
}
</script>

<style scoped>
.tree-node {
  list-style: none;
  margin: 0;
  padding: 0;
}

.node-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: default;
  font-size: 14px;
  line-height: 1.6;
  transition: background 0.15s ease;
  user-select: none;
}

.node-row:hover {
  background: rgba(37, 99, 235, 0.06);
}

.node-row.selected {
  background: rgba(37, 99, 235, 0.12);
  color: #2563eb;
  font-weight: 600;
}

.arrow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  margin: -4px -2px -4px -4px;
  padding: 0;
  border: 0;
  border-radius: 5px;
  background: transparent;
  transition: transform 0.2s ease;
  flex-shrink: 0;
  color: #64748b;
  cursor: pointer;
}

.arrow:hover {
  background: rgba(37, 99, 235, 0.08);
}

.arrow:focus-visible {
  outline: 2px solid rgba(37, 99, 235, 0.35);
  outline-offset: 1px;
}

.arrow.expanded {
  transform: rotate(90deg);
}

.arrow-placeholder {
  width: 28px;
  flex-shrink: 0;
}

.node-content {
  display: flex;
  align-items: center;
  min-width: 0;
  flex: 1 1 auto;
  gap: 6px;
  cursor: pointer;
}

/* 复选框自带的右侧留白会把字段名推远，这里收掉 */
.node-check {
  flex-shrink: 0;
  height: auto;
  margin-right: -6px;
}

.node-label {
  color: #1e293b;
  font-weight: 500;
}

.node-row.selected .node-label {
  color: #2563eb;
}

.node-row.preview-active {
  background: #edf6f4;
  box-shadow: inset 3px 0 #5d9f98;
}

.node-row.preview-active .node-label {
  color: #3f7773;
}

.node-row.search-match {
  background: rgba(103, 194, 58, 0.1);
}

.node-row.search-active {
  background: rgba(103, 194, 58, 0.2);
  box-shadow: inset 3px 0 #67c23a;
}

.node-row.search-active .node-label {
  color: #389e0d;
}

.node-type {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: #f1f5f9;
  color: #64748b;
  font-weight: 500;
  flex-shrink: 0;
}

.node-preview {
  color: #94a3b8;
  font-size: 12px;
  font-family: Consolas, 'Courier New', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}

.children {
  padding-left: 20px;
  margin: 0;
}
</style>
