<template>
  <div class="scope-panel">
    <div v-if="!isFixedScope" class="scope-filter-frame">
      <el-form :inline="true" class="scope-filter-form" @submit.prevent="search">
        <el-form-item label="接口集" class="scope-collection-filter-item">
          <div class="scope-collection-control">
            <el-cascader
              v-model="filters.collection_ids"
              :options="collectionTree"
              :props="collectionCascaderProps"
              filterable
              clearable
              collapse-tags
              :max-collapse-tags="1"
              :show-all-levels="false"
              placeholder="全部接口集"
              class="scope-collection-select"
              popper-class="scope-collection-cascader-popper"
            >
              <template #default="{ data }">
                <CollectionNodeLabel :node="data" />
              </template>
            </el-cascader>
          </div>
        </el-form-item>
        <el-form-item label="名称或 URL" class="scope-filter-keyword">
          <el-input v-model="filters.keyword" clearable placeholder="名称或 URL" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.workflow_status" clearable placeholder="全部" style="width: 96px">
            <el-option label="待处理" value="pending" />
            <el-option label="已处理" value="done" />
          </el-select>
        </el-form-item>
        <el-form-item class="scope-filter-actions">
          <el-button type="primary" @click="search">查询</el-button>
          <el-button
            type="primary"
            plain
            :loading="selectingAll"
            :title="allFilteredSelected ? '取消全选当前筛选结果' : '全选当前筛选结果'"
            @click="selectAllFiltered"
          >{{ allFilteredSelected ? '取消全选' : '全选' }}</el-button>
        </el-form-item>
      </el-form>
    </div>
    <div v-else class="scope-fixed-notice">
      本次仅针对当前选中的接口生成用例：{{ fixedInterfaces[0]?.name || fixedInterfaces[0]?.url || '当前接口' }}
    </div>

    <div class="scope-table-scroll">
      <el-table
        ref="tableRef"
        v-loading="loading"
        :data="items"
        row-key="id"
        :max-height="scopeTableMaxHeight"
        class="scope-table"
        @selection-change="handleSelectionChange"
      >
        <template #empty><GlobalEmpty text="暂无数据" /></template>
        <el-table-column type="selection" width="48" reserve-selection :selectable="isRowSelectable" />
        <el-table-column label="接口名称/URL" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="scope-interface-name-url-cell" :title="[row.name || '-', row.url || '-'].join('\n')">
              <el-link class="scope-interface-name" type="primary" underline="never" @click.stop="emit('view-interface', row)">{{ row.name || '-' }}</el-link>
              <span class="scope-interface-url">{{ row.url || '-' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="用例数" width="78" align="center">
          <template #default="{ row }">
            <CaseCountStatusBadge :count="row.test_case_count" :pending-count="row.pending_test_case_count" />
          </template>
        </el-table-column>
        <el-table-column prop="method" label="方法" width="84" />
        <el-table-column prop="collection_name" label="接口集" min-width="130" show-overflow-tooltip />
        <el-table-column label="服务标识" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.service_key || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.workflow_status === 'done' ? 'success' : 'warning'" size="small">
              {{ row.workflow_status_label || (row.workflow_status === 'done' ? '已处理' : '待处理') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="待处理原因" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.workflow_status === 'pending' ? (row.pending_reason_label || '-') : '-' }}
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="scope-pagination-bar">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, sizes, prev, pager, next"
        :page-sizes="[10, 50, 100]"
        class="scope-pagination"
        @current-change="loadPage"
        @size-change="handlePageSizeChange"
      />
    </div>

    <div v-if="showFooter" class="scope-footer">
      <div>
        <el-button @click="emit('cancel')">取消</el-button>
        <el-button type="primary" :disabled="selectedIds.size === 0" @click="confirmSelection">
          下一步（{{ selectedIds.size }}）
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import GlobalEmpty from '@/components/GlobalEmpty.vue'
import CaseCountStatusBadge from '@/components/CaseCountStatusBadge.vue'
import CollectionNodeLabel from '@/components/CollectionNodeLabel.vue'
import { getInterfaces, getInterfaceSelectionIds } from '@/api/interfaces'

const props = defineProps({
  projectId: { type: [Number, String], default: null },
  collectionTree: { type: Array, default: () => [] },
  interfaceIds: { type: Array, default: () => [] },
  fixedInterfaceIds: { type: Array, default: () => [] },
  fixedInterfaces: { type: Array, default: () => [] },
  showFooter: { type: Boolean, default: true },
})
const emit = defineEmits(['confirm', 'cancel', 'view-interface'])

const tableRef = ref(null)
const loading = ref(false)
const selectingAll = ref(false)
const allFilteredSelected = ref(false)
const syncingSelection = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const normalizeIds = ids => (ids || []).map(Number).filter(id => Number.isInteger(id) && id > 0)
const fixedIds = computed(() => new Set(normalizeIds(props.fixedInterfaceIds)))
const isFixedScope = computed(() => fixedIds.value.size > 0)
const selectedIds = ref(new Set(
  normalizeIds(isFixedScope.value ? props.fixedInterfaceIds : props.interfaceIds),
))
const filters = reactive({
  collection_ids: [],
  keyword: '',
  workflow_status: '',
})
const collectionCascaderProps = {
  value: 'id',
  label: 'name',
  children: 'children',
  multiple: true,
  checkStrictly: true,
  emitPath: false,
}
const scopeTableMaxHeight = 384
const pageIds = computed(() => items.value.map(item => Number(item.id)).filter(id => id > 0))
function isRowSelectable(row) {
  return !isFixedScope.value || fixedIds.value.has(Number(row?.id))
}

function requestParams() {
  const params = {
    keyword: filters.keyword.trim() || undefined,
    workflow_status: filters.workflow_status || undefined,
    collection_ids: filters.collection_ids.length ? filters.collection_ids : undefined,
  }
  return params
}

async function loadPage() {
  if (isFixedScope.value) {
    items.value = (props.fixedInterfaces || []).filter(item => fixedIds.value.has(Number(item?.id)))
    total.value = items.value.length
    await nextTick()
    syncPageSelection()
    return
  }
  if (!props.projectId) return
  loading.value = true
  try {
    const result = await getInterfaces(null, props.projectId, page.value, pageSize.value, requestParams())
    items.value = Array.isArray(result?.items) ? result.items : []
    total.value = Number(result?.total || 0)
    await nextTick()
    syncPageSelection()
  } finally {
    loading.value = false
  }
}

function syncPageSelection() {
  syncingSelection.value = true
  try {
    const selected = selectedIds.value
    tableRef.value?.clearSelection()
    items.value.forEach(item => {
      if (selected.has(Number(item.id))) tableRef.value?.toggleRowSelection(item, true)
    })
  } finally {
    syncingSelection.value = false
  }
}

function handleSelectionChange(rows) {
  const currentPageIds = new Set(pageIds.value)
  const next = new Set(selectedIds.value)
  currentPageIds.forEach(id => next.delete(id))
  rows.forEach(row => next.add(Number(row.id)))
  selectedIds.value = next
  if (!syncingSelection.value) allFilteredSelected.value = false
}

async function selectAllFiltered() {
  if (isFixedScope.value || selectingAll.value) return
  selectingAll.value = true
  try {
    const result = await getInterfaceSelectionIds(props.projectId, requestParams())
    const filteredIds = (result?.ids || []).map(Number).filter(id => id > 0)
    const shouldClear = filteredIds.length > 0
      && filteredIds.every(id => selectedIds.value.has(id))
    const next = new Set(selectedIds.value)
    filteredIds.forEach(id => {
      if (shouldClear) next.delete(id)
      else next.add(id)
    })
    selectedIds.value = next
    await nextTick()
    syncPageSelection()
    allFilteredSelected.value = filteredIds.length > 0 && !shouldClear
  } finally {
    selectingAll.value = false
  }
}

function search() {
  if (isFixedScope.value) return
  selectedIds.value = new Set()
  allFilteredSelected.value = false
  page.value = 1
  loadPage()
}

function handlePageSizeChange(size) {
  if (isFixedScope.value) return
  pageSize.value = size
  page.value = 1
  loadPage()
}

function confirmSelection() {
  if (!selectedIds.value.size) return
  emit('confirm', [...selectedIds.value])
}

function resetState() {
  items.value = []
  total.value = 0
  page.value = 1
  selectedIds.value = new Set(
    normalizeIds(isFixedScope.value ? props.fixedInterfaceIds : props.interfaceIds),
  )
  allFilteredSelected.value = false
}

watch(() => [props.interfaceIds, props.fixedInterfaceIds], () => {
  selectedIds.value = new Set(
    normalizeIds(isFixedScope.value ? props.fixedInterfaceIds : props.interfaceIds),
  )
  allFilteredSelected.value = false
  nextTick(syncPageSelection)
  if (isFixedScope.value) loadPage()
}, { deep: true })

watch(() => props.fixedInterfaces, () => {
  if (isFixedScope.value) loadPage()
}, { deep: true })

onMounted(loadPage)

defineExpose({
  loadPage,
  resetState,
  confirmSelection,
  selectedIds,
})
</script>

<style scoped>
.scope-panel { display: flex; flex: 1 1 auto; flex-direction: column; box-sizing: border-box; width: 100%; height: 100%; min-width: 0; min-height: 0; overflow: hidden; }
.scope-filter-frame { box-sizing: border-box; display: flex; align-items: center; width: 100%; min-width: 0; padding: 12px 16px; margin-bottom: 12px; background: #f8fafc; border: 1px solid #edf1f6; border-radius: 10px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.02); }
.scope-fixed-notice { box-sizing: border-box; display: flex; align-items: center; width: 100%; min-width: 0; min-height: 56px; padding: 12px 16px; margin-bottom: 12px; color: #475569; font-size: 13px; background: #f8fafc; border: 1px solid #edf1f6; border-radius: 10px; }
.scope-filter-form { display: flex; flex: 1 1 auto; flex-wrap: nowrap; align-items: center; gap: 0 12px; width: 100%; min-width: 0; margin: 0; }
.scope-filter-form :deep(.el-form-item) { flex: 0 0 auto; height: 32px !important; min-height: 32px !important; max-height: 32px !important; margin: 0; }
.scope-filter-form :deep(.el-form-item__content) { display: flex; align-items: center; height: 32px !important; min-height: 32px !important; max-height: 32px !important; }
.scope-filter-form :deep(.el-form-item__label) { padding-right: 8px; white-space: nowrap; }
.scope-filter-keyword { flex: 0 0 auto !important; }
.scope-filter-keyword :deep(.el-form-item__content) { flex: 1; min-width: 0; }
.scope-filter-keyword :deep(.el-input) { width: 180px; }
.scope-filter-actions { flex: 0 0 auto !important; white-space: nowrap; }
.scope-collection-filter-item { flex: 0 0 auto !important; height: 32px !important; min-height: 32px !important; max-height: 32px !important; }
.scope-collection-filter-item :deep(.el-form-item__content) { display: flex; align-items: center; flex: 0 0 220px !important; width: 220px !important; min-width: 220px; max-width: 220px; height: 32px !important; min-height: 32px; max-height: 32px; overflow: visible !important; }
.scope-collection-control { position: relative; flex: 0 0 220px; width: 220px; min-width: 220px; max-width: 220px; height: 32px !important; min-height: 32px !important; max-height: 32px !important; overflow: visible !important; }
:global(.scope-collection-select) { position: relative; display: block; width: 220px !important; min-width: 220px; max-width: 220px; height: 32px !important; min-height: 32px !important; max-height: 32px !important; overflow: hidden !important; box-sizing: border-box; }
:global(.scope-collection-select .el-input),
:global(.scope-collection-select .el-input__wrapper) { position: relative; display: flex; align-items: center; width: 220px !important; min-width: 220px !important; max-width: 220px !important; height: 32px !important; min-height: 32px !important; max-height: 32px !important; overflow: hidden !important; box-sizing: border-box; }
:global(.scope-collection-select .el-input__inner) { height: 30px !important; min-height: 30px !important; max-height: 30px !important; line-height: 30px !important; }
:global(.scope-collection-select .el-input__suffix) { position: absolute !important; top: 50% !important; right: 5px !important; bottom: auto !important; display: flex !important; align-items: center !important; height: 20px !important; min-height: 20px !important; max-height: 20px !important; transform: translateY(-50%) !important; }
:global(.scope-collection-select .el-input__suffix-inner) { display: inline-flex !important; align-items: center !important; justify-content: center !important; height: 100% !important; min-height: 0 !important; max-height: none !important; line-height: 1 !important; }
:global(.scope-collection-select .el-input__suffix .el-icon) { display: inline-flex !important; align-items: center !important; justify-content: center !important; height: 20px !important; line-height: 1 !important; margin: 0 !important; }
:global(.scope-collection-select .el-input__clear) { position: static !important; top: auto !important; right: auto !important; margin: 0 !important; line-height: 1 !important; transform: none !important; }
:global(.scope-collection-select .el-cascader__clear-icon),
:global(.scope-collection-select .el-cascader__close-icon) { position: static !important; top: auto !important; right: auto !important; margin: 0 !important; line-height: 1 !important; transform: none !important; }
:global(.scope-collection-select .el-cascader__tags) { position: absolute !important; top: 50% !important; right: 22px; bottom: auto !important; left: 11px !important; display: flex !important; box-sizing: border-box; flex-wrap: nowrap !important; align-items: center !important; height: 24px !important; min-height: 24px !important; max-height: 24px !important; padding: 0; gap: 4px; overflow: hidden; white-space: nowrap; transform: translateY(-50%) !important; }
:global(.scope-collection-select .el-cascader__tags .el-tag) { flex: 0 0 auto; height: 24px !important; max-width: 100%; margin: 0 !important; overflow: hidden; line-height: 22px !important; text-overflow: ellipsis; white-space: nowrap; }
:global(.scope-collection-select .el-cascader__tags .el-tag__close) { flex: 0 0 auto; }
.scope-interface-name-url-cell { min-width: 0; max-width: 100%; overflow: hidden; line-height: 1.45; }
.scope-interface-name-url-cell :deep(.scope-interface-name),
.scope-interface-name-url-cell .scope-interface-url { display: block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.scope-interface-name-url-cell :deep(.scope-interface-name) { font-weight: 500; }
.scope-interface-url { margin-top: 2px; color: #909399; font-size: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.scope-table-scroll { flex: 1 1 auto; width: 100%; height: auto; min-width: 0; min-height: 0; overflow-x: auto; overflow-y: hidden; scrollbar-width: thin; scrollbar-color: #aeb8c4 #f7f9fc; }
.scope-table { width: 100%; min-width: 100%; }
.scope-table :deep(.el-table__inner-wrapper::before) { display: none; }
.scope-table :deep(.el-table__empty-block) { height: 100%; min-height: 0; }
.scope-table :deep(.global-empty) { display: flex; align-items: center; justify-content: center; height: 100%; }
.scope-table :deep(.global-empty .el-empty) { min-height: 0; padding: 24px 0; }
.scope-table :deep(.el-table__header .cell), .scope-table :deep(.el-table__body .cell) { white-space: nowrap; }
.scope-table :deep(.el-table__body .cell) { overflow: hidden; text-overflow: ellipsis; }
.scope-pagination-bar { display: flex; align-items: center; justify-content: flex-end; gap: 16px; flex: 0 0 auto; box-sizing: border-box; min-width: 0; margin-top: 14px; }
.scope-pagination { display: flex; justify-content: flex-end; min-width: 0; }
.scope-footer { display: flex; flex: 0 0 auto; align-items: center; justify-content: flex-end; gap: 16px; box-sizing: border-box; min-height: 0; margin-top: 10px; padding-top: 12px; border-top: 1px solid var(--el-border-color-lighter); white-space: nowrap; }
:global(.scope-collection-cascader-popper) { max-width: min(720px, calc(100vw - 48px)); }
:global(.scope-collection-cascader-popper .el-cascader-panel) { max-width: min(720px, calc(100vw - 48px)); overflow-x: auto; }
:global(.scope-collection-cascader-popper .el-cascader-menu) { min-width: 180px; max-height: 320px; }
:global(.scope-collection-cascader-popper .el-cascader-menu__wrap) { max-height: 320px; }
:global(.scope-collection-cascader-popper .el-cascader-node) { white-space: nowrap; }
@media (max-width: 1199px) {
  .scope-collection-filter-item :deep(.el-form-item__content),
  .scope-collection-control,
  :global(.scope-collection-select),
  :global(.scope-collection-select .el-input),
  :global(.scope-collection-select .el-input__wrapper) { width: 220px !important; min-width: 220px; max-width: 220px; }
  .scope-footer { align-items: flex-end; flex-direction: column; }
  .scope-pagination-bar { align-items: flex-end; flex-direction: column; }
}
</style>
