<template>
  <el-dialog v-model="visible" :title="config.title" width="980px" destroy-on-close class="asset-list-dialog">
    <el-form class="filter-form" :inline="true" @submit.prevent>
      <el-form-item :label="config.queryLabel">
        <el-input v-model="filters[config.queryField]" clearable :placeholder="config.queryPlaceholder" style="width: 180px" @keyup.enter="handleQuery" />
      </el-form-item>
      <el-form-item v-if="assetType === 'version'" label="系统">
        <el-select v-model="filters.system_id" clearable placeholder="全部系统" style="width: 150px" @change="handleSystemChange">
          <el-option v-for="item in systems" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="config.statuses" :label="config.statusLabel || '状态'">
        <el-select v-model="filters[config.statusField || 'status']" clearable placeholder="全部状态" style="width: 130px">
          <el-option v-for="item in config.statuses" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="创建时间"><el-date-picker v-model="filters.created_dates" type="daterange" value-format="YYYY-MM-DD" format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 240px" /></el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleQuery">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="items" height="390" row-key="id" class="asset-table">
      <template #empty><el-empty v-if="!loading" class="asset-empty" :description="`暂无${config.name}`" :image-size="72" /></template>
      <el-table-column v-for="column in config.columns" :key="column.prop" :prop="column.prop" :label="column.label" :min-width="column.minWidth" :width="column.width" show-overflow-tooltip>
        <template #default="{ row }">{{ formatCell(row, column) }}</template>
      </el-table-column>
    </el-table>

    <div class="dialog-pagination">
      <el-pagination
        v-model:current-page="filters.page"
        v-model:page-size="filters.page_size"
        :total="total"
        :page-sizes="[10, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="loadAssets"
        @size-change="handleSizeChange"
      />
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, inject, reactive, ref, watch } from 'vue'
import { getWorkbenchProjectDashboardAssets } from '@/api/testWorkbench'
import { formatBeijingTime } from '@/utils/beijingTime'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  projectId: { type: Number, required: true },
  assetType: { type: String, default: 'system' },
  initialStatus: { type: String, default: '' },
  initialSystemId: { type: Number, default: undefined },
  initialVersionId: { type: Number, default: undefined },
})
const emit = defineEmits(['update:modelValue'])
const workbenchContext = inject('workbenchContext', {})

const configs = {
  system: {
    title: '系统明细', name: '系统',
    queryLabel: '系统名称', queryField: 'name', queryPlaceholder: '请输入系统名称',
    columns: [
      { prop: 'name', label: '系统名称', width: 220 },
      { prop: 'type', label: '系统类型', width: 160 },
      { prop: 'description', label: '描述', minWidth: 240 },
      { prop: 'created_at', label: '创建时间', width: 200, format: 'time' },
    ],
  },
  version: {
    title: '版本明细', name: '版本',
    queryLabel: '版本号', queryField: 'version_no', queryPlaceholder: '请输入版本号',
    columns: [
      { prop: 'version_no', label: '版本号', width: 170 },
      { prop: 'system_name', label: '所属系统', width: 150 },
      { prop: 'current_stage', label: '当前阶段', width: 130 },
      { prop: 'plan_release_date', label: '计划发布日期', width: 140 },
      { prop: 'actual_release_date', label: '实际发布日期', width: 140 },
      { prop: 'description', label: '描述', minWidth: 220 },
      { prop: 'created_at', label: '创建时间', width: 200, format: 'time' },
    ],
  },
  requirement: {
    title: '需求明细', name: '需求', statuses: [{ label: '待确认', value: 'draft' }, { label: '已确认', value: 'confirmed' }],
    queryLabel: '需求标题', queryField: 'title', queryPlaceholder: '请输入需求标题',
    columns: [
      { prop: 'req_no', label: '需求编号', width: 150 },
      { prop: 'title', label: '需求标题', minWidth: 260 },
      { prop: 'system_name', label: '所属系统', width: 140 },
      { prop: 'version_no', label: '所属版本', width: 140 },
      { prop: 'confirm_status', label: '状态', width: 120, format: 'status' },
      { prop: 'created_at', label: '创建时间', width: 200, format: 'time' },
    ],
  },
  merged_requirement: {
    title: '合并需求明细', name: '合并需求', statusLabel: '合并状态', statusField: 'merge_status', statuses: [{ label: '已合并', value: 'merged' }, { label: '待重新合并', value: 'stale' }],
    queryLabel: '需求标题', queryField: 'title', queryPlaceholder: '请输入需求标题',
    columns: [
      { prop: 'req_no', label: '需求编号', width: 150 },
      { prop: 'title', label: '需求标题', minWidth: 260 },
      { prop: 'system_name', label: '所属系统', width: 140 },
      { prop: 'version_no', label: '所属版本', width: 140 },
      { prop: 'merge_status', label: '合并状态', width: 120, format: 'status' },
      { prop: 'created_at', label: '创建时间', width: 200, format: 'time' },
    ],
  },
  test_case: {
    title: '测试用例明细', name: '测试用例', statuses: [{ label: '待执行', value: 'not_executed' }, { label: '通过', value: 'passed' }, { label: '失败', value: 'failed' }, { label: '阻塞', value: 'blocked' }, { label: '未测', value: 'not_tested' }],
    queryLabel: '用例标题', queryField: 'title', queryPlaceholder: '请输入用例标题',
    columns: [
      { prop: 'case_no', label: '用例编号', width: 150 },
      { prop: 'title', label: '用例标题', minWidth: 240 },
      { prop: 'system_name', label: '所属系统', width: 140 },
      { prop: 'version_no', label: '所属版本', width: 140 },
      { prop: 'execution_status', label: '执行状态', width: 120, format: 'status' },
    ],
  },
  bug: {
    title: 'Bug 明细', name: 'Bug', statuses: [{ label: '未关闭', value: 'unclosed' }, { label: '待解决', value: 'pending' }, { label: '已解决', value: 'resolved' }, { label: '已验证关闭', value: 'closed' }],
    queryLabel: 'Bug 标题', queryField: 'title', queryPlaceholder: '请输入 Bug 标题',
    columns: [
      { prop: 'title', label: 'Bug 标题', minWidth: 250 },
      { prop: 'system_name', label: '所属系统', width: 140 },
      { prop: 'version_no', label: '所属版本', width: 140 },
      { prop: 'severity', label: '严重级别', width: 120 },
      { prop: 'status', label: '状态', width: 120, format: 'status' },
    ],
  },
  legacy_item: {
    title: '遗留项明细', name: '遗留项', statuses: [{ label: '待处理', value: 'pending' }, { label: '已处理', value: 'done' }],
    queryLabel: '遗留项标题', queryField: 'title', queryPlaceholder: '请输入遗留项标题',
    columns: [
      { prop: 'title', label: '遗留项标题', minWidth: 250 },
      { prop: 'system_name', label: '所属系统', width: 140 },
      { prop: 'version_no', label: '所属版本', width: 140 },
      { prop: 'type', label: '类型', width: 120 },
      { prop: 'status', label: '状态', width: 120, format: 'status' },
    ],
  },
}

const visible = computed({ get: () => props.modelValue, set: (value) => emit('update:modelValue', value) })
const config = computed(() => configs[props.assetType] || configs.system)
const filters = reactive({ name: '', version_no: '', title: '', system_id: undefined, version_id: undefined, status: '', merge_status: '', created_dates: [], page: 1, page_size: 10 })
const systems = ref([])
const versions = ref([])
const items = ref([])
const total = ref(0)
const loading = ref(false)
let requestNo = 0
const filteredVersions = computed(() => (filters.system_id ? versions.value.filter((item) => item.system_id === filters.system_id) : versions.value))

const formatCell = (row, column) => {
  const value = row[column.prop]
  if (!value) return '—'
  if (column.format === 'time') return formatBeijingTime(value) || '—'
  if (column.format === 'status') return config.value.statuses?.find((item) => item.value === value)?.label || value
  return value
}

const loadAssets = async () => {
  if (!props.projectId) return
  const currentRequestNo = ++requestNo
  loading.value = true
  try {
    const { created_dates, ...queryFilters } = filters
    const [created_from, created_to] = created_dates || []
    const result = await getWorkbenchProjectDashboardAssets(props.projectId, {
      ...queryFilters,
      asset_type: props.assetType,
      created_from,
      created_to,
      ...(workbenchContext.scope?.value || {}),
    })
    if (currentRequestNo !== requestNo) return
    items.value = result?.items || []
    total.value = result?.total || 0
    systems.value = result?.systems || []
    versions.value = result?.versions || []
  } finally {
    if (currentRequestNo === requestNo) loading.value = false
  }
}

const handleQuery = () => { filters.page = 1; loadAssets() }
const handleSizeChange = () => { filters.page = 1; loadAssets() }
const handleSystemChange = () => {
  if (filters.version_id && !filteredVersions.value.some((item) => item.id === filters.version_id)) filters.version_id = undefined
}
const resetFilters = (shouldLoad = true) => {
  Object.assign(filters, { name: '', version_no: '', title: '', system_id: undefined, version_id: undefined, status: '', merge_status: '', created_dates: [], page: 1, page_size: 10 })
  if (shouldLoad) loadAssets()
}

watch([visible, () => props.assetType], ([isVisible]) => {
  if (isVisible) {
    resetFilters(false)
    filters.system_id = props.initialSystemId
    filters.version_id = props.initialVersionId
    filters.status = props.initialStatus
    loadAssets()
  }
  else requestNo += 1
})
</script>

<style scoped>
.filter-form { display: flex; flex-wrap: wrap; align-items: center; margin-bottom: 2px; }
.asset-table { margin-top: 2px; }
.asset-table :deep(.el-table__header .cell), .asset-table :deep(.el-table__body .cell) { white-space: nowrap; }
.asset-table :deep(.el-table__body .cell) { overflow: hidden; text-overflow: ellipsis; }
.asset-list-dialog :deep(.el-dialog__body) { padding-top: 12px; }
.asset-empty { padding: 0; }
.asset-empty :deep(.el-empty__image) { margin-bottom: 14px; }
.asset-empty :deep(.el-empty__description) { margin-top: 0; color: #909399; font-size: 14px; line-height: 20px; }
.dialog-pagination { display: flex; justify-content: flex-end; padding-top: 14px; }
</style>
