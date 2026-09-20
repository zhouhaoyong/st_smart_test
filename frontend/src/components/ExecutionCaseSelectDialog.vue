<template>
  <el-dialog
    :model-value="modelValue"
    title="选择用例"
    width="min(960px, calc(100vw - 48px))"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    class="execution-case-select-dialog"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="execution-case-select-content">
      <div class="execution-case-select-toolbar">
        <el-form :inline="true" class="execution-case-select-filter-form" @submit.prevent>
          <el-form-item label="名称" class="execution-case-select-filter-item execution-case-select-filter-item--keyword">
            <el-input
              v-model="keywordProxy"
              placeholder="搜索接口名称或用例名称"
              clearable
              :prefix-icon="Search"
            />
          </el-form-item>
          <el-form-item label="接口状态" class="execution-case-select-filter-item execution-case-select-filter-item--interface-status">
            <el-select v-model="interfaceStatusProxy" placeholder="全部" clearable @change="handleFilterChange">
              <el-option label="全部" value="" />
              <el-option label="待处理" value="pending" />
              <el-option label="已处理" value="done" />
            </el-select>
          </el-form-item>
          <el-form-item label="用例状态" class="execution-case-select-filter-item execution-case-select-filter-item--case-status">
            <el-select v-model="caseStatusProxy" placeholder="全部" clearable @change="handleFilterChange">
              <el-option label="全部" value="" />
              <el-option label="待确认" value="pending" />
              <el-option label="已确认" value="confirmed" />
            </el-select>
          </el-form-item>
        </el-form>
        <div class="execution-case-select-toolbar__actions">
          <el-button class="execution-case-select-toolbar__select-all" :disabled="treeLoading" @click="toggleAllNodes(!allVisibleCasesSelected)">
            {{ allVisibleCasesSelected ? '取消全选' : '全选' }}（{{ checkedCaseIds.length }}）
          </el-button>
        </div>
      </div>

      <div v-loading="treeLoading" class="execution-case-select-tree-wrap">
        <el-tree
          ref="caseTreeRef"
          :data="visibleFilteredTreeData"
          show-checkbox
          node-key="nodeKey"
          :props="treeProps"
          :default-expanded-keys="defaultExpandedKeys"
          :default-checked-keys="defaultCheckedKeys"
          :key="treeKey"
          class="execution-case-select-tree"
          @check="handleCheck"
        >
          <template #default="{ data }">
            <CollectionNodeLabel v-if="data.type === 'collection'" :node="data" />
            <span v-else-if="data.type === 'interface'" class="execution-case-select-interface-node">
              <el-tag :type="data.workflow_status === 'done' ? 'success' : 'warning'" size="small">
                {{ data.workflow_status_label || (data.workflow_status === 'done' ? '已处理' : '待处理') }}
              </el-tag>
              <button
                type="button"
                class="execution-case-select-detail-trigger execution-case-select-interface-detail"
                :title="`查看接口详情：${data.label || '未命名接口'}`"
                @click.stop="emit('view-interface', data)"
              >
                <span class="execution-case-select-interface-name">{{ data.label }}</span>
                <span class="execution-case-select-interface-url">{{ data.url }}</span>
              </button>
            </span>
            <span v-else-if="data.type === 'case'" class="execution-case-select-case-node">
              <el-tag :type="data.confirm_status === 'confirmed' ? 'success' : 'warning'" size="small">
                {{ data.confirm_status_label || (data.confirm_status === 'confirmed' ? '已确认' : '待确认') }}
              </el-tag>
              <el-tag :type="data.priority === 'high' ? 'danger' : data.priority === 'medium' ? 'warning' : 'info'" size="small">
                {{ data.priority === 'high' ? '高' : data.priority === 'medium' ? '中' : '低' }}
              </el-tag>
              <button
                type="button"
                class="execution-case-select-detail-trigger execution-case-select-case-detail"
                :title="`查看用例详情：${data.label || '未命名用例'}`"
                @click.stop="emit('view-case', data)"
              >
                <span class="execution-case-select-case-name">{{ data.label }}</span>
              </button>
            </span>
            <span v-else class="execution-case-select-case-node">{{ data.label }}</span>
          </template>
        </el-tree>
        <GlobalEmpty v-if="!treeLoading && !visibleFilteredTreeData.length" text="暂无可选用例" :image-size="64" />
      </div>

      <div class="execution-case-select-hint">
        <el-icon><InfoFilled /></el-icon>
        <span>无断言的用例统一使用 HTTP status_code 判断，2xx 为成功。</span>
      </div>
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :disabled="treeLoading || (!allowEmpty && checkedCaseIds.length === 0)" @click="confirmSelection">
        确定（{{ checkedCaseIds.length }}）
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { InfoFilled, Search } from '@element-plus/icons-vue'
import GlobalEmpty from '@/components/GlobalEmpty.vue'
import CollectionNodeLabel from '@/components/CollectionNodeLabel.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  treeData: { type: Array, default: () => [] },
  filteredTreeData: { type: Array, default: () => [] },
  searchKeyword: { type: String, default: '' },
  interfaceStatus: { type: String, default: '' },
  caseStatus: { type: String, default: '' },
  treeLoading: { type: Boolean, default: false },
  treeKey: { type: [Number, String], default: 0 },
  checkedCaseIds: { type: Array, default: () => [] },
  defaultCheckedKeys: { type: Array, default: () => [] },
  defaultExpandedKeys: { type: Array, default: () => [] },
  allowEmpty: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:modelValue',
  'update:searchKeyword',
  'update:interfaceStatus',
  'update:caseStatus',
  'filter',
  'check',
  'confirm',
  'view-interface',
  'view-case',
])

const caseTreeRef = ref(null)

// 选择器只展示包含可选用例的树枝，保留有后代用例的父级接口集以支持级联选择。
const pruneEmptyCaseBranches = (nodes = []) => {
  const result = []
  ;(Array.isArray(nodes) ? nodes : []).forEach(node => {
    const children = pruneEmptyCaseBranches(node?.children)
    const nodeKey = String(node?.nodeKey || node?.id || '')
    const hasSelectableCase = (node?.type === 'case' && nodeKey.startsWith('case_')) || children.length > 0
    if (!hasSelectableCase) return
    result.push({ ...node, children })
  })
  return result
}

const visibleTreeData = computed(() => pruneEmptyCaseBranches(props.treeData))
const visibleFilteredTreeData = computed(() => pruneEmptyCaseBranches(props.filteredTreeData))

const selectedCaseKeys = () => {
  const visibleCaseIds = new Set(collectCaseIds(visibleFilteredTreeData.value))
  return (props.checkedCaseIds || [])
    .map((id) => Number(id))
    .filter((id) => visibleCaseIds.has(id))
    .map((id) => `case_${id}`)
}

const syncVisibleCheckedKeys = async () => {
  await nextTick()
  if (!caseTreeRef.value) return
  caseTreeRef.value.setCheckedKeys(selectedCaseKeys(), false)
}

watch(
  [() => props.filteredTreeData, () => props.treeKey, () => props.checkedCaseIds],
  syncVisibleCheckedKeys,
  { flush: 'post' },
)
const treeProps = { label: 'label', children: 'children' }
const keywordProxy = computed({
  get: () => props.searchKeyword,
  set: value => {
    emit('update:searchKeyword', value)
    emit('filter')
  },
})
const interfaceStatusProxy = computed({
  get: () => props.interfaceStatus,
  set: value => emit('update:interfaceStatus', value || ''),
})
const caseStatusProxy = computed({
  get: () => props.caseStatus,
  set: value => emit('update:caseStatus', value || ''),
})
const handleFilterChange = () => emit('filter')

const collectNodeKeys = (nodes = []) => {
  const keys = []
  const walk = items => {
    items.forEach(item => {
      keys.push(item.nodeKey)
      if (item.children?.length) walk(item.children)
    })
  }
  walk(nodes)
  return keys
}

const collectCaseIds = (nodes = []) => {
  const ids = []
  const walk = items => {
    items.forEach(item => {
      const key = String(item?.nodeKey || item?.id || '')
      if (item?.type === 'case' && key.startsWith('case_')) {
        const id = parseInt(key.replace('case_', ''), 10)
        if (Number.isInteger(id) && id > 0) ids.push(id)
      }
      if (Array.isArray(item?.children) && item.children.length) walk(item.children)
    })
  }
  walk(Array.isArray(nodes) ? nodes : [])
  return ids
}

const allVisibleCasesSelected = computed(() => {
  const visibleCaseIds = collectCaseIds(visibleFilteredTreeData.value)
  if (!visibleCaseIds.length) return false
  const selectedIds = new Set((props.checkedCaseIds || []).map(id => Number(id)))
  return visibleCaseIds.every(id => selectedIds.has(id))
})

const readVisibleCheckedCaseIds = () => {
  const checked = caseTreeRef.value?.getCheckedKeys() || []
  const halfChecked = caseTreeRef.value?.getHalfCheckedKeys() || []
  return [...checked, ...halfChecked]
    .filter(key => String(key).startsWith('case_'))
    .map(key => parseInt(String(key).replace('case_', ''), 10))
    .filter(id => Number.isInteger(id) && id > 0)
}

const readCheckedCaseIds = () => {
  return mergeVisibleSelection(readVisibleCheckedCaseIds())
}

const handleCheck = () => emit('check', readCheckedCaseIds())

const mergeVisibleSelection = (visibleSelectedCaseIds = []) => {
  const visibleCaseIds = new Set(collectCaseIds(visibleFilteredTreeData.value))
  const availableCaseIds = new Set(collectCaseIds(visibleTreeData.value))
  const preservedCaseIds = (props.checkedCaseIds || [])
    .map(id => Number(id))
    .filter(id => availableCaseIds.has(id) && !visibleCaseIds.has(id))
  return [...new Set([...preservedCaseIds, ...visibleSelectedCaseIds])]
}

const toggleAllNodes = checked => {
  const keys = checked ? collectNodeKeys(visibleFilteredTreeData.value) : []
  caseTreeRef.value?.setCheckedKeys(keys, false)
  emit('check', mergeVisibleSelection(checked ? collectCaseIds(visibleFilteredTreeData.value) : []))
}

const confirmSelection = () => {
  if (!props.allowEmpty && !(props.checkedCaseIds || []).length) return
  emit('confirm', Array.isArray(props.checkedCaseIds) ? [...props.checkedCaseIds] : [])
}
</script>

<style scoped>
.execution-case-select-content {
  display: flex;
  flex-direction: column;
  min-height: 0;
  gap: 12px;
}

.execution-case-select-filter-form {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 8px 12px;
  margin: 0;
}

.execution-case-select-filter-item {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  height: 32px;
  min-height: 32px;
  margin: 0;
}

.execution-case-select-filter-item :deep(.el-form-item__label) {
  padding-right: 8px;
  line-height: 32px;
  white-space: nowrap;
}

.execution-case-select-filter-item :deep(.el-form-item__content) {
  display: flex;
  align-items: center;
  height: 32px;
  min-height: 32px;
}

.execution-case-select-filter-item--keyword :deep(.el-form-item__content) { width: 260px; min-width: 260px; }
.execution-case-select-filter-item--interface-status :deep(.el-form-item__content),
.execution-case-select-filter-item--case-status :deep(.el-form-item__content) { width: 120px; min-width: 120px; }
.execution-case-select-filter-item :deep(.el-input),
.execution-case-select-filter-item :deep(.el-select) { width: 100%; }

.execution-case-select-toolbar {
  display: flex;
  align-items: center;
  min-height: 28px;
  gap: 12px;
}

.execution-case-select-toolbar__actions { display: inline-flex; gap: 8px; }
.execution-case-select-toolbar__select-all { height: 32px; min-height: 32px; }
.execution-case-select-tree-wrap {
  position: relative;
  height: min(420px, calc(100vh - 280px));
  min-height: 220px;
  overflow: auto;
  padding: 6px 8px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
}

.execution-case-select-tree { min-width: max-content; }
.execution-case-select-tree :deep(.el-tree-node__content) { min-height: 36px; }
.execution-case-select-tree :deep(.el-tree-node__label) { min-width: 0; }

.execution-case-select-interface-node,
.execution-case-select-case-node {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  gap: 6px;
  font-size: 13px;
}

.execution-case-select-interface-name,
.execution-case-select-interface-url,
.execution-case-select-case-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.execution-case-select-interface-name { font-weight: 600; }
.execution-case-select-interface-url { color: var(--el-text-color-secondary); }
.execution-case-select-detail-trigger {
  display: inline-flex;
  align-items: flex-start;
  flex-direction: column;
  min-width: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  text-align: left;
}
.execution-case-select-detail-trigger:hover .execution-case-select-interface-name,
.execution-case-select-detail-trigger:hover .execution-case-select-case-name { text-decoration: underline; }
.execution-case-select-case-detail { color: var(--el-color-primary); }

.execution-case-select-hint {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.8;
}

.execution-case-select-tree-wrap > :deep(.global-empty) {
  min-height: 260px;
}

@media (max-width: 768px) {
  .execution-case-select-toolbar { flex-wrap: wrap; }
}

@media (max-width: 960px) {
  .execution-case-select-toolbar { flex-wrap: wrap; }
  .execution-case-select-filter-form { flex-wrap: wrap; }
}
</style>
