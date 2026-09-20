<template>
  <section class="workbench-list-section">
    <div class="merged-page">
        <div class="list-toolbar">
          <el-form :inline="true" @submit.prevent>
            <el-form-item label="需求标题"><el-input v-model="filters.title" clearable placeholder="请输入需求标题" style="width: 180px" @keyup.enter="query" /></el-form-item>
            <el-form-item label="合并状态"><el-select v-model="filters.merge_status" clearable placeholder="全部状态" style="width: 140px"><el-option label="已合并" value="merged" /><el-option label="待重新合并" value="stale" /></el-select></el-form-item>
            <el-form-item label="创建时间"><el-date-picker v-model="filters.created_dates" type="daterange" value-format="YYYY-MM-DD" format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 240px" /></el-form-item>
            <el-form-item><el-button @click="query">查询</el-button><el-button @click="reset">重置</el-button><el-button :disabled="!confirmableSelection" @click="batchConfirm">批量确认</el-button></el-form-item>
          </el-form>
        </div>
        <div class="table-wrap">
          <el-table v-loading="loading" :data="items" height="100%" row-key="id" style="width: 100%" @selection-change="onSelectionChange">
            <template #empty><GlobalEmpty v-if="!loading" text="暂无数据" /></template>
            <el-table-column type="selection" width="46" />
            <el-table-column prop="title" label="需求标题" width="220" show-overflow-tooltip>
              <template #default="{ row }"><el-link type="primary" underline="never" @click.stop="openDetail(row, 'preview', true)">{{ row.title }}</el-link></template>
            </el-table-column>
            <el-table-column prop="system_name" label="所属系统" width="130" show-overflow-tooltip />
            <el-table-column prop="version_no" label="所属版本" width="120" show-overflow-tooltip />
            <el-table-column label="状态" width="120"><template #default="{ row }"><el-tag :type="row.confirm_status === 'confirmed' ? 'success' : 'info'" effect="light">{{ row.confirm_status === 'confirmed' ? '已确认' : '待确认' }}</el-tag></template></el-table-column>
            <el-table-column label="合并状态" width="130"><template #default="{ row }"><el-tag :type="row.is_stale ? 'warning' : 'success'" effect="light">{{ row.is_stale ? '待重新合并' : '已合并' }}</el-tag></template></el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="190"><template #default="{ row }"><span class="created-time">{{ formatTime(row.created_at) }}</span></template></el-table-column>
            <el-table-column prop="creator_name" label="创建人" min-width="110" show-overflow-tooltip><template #default="{ row }">{{ row.creator_name || '—' }}</template></el-table-column>
            <el-table-column label="操作" width="290" fixed="right" align="center">
              <template #default="{ row }">
                <div class="table-actions">
                  <el-button link type="primary" @click="openDetail(row, 'preview', true)">编辑</el-button>
                  <el-button :disabled="row.confirm_status === 'confirmed'" link type="warning" @click="confirm(row)">确认</el-button>
                  <el-button link type="primary" @click="openAi(row)">AI 补全</el-button>
                  <el-button link type="danger" @click="remove(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div class="list-pagination"><el-pagination v-model:current-page="filters.page" v-model:page-size="filters.page_size" :total="total" :page-sizes="[10, 50, 100]" layout="total, sizes, prev, pager, next" @current-change="load" @size-change="onSizeChange" /></div>
    </div>

    <!-- 重新合并预览 -->
    <MergedRequirementRemergeDialog :dialog="remergeDialog" @confirm="submitRemerge" />

    <!-- 详情 / 编辑弹窗（合并预览 / 来源需求） -->
    <MergedRequirementDetailDrawer
      :drawer="detailDrawer"
      @save-markdown="saveDetailMarkdown"
      @remerge="openRemerge"
      @open-source="openSourceRequirement"
    />

    <!-- 来源需求下钻：查看对应原始需求详情 -->
    <RequirementPreviewDrawer v-model="sourceDrawer.visible" :detail="sourceDrawer.detail" :requirement-type="sourceDrawer.requirementType" />

    <!-- AI 补全 / 对话式合并（复用同一 AI 补全弹窗 + 合并需求接口适配器）：
         传 scope 时为「新建合并」，保存前无任何业务记录，作用域随每轮请求回传；
         不传时为对已有合并需求继续补全。 -->
    <RequirementRefinementDrawer v-model="aiVisible" :title="aiDrawerTitle" :requirement="activeMerged" :api="mergedAiApi" :scope="aiScope" :workflow="mergedAiWorkflow" @previewed="onAiPreviewed" />
  </section>
</template>

<script setup>
import { computed, inject, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'
import {
  askWorkbenchMergeAiStream,
  askWorkbenchMergedRequirementAiStream,
  composeWorkbenchMergeAiStream,
  compareWorkbenchMergeAiStream,
  composeWorkbenchMergedRequirementAiStream,
  compareWorkbenchMergedRequirementAiStream,
  confirmWorkbenchMergedRequirement,
  batchConfirmWorkbenchMergedRequirements,
  deleteWorkbenchMergedRequirement,
  getWorkbenchMergedRequirement,
  getWorkbenchCompletedRequirementDetail,
  getWorkbenchRequirementDetail,
  getWorkbenchMergeRequirementAiModel,
  getWorkbenchMergedRequirementAiModel,
  getWorkbenchProjectDashboardAssets,
  remergeSaveWorkbenchMergedRequirement,
  remergeWorkbenchMergedRequirementPreview,
  saveWorkbenchMergeAi,
  saveWorkbenchMergedRequirementAi,
  updateWorkbenchMergedRequirement,
} from '@/api/testWorkbench'
import GlobalEmpty from '@/components/GlobalEmpty.vue'
import MergedRequirementRemergeDialog from '@/views/test-workbench/components/MergedRequirementRemergeDialog.vue'
import MergedRequirementDetailDrawer from '@/views/test-workbench/components/MergedRequirementDetailDrawer.vue'
import RequirementRefinementDrawer from '@/views/test-workbench/components/RequirementRefinementDrawer.vue'
import RequirementPreviewDrawer from '@/views/test-workbench/components/RequirementPreviewDrawer.vue'
import { formatBeijingTime } from '@/utils/beijingTime'

const route = useRoute()
const projectId = computed(() => Number(route.params.id))
const workbenchContext = inject('workbenchContext', {})
const { refreshDashboardStats, scope, scopeRefreshKey } = workbenchContext

const queryId = value => {
  const id = Number(value)
  return Number.isInteger(id) && id > 0 ? id : undefined
}
const filters = reactive({ title: '', merge_status: '', created_dates: [], page: 1, page_size: 10 })
const systems = ref([])
const versions = ref([])
const items = ref([])
const total = ref(0)
const loading = ref(false)
const selectedRows = ref([])
let requestNo = 0
const filteredVersions = computed(() => {
  const selectedVersionIds = scope.value.version_ids?.split(',').map(Number) || []
  const selectedSystemIds = scope.value.system_ids?.split(',').map(Number) || []
  if (selectedVersionIds.length) return versions.value.filter(item => selectedVersionIds.includes(item.id))
  if (selectedSystemIds.length) return versions.value.filter(item => selectedSystemIds.includes(item.system_id))
  return versions.value
})

const formatTime = value => formatBeijingTime(value) || '—'
const onSelectionChange = rows => { selectedRows.value = rows }
const confirmableSelection = computed(() => selectedRows.value.length > 0 && selectedRows.value.every(row => row.confirm_status === 'draft'))
const batchScopePayload = () => ({
  project_id: projectId.value,
  system_ids: scope.value.system_ids ? scope.value.system_ids.split(',').map(Number) : [],
  version_id: scope.value.version_id,
  version_ids: scope.value.version_ids ? scope.value.version_ids.split(',').map(Number) : [],
})

// ---------- 列表：与需求列表一致，统一走看板资产接口拿编号/系统/版本/创建人 ----------
const load = async () => {
  const current = ++requestNo
  loading.value = true
  try {
    const { created_dates, ...queryFilters } = filters
    const [created_from, created_to] = created_dates || []
    const result = await getWorkbenchProjectDashboardAssets(projectId.value, { asset_type: 'merged_requirement', ...queryFilters, created_from, created_to, ...scope.value })
    if (current !== requestNo) return
    items.value = result?.items || []
    systems.value = result?.systems || []
    versions.value = result?.versions || []
    total.value = result?.total || 0
  } finally { if (current === requestNo) loading.value = false }
}
const query = () => { filters.page = 1; load() }
const reset = () => { Object.assign(filters, { title: '', merge_status: '', created_dates: [], page: 1, page_size: 10 }); load() }
const onSizeChange = () => { filters.page = 1; load() }

// ---------- 重新合并（从详情抽屉触发） ----------
const remergeDialog = reactive({ visible: false, id: null, title: '', markdown_content: '', source_ids: [], saving: false })
const openRemerge = async () => {
  const row = detailDrawer.data
  if (!row?.id) return
  detailDrawer.remerging = true
  try {
    const result = await remergeWorkbenchMergedRequirementPreview(row.id)
    remergeDialog.id = row.id
    remergeDialog.title = result?.title || row.title
    remergeDialog.markdown_content = result?.markdown_content || ''
    // 预览随正文回传的最新有效来源需求；后端会保持既有的来源类型，避免补全需求被降级为原始需求。
    remergeDialog.source_ids = (result?.sources || []).map(item => item.source_id).filter(Boolean)
    remergeDialog.visible = true
  } finally { detailDrawer.remerging = false }
}
const submitRemerge = async () => {
  remergeDialog.saving = true
  try {
    // 重新合并保存走 remerge-save：后端按既有来源类型重新读取正文，并覆盖来源列表、清除「待重新合并」标记。
    await remergeSaveWorkbenchMergedRequirement(remergeDialog.id, {
      title: remergeDialog.title,
      markdown_content: remergeDialog.markdown_content,
      source_ids: remergeDialog.source_ids,
    })
    remergeDialog.visible = false
    if (detailDrawer.data?.id === remergeDialog.id) detailDrawer.data = await getWorkbenchMergedRequirement(remergeDialog.id)
    await load()
    await refreshDashboardStats?.()
  } finally { remergeDialog.saving = false }
}

// ---------- 详情 / 编辑 ----------
const detailDrawer = reactive({ visible: false, loading: false, data: null, tab: 'preview', editing: false, titleDraft: '', markdownDraft: '', saving: false, remerging: false })
const openDetail = async (row, tab = 'preview', editing = false) => {
  detailDrawer.visible = true
  detailDrawer.loading = true
  detailDrawer.editing = false
  detailDrawer.tab = tab
  detailDrawer.data = row
  try {
    detailDrawer.data = await getWorkbenchMergedRequirement(row.id)
    if (editing) {
      detailDrawer.titleDraft = detailDrawer.data?.title || ''
      detailDrawer.markdownDraft = detailDrawer.data?.markdown_content || ''
      detailDrawer.editing = true
    }
  } finally { detailDrawer.loading = false }
}
const saveDetailMarkdown = async () => {
  detailDrawer.saving = true
  try {
    detailDrawer.data = await updateWorkbenchMergedRequirement(detailDrawer.data.id, { title: detailDrawer.titleDraft, markdown_content: detailDrawer.markdownDraft })
    detailDrawer.editing = false
    await load()
    await refreshDashboardStats?.()
  } finally { detailDrawer.saving = false }
}

// ---------- AI 补全 / 对话式合并（复用需求 AI 补全弹窗，接口切换为合并需求） ----------
const aiVisible = ref(false)
const activeMerged = ref(null)
// 「新建合并」时携带的启动载荷 { version_id, source_requirement_ids, title }；对已有合并需求补全时为 null。
const aiScope = ref(null)
const aiDrawerTitle = computed(() => (aiScope.value ? 'AI 合并需求（对话式）' : 'AI 补全合并需求'))
const mergedAiWorkflow = computed(() => (aiScope.value ? {} : {
  saveHint: '保存后将更新当前 AI 合并需求正文，不会新增需求记录。',
}))
// 合并需求没有 original_content：原始/发起内容都取当前合并正文
const MERGED_BODY = {
  getOriginal: r => r?.markdown_content || '',
  getStartContent: r => r?.markdown_content || '',
}
// 对话式合并（无资产，作用域随请求回传）：由抽屉把 scope 并入每次 payload，这里只需忽略 id。
const MERGE_SCOPE_API = {
  ...MERGED_BODY,
  getModel: getWorkbenchMergeRequirementAiModel,
  askStream: (_id, data, onEvent, signal) => askWorkbenchMergeAiStream(data, onEvent, signal),
  composeStream: (_id, data, onEvent, signal) => composeWorkbenchMergeAiStream(data, onEvent, signal),
  compareStream: (_id, data, onEvent, signal) => compareWorkbenchMergeAiStream(data, onEvent, signal),
  save: (_id, data) => saveWorkbenchMergeAi(data),
}
// 已有合并需求的 AI 补全：与原始需求补全完全同构。
const MERGED_REFINE_API = {
  ...MERGED_BODY,
  getModel: getWorkbenchMergedRequirementAiModel,
  askStream: askWorkbenchMergedRequirementAiStream,
  // 「结束对话」在原文基础上修订出正文（流式、不落库），「预览并保存」写入正文
  composeStream: composeWorkbenchMergedRequirementAiStream,
  compareStream: compareWorkbenchMergedRequirementAiStream,
  save: saveWorkbenchMergedRequirementAi,
}
const mergedAiApi = computed(() => (aiScope.value ? MERGE_SCOPE_API : MERGED_REFINE_API))
const openAi = async row => {
  aiScope.value = null
  activeMerged.value = await getWorkbenchMergedRequirement(row.id)
  aiVisible.value = true
}

const confirm = async row => {
  await ElMessageBox.confirm(`确认 AI合并需求“${row.title}”吗？`, '确认需求', { type: 'warning' })
  await confirmWorkbenchMergedRequirement(row.id)
  await Promise.all([load(), refreshDashboardStats?.()])
}
const batchConfirm = async () => {
  if (!confirmableSelection.value) { ElMessage.warning('请选择待确认的 AI合并需求'); return }
  await ElMessageBox.confirm(`确认所选 ${selectedRows.value.length} 条 AI合并需求吗？`, '批量确认', { type: 'warning' })
  await batchConfirmWorkbenchMergedRequirements({ ...batchScopePayload(), ids: selectedRows.value.map(row => row.id) })
  await Promise.all([load(), refreshDashboardStats?.()])
}
const onAiPreviewed = async () => {
  // 对话式合并保存成功后才落库（保存后为待确认），刷新列表让它出现。
  aiScope.value = null
  filters.page = 1
  await load()
  await refreshDashboardStats?.()
}

// ---------- 来源需求下钻：查看对应原始需求详情 ----------
const sourceDrawer = reactive({ visible: false, detail: null, requirementType: 'original' })
const openSourceRequirement = async source => {
  const sourceId = Number(source?.id ?? source)
  const sourceType = source?.source_type || 'requirement'
  if (!Number.isInteger(sourceId) || sourceId <= 0) return
  try {
    sourceDrawer.requirementType = sourceType === 'completed_requirement' ? 'completed' : 'original'
    sourceDrawer.detail = sourceDrawer.requirementType === 'completed'
      ? await getWorkbenchCompletedRequirementDetail(sourceId)
      : await getWorkbenchRequirementDetail(sourceId)
    sourceDrawer.visible = true
  } catch {
    // 读取失败的原因以后端返回的 message 为准，请求层已统一提示
  }
}

// ---------- 删除 ----------
const remove = async row => {
  await ElMessageBox.confirm(`确认删除合并需求“${row.title}”吗？`, '删除确认', { type: 'warning' })
  await deleteWorkbenchMergedRequirement(row.id)
  if (items.value.length === 1 && filters.page > 1) filters.page -= 1
  await load()
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
.merged-page { display: flex; flex: 1; min-height: 0; flex-direction: column; }
.list-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-shrink: 0; padding: 12px 16px; margin-bottom: 12px; background: #f8fafc; border: 1px solid #edf1f6; border-radius: 10px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.02); }
.list-toolbar :deep(.el-form-item) { margin-bottom: 12px; }
.table-wrap { flex: 1; min-height: 0; overflow: hidden; }
.table-wrap :deep(.el-table__cell) { white-space: nowrap; }
.created-time { white-space: nowrap; }
.table-actions { display: flex; align-items: center; justify-content: center; gap: 10px; white-space: nowrap; }
.table-actions :deep(.el-button + .el-button) { margin-left: 0; }
.asset-empty { padding: 0; }
.asset-empty :deep(.el-empty__image) { margin-bottom: 14px; }
.asset-empty :deep(.el-empty__description) { margin-top: 0; color: #909399; font-size: 14px; line-height: 20px; }
.list-pagination { display: flex; justify-content: flex-end; padding-top: 14px; flex-shrink: 0; }
</style>
