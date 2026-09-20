<template>
  <section class="workbench-list-section">
    <div class="requirement-page">
        <div class="list-toolbar">
          <el-form class="toolbar-form" :inline="true" :model="filters" @submit.prevent>
            <el-form-item label="需求标题"><el-input v-model="filters.title" clearable placeholder="请输入需求标题" style="width: 150px" @keyup.enter="query" /></el-form-item>
            <el-form-item label="状态"><el-select v-model="filters.status" clearable placeholder="全部状态" style="width: 110px"><el-option v-for="status in statuses" :key="status.value" :label="status.label" :value="status.value" /></el-select></el-form-item>
            <el-form-item label="创建时间"><el-date-picker v-model="filters.created_dates" type="daterange" value-format="YYYY-MM-DD" format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 210px" /></el-form-item>
            <el-form-item class="toolbar-button-item">
              <div class="toolbar-buttons">
                <el-button @click="query">查询</el-button>
                <el-button @click="reset">重置</el-button>
                <el-button :disabled="!confirmableSelection" @click="batchConfirm">{{ withCount('批量确认', selectedRows.length) }}</el-button>
                <el-button :disabled="!mergeableSelection" @click="openMerge">{{ withCount('AI 合并', selectedRows.length) }}</el-button>
                <el-button :disabled="!selectedRows.length" type="danger" plain @click="batchRemove">{{ withCount('批量删除', selectedRows.length) }}</el-button>
                <el-button type="danger" plain @click="removeAll">{{ withCount('全部删除', total) }}</el-button>
                <el-button v-if="!isCompleted" type="primary" @click="openCreate">新建需求</el-button>
              </div>
            </el-form-item>
          </el-form>
        </div>
        <div class="table-wrap">
          <el-table v-loading="loading" :data="items" width="100%" height="100%" row-key="id" @selection-change="onSelectionChange">
            <template #empty><el-empty v-if="!loading" class="asset-empty" :description="isCompleted ? '暂无补全需求' : '暂无原始需求'" :image-size="72" /></template>
            <el-table-column type="selection" width="46" />
            <el-table-column prop="title" label="需求标题" min-width="180" show-overflow-tooltip>
              <template #default="{ row }"><el-link type="primary" underline="never" @click.stop="openEdit(row)">{{ row.title }}</el-link></template>
            </el-table-column>
            <el-table-column v-if="isCompleted" prop="source_requirement_title" label="来源原始需求" min-width="180" show-overflow-tooltip />
            <el-table-column prop="system_name" label="所属系统" min-width="110" show-overflow-tooltip />
            <el-table-column prop="version_no" label="所属版本" min-width="90" show-overflow-tooltip />
            <el-table-column label="状态" min-width="110"><template #default="{ row }"><div class="status-cell"><el-tag :type="statusType(row.confirm_status)" effect="light" size="small">{{ statusLabel(row.confirm_status) }}</el-tag><span v-if="isCompleted && row.is_stale" class="status-stale">来源已更新</span></div></template></el-table-column>
            <el-table-column prop="created_at" label="创建时间" min-width="180"><template #default="{ row }">{{ formatTime(row.created_at) }}</template></el-table-column>
            <el-table-column prop="creator_name" label="创建人" min-width="90" show-overflow-tooltip><template #default="{ row }">{{ row.creator_name || '—' }}</template></el-table-column>
            <el-table-column label="操作" width="180" fixed="right" align="center"><template #default="{ row }"><div class="table-actions"><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-button v-if="!isCompleted" link type="primary" @click="openAi(row)">AI 补全</el-button><el-button link type="danger" @click="remove(row)">删除</el-button></div></template></el-table-column>
          </el-table>
        </div>
        <div class="list-pagination"><el-pagination v-model:current-page="filters.page" v-model:page-size="filters.page_size" :total="total" :page-sizes="[10, 50, 100]" layout="total, sizes, prev, pager, next" @current-change="load" @size-change="onSizeChange" /></div>
    </div>
    <RequirementFormDialog v-model="formVisible" :project-id="projectId" :item="editing" @saved="onSaved" />
    <RequirementRefinementDrawer v-if="!isCompleted" v-model="aiVisible" :requirement="activeDetail" @previewed="onAiPreviewed" />
    <RequirementPreviewDrawer v-model="previewVisible" :detail="activeDetail" :requirement-type="requirementType" :start-editing="startPreviewEditing" @confirmed="onConfirmed" @saved="onSavedDetail" @re-complete="onReComplete" />
    <!-- AI 合并会话：预览保存前不会创建 AI 合并需求记录。 -->
    <RequirementRefinementDrawer v-model="mergeAiVisible" title="AI 合并需求（对话式）" :requirement="null" :api="mergedAiApi" :scope="mergeScope" @previewed="onMergePreviewed" />
  </section>
</template>

<script setup>
import { computed, inject, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  batchDeleteWorkbenchRequirements,
  batchDeleteWorkbenchCompletedRequirements,
  batchConfirmWorkbenchRequirements,
  batchConfirmWorkbenchCompletedRequirements,
  deleteWorkbenchCompletedRequirement,
  deleteWorkbenchRequirement,
  getWorkbenchCompletedRequirementDetail,
  getWorkbenchProjectDashboardAssets,
  getWorkbenchRequirementDetail,
  getWorkbenchRequirements,
  askWorkbenchMergeAiStream,
  compareWorkbenchMergeAiStream,
  composeWorkbenchMergeAiStream,
  getWorkbenchMergeRequirementAiModel,
  saveWorkbenchMergeAi,
} from '@/api/testWorkbench'
import RequirementFormDialog from '@/views/test-workbench/components/RequirementFormDialog.vue'
import RequirementPreviewDrawer from '@/views/test-workbench/components/RequirementPreviewDrawer.vue'
import RequirementRefinementDrawer from '@/views/test-workbench/components/RequirementRefinementDrawer.vue'
import { formatBeijingTime } from '@/utils/beijingTime'

const props = defineProps({ requirementType: { type: String, default: 'original' } })

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.id))
const isCompleted = computed(() => props.requirementType === 'completed')
const { refreshDashboardStats, scope, scopeRefreshKey } = inject('workbenchContext')
const queryId = value => {
  const id = Number(value)
  return Number.isInteger(id) && id > 0 ? id : undefined
}
const filters = reactive({ title: '', status: '', created_dates: [], page: 1, page_size: 10 })
const statuses = [{ label: '待确认', value: 'draft' }, { label: '已确认', value: 'confirmed' }]
const items = ref([]); const systems = ref([]); const versions = ref([]); const total = ref(0); const loading = ref(false)
const formVisible = ref(false); const previewVisible = ref(false); const aiVisible = ref(false); const editing = ref(null); const activeDetail = ref(null); const startPreviewEditing = ref(false)
const selectedRows = ref([])
let requestNo = 0
const filteredVersions = computed(() => {
  const selectedVersionIds = scope.value.version_ids?.split(',').map(Number) || []
  const selectedSystemIds = scope.value.system_ids?.split(',').map(Number) || []
  if (selectedVersionIds.length) return versions.value.filter(item => selectedVersionIds.includes(item.id))
  if (selectedSystemIds.length) return versions.value.filter(item => selectedSystemIds.includes(item.system_id))
  return versions.value
})
const statusLabel = status => ({ draft: '待确认', confirmed: '已确认' }[status] || '待确认')
const statusType = status => ({ draft: 'info', confirmed: 'success' }[status] || 'info')
const formatTime = value => formatBeijingTime(value) || '—'
const withCount = (label, count) => count > 0 ? `${label}（${count}）` : label
const mergeableSelection = computed(() => {
  const rows = selectedRows.value
  if (!rows.length) return false
  if (rows.some(r => r.confirm_status !== 'confirmed')) return false
  return new Set(rows.map(r => r.version_id)).size === 1 && new Set(rows.map(r => r.system_id)).size === 1
})
const confirmableSelection = computed(() => selectedRows.value.length > 0 && selectedRows.value.every(row => row.confirm_status === 'draft'))
const onSelectionChange = rows => { selectedRows.value = rows }
const batchScopePayload = () => ({
  project_id: projectId.value,
  system_ids: scope.value.system_ids ? scope.value.system_ids.split(',').map(Number) : [],
  version_id: scope.value.version_id,
  version_ids: scope.value.version_ids ? scope.value.version_ids.split(',').map(Number) : [],
})
const currentListDeletePayload = () => {
  const [created_from, created_to] = filters.created_dates || []
  return {
    ...batchScopePayload(),
    delete_all_in_scope: true,
    title: filters.title || undefined,
    status: filters.status || undefined,
    created_from,
    created_to,
  }
}
const load = async () => {
  const current = ++requestNo; loading.value = true
  try {
    const { created_dates, ...queryFilters } = filters
    const [created_from, created_to] = created_dates || []
    const result = await getWorkbenchProjectDashboardAssets(projectId.value, { asset_type: isCompleted.value ? 'completed_requirement' : 'requirement', ...queryFilters, created_from, created_to, ...scope.value })
    if (current !== requestNo) return
    items.value = result?.items || []; systems.value = result?.systems || []; versions.value = result?.versions || []; total.value = result?.total || 0
  } finally { if (current === requestNo) loading.value = false }
}
const query = () => { filters.page = 1; load() }
const reset = () => { Object.assign(filters, { title: '', status: '', created_dates: [], page: 1, page_size: 10 }); load() }
const onSizeChange = () => { filters.page = 1; load() }
const openCreate = () => { editing.value = null; formVisible.value = true }
const loadDetail = async row => { activeDetail.value = isCompleted.value ? await getWorkbenchCompletedRequirementDetail(row.id) : await getWorkbenchRequirementDetail(row.id); return activeDetail.value }
const openEdit = async row => {
  await loadDetail(row)
  startPreviewEditing.value = true
  previewVisible.value = true
}
const openAi = async row => { await loadDetail(row); aiVisible.value = true }
const onSaved = async () => {
  await Promise.all([load(), refreshDashboardStats?.()])
}
const onAiPreviewed = async (result) => {
  await Promise.all([load(), refreshDashboardStats?.()])
  if (result?.source_requirement_id) {
    await router.push({ name: 'TestWorkbenchRequirements', params: { id: route.params.id }, query: { ...route.query, requirement_type: 'completed' } })
  }
}
// 从预览弹窗「重新补全」：预览已自行关闭，这里以当前需求（含补全正文）为基线另起一轮 AI 补全会话。
const onReComplete = () => { previewVisible.value = false; if (activeDetail.value?.id) aiVisible.value = true }
const onConfirmed = async () => {
  previewVisible.value = false
  await Promise.all([load(), refreshDashboardStats?.()])
}
const onSavedDetail = async () => { if (activeDetail.value?.id) await loadDetail(activeDetail.value); await load() }
const remove = async row => {
  await ElMessageBox.confirm(`确认删除${isCompleted.value ? '补全需求' : '原始需求'}“${row.title}”吗？`, '删除确认', { type: 'warning' })
  if (isCompleted.value) await deleteWorkbenchCompletedRequirement(row.id)
  else await deleteWorkbenchRequirement(row.id)
  if (items.value.length === 1 && filters.page > 1) filters.page -= 1
  await Promise.all([load(), refreshDashboardStats?.()])
}
const batchRemove = async () => {
  if (!selectedRows.value.length) { ElMessage.warning('请先选择要删除的需求'); return }
  await ElMessageBox.confirm(`确认删除所选 ${selectedRows.value.length} 条需求吗？`, '批量删除', { type: 'warning' })
  const data = { ...batchScopePayload(), ids: selectedRows.value.map(r => r.id) }
  if (isCompleted.value) await batchDeleteWorkbenchCompletedRequirements(data)
  else await batchDeleteWorkbenchRequirements(data)
  filters.page = 1
  await Promise.all([load(), refreshDashboardStats?.()])
}
const batchConfirm = async () => {
  if (!confirmableSelection.value) { ElMessage.warning('请选择待确认的需求'); return }
  await ElMessageBox.confirm(`确认所选 ${selectedRows.value.length} 条需求吗？`, '批量确认', { type: 'warning' })
  const data = { ...batchScopePayload(), ids: selectedRows.value.map(row => row.id) }
  if (isCompleted.value) await batchConfirmWorkbenchCompletedRequirements(data)
  else await batchConfirmWorkbenchRequirements(data)
  await Promise.all([load(), refreshDashboardStats?.()])
}
const removeAll = async () => {
  await ElMessageBox.confirm('确认删除当前查询结果中的全部需求吗？此操作不可恢复。', '全部删除', { type: 'warning' })
  const data = currentListDeletePayload()
  if (isCompleted.value) await batchDeleteWorkbenchCompletedRequirements(data)
  else await batchDeleteWorkbenchRequirements(data)
  filters.page = 1
  await Promise.all([load(), refreshDashboardStats?.()])
}

// ---------- 合并所选：直接进入对话式合并抽屉 ----------
const openMerge = async () => {
  if (!mergeableSelection.value) { ElMessage.warning('只能合并同一系统同一版本内的已确认需求'); return }
  mergeScope.value = {
    version_id: selectedRows.value[0].version_id,
    source_type: isCompleted.value ? 'completed_requirement' : 'requirement',
    source_ids: selectedRows.value.map(r => r.id),
    source_snapshots: selectedRows.value.map(row => ({
      req_no: row.req_no || '',
      title: row.title || '',
      content: isCompleted.value ? row.markdown_content || '' : row.original_content || row.markdown_content || '',
    })),
  }
  mergeAiVisible.value = true
}

// 对话式合并：不再一次性直出预览，改为携带合并作用域进入 AI 补全抽屉，逐轮追问后整理成文并保存。
// 保存前不产生任何业务记录：作用域（版本 + 来源需求）由抽屉并入每轮请求，后端重读来源正文。
const mergeAiVisible = ref(false)
const mergeScope = ref(null)
const mergedAiApi = {
  feature: 'test_workbench_requirement_merge',
  getModel: getWorkbenchMergeRequirementAiModel,
  askStream: (_id, data, onEvent, signal) => askWorkbenchMergeAiStream(data, onEvent, signal),
  composeStream: (_id, data, onEvent, signal) => composeWorkbenchMergeAiStream(data, onEvent, signal),
  compareStream: (_id, data, onEvent, signal) => compareWorkbenchMergeAiStream(data, onEvent, signal),
  save: (_id, data) => saveWorkbenchMergeAi(data),
  getOriginal: r => r?.markdown_content || '',
  getStartContent: r => r?.markdown_content || '',
}
const onMergePreviewed = async () => {
  // 保存后生成一条已落库、待确认的 AI 合并需求（在合并需求页展示）；此处仅刷新看板统计。
  mergeScope.value = null
  await refreshDashboardStats?.()
}
load()
watch(scopeRefreshKey, () => {
  filters.page = 1
  load()
})
</script>

<style scoped>
.workbench-list-section { height: 100%; min-height: 0; display: flex; flex-direction: column; gap: 16px; }
.requirement-page { display: flex; flex: 1; min-height: 0; flex-direction: column; }
.list-toolbar { flex-shrink: 0; margin-bottom: 12px; padding: 12px 16px 12px; background: #f8fafc; border: 1px solid #edf1f6; border-radius: 10px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.02); }
/* 筛选项和按钮区分行，按钮在空间不足时自然换行 */
.toolbar-form { display: flex; align-items: flex-start; flex-wrap: wrap; gap: 12px 10px; width: 100%; }
.toolbar-form :deep(.el-form-item) { flex: none; margin: 0; }
.toolbar-button-item { flex: 0 0 100%; width: 100%; min-width: 0; }
.toolbar-button-item :deep(.el-form-item__content) { width: 100%; }
.toolbar-buttons { display: flex; align-items: center; flex-wrap: wrap; gap: 10px 12px; width: 100%; white-space: nowrap; }
.toolbar-buttons :deep(.el-button) { flex: 0 0 auto; }
.table-wrap { flex: 1; min-width: 0; min-height: 0; width: 100%; overflow: hidden; }
.table-wrap :deep(.el-table__cell) { white-space: nowrap; }
.table-actions { display: flex; justify-content: center; gap: 8px; white-space: nowrap; }
.table-actions :deep(.el-button + .el-button) { margin-left: 0; }
.status-cell { display: flex; align-items: center; gap: 6px; line-height: 1; white-space: nowrap; }
.status-stale { color: var(--el-color-warning); font-size: 12px; line-height: 16px; }

.asset-empty { padding: 0; }
.asset-empty :deep(.el-empty__image) { margin-bottom: 14px; }
.asset-empty :deep(.el-empty__description) { margin-top: 0; color: #909399; font-size: 14px; line-height: 20px; }
.list-pagination { display: flex; justify-content: flex-end; padding-top: 14px; flex-shrink: 0; }
</style>
