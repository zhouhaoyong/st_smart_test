<template>
  <div class="pending-list">
    <div class="pending-toolbar">
      <el-form :inline="true" :model="filters" @submit.prevent>
        <el-form-item label="Bug 标题"><el-input v-model="filters.title" clearable placeholder="请输入 Bug 标题" style="width: 180px" @keyup.enter="handleQuery" /></el-form-item>
        <el-form-item label="严重级别"><el-select v-model="filters.severity" clearable placeholder="全部严重级别" style="width: 140px"><el-option label="严重" value="critical" /><el-option label="主要" value="major" /><el-option label="一般" value="minor" /></el-select></el-form-item>
        <el-form-item v-if="view === 'handled'" label="当前状态"><el-select v-model="filters.status" clearable placeholder="全部状态" style="width: 130px"><el-option label="待解决" value="pending" /><el-option label="待验证" value="resolved" /><el-option label="已关闭" value="closed" /></el-select></el-form-item>
        <el-form-item label="创建时间"><el-date-picker v-model="filters.created_dates" type="daterange" value-format="YYYY-MM-DD" format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 240px" /></el-form-item>
        <el-form-item><el-button @click="handleQuery">查询</el-button><el-button @click="resetFilters">重置</el-button></el-form-item>
      </el-form>
    </div>

    <div class="table-wrap">
      <el-table v-loading="loading" :data="items" height="100%" row-key="id" class="pending-table" :style="{ width: '100%' }">
        <template #empty><el-empty v-if="!loading" class="pending-empty" :description="emptyText" :image-size="72" /></template>
        <el-table-column v-for="column in columns" :key="column.prop" :prop="column.prop" :label="column.label" :min-width="column.minWidth" :width="column.width" show-overflow-tooltip>
          <template #default="{ row }"><el-tag v-if="column.format === 'severity'" :type="severityType(row.severity)" size="small">{{ severityLabel(row.severity) }}</el-tag><el-tag v-else-if="column.format === 'status'" :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag><span v-else>{{ formatCell(row, column) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }"><div class="pending-actions"><el-button link type="primary" @click="openDetail(row)">查看</el-button><el-button v-if="view === 'pending'" link type="success" @click="openAction(row)">修复</el-button><el-button v-else-if="view === 'verification'" link type="warning" @click="openAction(row)">验证</el-button></div></template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pending-pagination"><el-pagination v-model:current-page="filters.page" v-model:page-size="filters.page_size" :total="total" :page-sizes="[10, 50, 100]" layout="total, sizes, prev, pager, next" @current-change="loadItems" @size-change="handleSizeChange" /></div>

    <el-dialog v-model="detail.visible" title="Bug 详情" width="980px" top="7vh" append-to-body class="pending-detail-dialog">
      <el-tabs v-model="detail.tab" class="pending-detail-tabs" @tab-change="handleDetailTabChange">
        <el-tab-pane label="Bug 详情" name="detail">
          <template v-if="detail.bug">
            <el-descriptions :column="2" border class="bug-summary">
              <el-descriptions-item label="Bug 标题" :span="2">{{ detail.bug.title }}</el-descriptions-item>
              <el-descriptions-item label="所属系统">{{ detail.bug.system_name || '—' }}</el-descriptions-item>
              <el-descriptions-item label="所属版本">{{ detail.bug.version_no || '—' }}</el-descriptions-item>
              <el-descriptions-item label="严重级别"><el-tag :type="severityType(detail.bug.severity)" size="small">{{ severityLabel(detail.bug.severity) }}</el-tag></el-descriptions-item>
              <el-descriptions-item label="优先级">{{ detail.bug.priority || '—' }}</el-descriptions-item>
              <el-descriptions-item label="当前状态"><el-tag :type="statusType(detail.bug.status)" size="small">{{ statusLabel(detail.bug.status) }}</el-tag></el-descriptions-item>
              <el-descriptions-item label="发起人">{{ detail.bug.creator_name || '—' }}</el-descriptions-item>
              <el-descriptions-item label="处理人">{{ detail.bug.assignee_name || '未指派' }}</el-descriptions-item>
              <el-descriptions-item label="验证人">{{ detail.bug.verifier_name || '—' }}</el-descriptions-item>
            </el-descriptions>
            <div class="bug-content-grid">
              <section><h4>复现步骤</h4><p>{{ detail.bug.steps || '—' }}</p></section>
              <section><h4>预期结果</h4><p>{{ detail.bug.expected_result || '—' }}</p></section>
              <section><h4>实际结果</h4><p>{{ detail.bug.actual_result || '—' }}</p></section>
              <section><h4>修复说明</h4><p>{{ detail.bug.resolution || '—' }}</p></section>
            </div>
            <el-form v-if="view === 'pending' && detail.actionable" label-position="top" class="action-form"><el-form-item label="修复说明" required><el-input v-model="detail.resolution" type="textarea" :rows="3" placeholder="请说明修复内容" /></el-form-item></el-form>
            <el-form v-if="view === 'verification' && detail.actionable" label-position="top" class="action-form"><el-form-item label="验证结果" required><el-radio-group v-model="detail.verifyResult"><el-radio value="pass">验证通过并关闭</el-radio><el-radio value="fail">验证不通过，退回处理人</el-radio></el-radio-group></el-form-item><el-form-item :label="detail.verifyResult === 'fail' ? '退回原因' : '验证结论'"><el-input v-model="detail.verifyConclusion" type="textarea" :rows="3" :placeholder="detail.verifyResult === 'fail' ? '请填写退回原因' : '选填'" /></el-form-item></el-form>
          </template>
        </el-tab-pane>
        <el-tab-pane label="流转记录" name="history"><el-empty v-if="!detail.historyLoading && !detail.history.length" description="暂无流转记录" :image-size="64" /><el-timeline v-else v-loading="detail.historyLoading" class="transition-timeline"><el-timeline-item v-for="record in detail.history" :key="record.id" :timestamp="formatTime(record.operated_at || record.created_at)"><strong>{{ actionLabel(record.action) }}</strong><span class="transition-operator">{{ record.operator_name || '—' }}</span><p v-if="record.remark">{{ record.remark }}</p></el-timeline-item></el-timeline></el-tab-pane>
      </el-tabs>
      <template #footer><div class="pending-dialog-actions"><el-button @click="detail.visible = false">关闭</el-button><el-button v-if="view === 'pending' && detail.actionable && detail.tab === 'detail'" type="primary" :loading="detail.saving" @click="submitResolve">提交修复</el-button><el-button v-if="view === 'verification' && detail.actionable && detail.tab === 'detail'" type="primary" :loading="detail.saving" @click="submitVerify">提交验证</el-button></div></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, inject, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute } from 'vue-router'
import { getWorkbenchBugTransitions, getWorkbenchProjectDashboardAssets, resolveWorkbenchBug, verifyWorkbenchBug } from '@/api/testWorkbench'
import { formatBeijingTime } from '@/utils/beijingTime'

const props = defineProps({ view: { type: String, required: true }, columns: { type: Array, required: true }, emptyText: { type: String, default: '暂无数据' }, refreshKey: { type: Number, default: 0 } })
const emit = defineEmits(['changed'])
const route = useRoute()
const projectId = computed(() => Number(route.params.id))
const { assetListRefreshKey } = inject('workbenchContext')
const filters = reactive({ title: '', severity: '', status: '', created_dates: [], page: 1, page_size: 10 })
const items = ref([])
const total = ref(0)
const loading = ref(false)
const detail = reactive({ visible: false, bug: null, tab: 'detail', history: [], historyLoading: false, actionable: false, resolution: '', verifyResult: 'pass', verifyConclusion: '', saving: false })
let requestNo = 0

const severityLabel = value => ({ critical: '严重', major: '主要', minor: '一般' }[value] || '一般')
const severityType = value => ({ critical: 'danger', major: 'warning', minor: 'info' }[value] || 'info')
const statusLabel = value => ({ pending: '待解决', resolved: '待验证', closed: '已关闭' }[value] || '—')
const statusType = value => ({ pending: 'danger', resolved: 'warning', closed: 'success' }[value] || 'info')
const actionLabel = value => ({ submit: '提交 Bug', assign: '指派', resolve: '提交修复', verify: '验证通过', reactivate: '验证不通过并退回' }[value] || value)
const formatTime = value => formatBeijingTime(value) || '—'
const formatCell = (row, column) => column.format === 'time' ? formatTime(row[column.prop]) : row[column.prop] || '—'

const loadItems = async () => {
  if (!projectId.value) return
  const currentRequestNo = ++requestNo
  loading.value = true
  try {
    const [created_from, created_to] = filters.created_dates || []
    const result = await getWorkbenchProjectDashboardAssets(projectId.value, { asset_type: 'bug', workflow_view: props.view, title: filters.title, severity: filters.severity, status: props.view === 'handled' ? filters.status : undefined, created_from, created_to, page: filters.page, page_size: filters.page_size })
    if (currentRequestNo !== requestNo) return
    items.value = result?.items || []
    total.value = result?.total || 0
  } finally { if (currentRequestNo === requestNo) loading.value = false }
}
const handleQuery = () => { filters.page = 1; loadItems() }
const handleSizeChange = () => { filters.page = 1; loadItems() }
const resetFilters = () => { Object.assign(filters, { title: '', severity: '', status: '', created_dates: [], page: 1, page_size: 10 }); loadItems() }
const openDetail = row => { Object.assign(detail, { visible: true, bug: row, tab: 'detail', history: [], actionable: false, resolution: '', verifyResult: 'pass', verifyConclusion: '' }) }
const openAction = row => { openDetail(row); detail.actionable = true }
const loadHistory = async () => { if (!detail.bug?.id || detail.historyLoading) return; detail.historyLoading = true; try { detail.history = await getWorkbenchBugTransitions(detail.bug.id) || [] } finally { detail.historyLoading = false } }
const handleDetailTabChange = tab => { if (tab === 'history') loadHistory() }
const afterAction = async () => { detail.visible = false; await loadItems(); emit('changed') }
const submitResolve = async () => { if (!detail.resolution.trim()) { ElMessage.warning('请填写修复说明'); return }; detail.saving = true; try { await resolveWorkbenchBug(detail.bug.id, { resolution: detail.resolution.trim() }); await afterAction() } finally { detail.saving = false } }
const submitVerify = async () => { if (detail.verifyResult === 'fail' && !detail.verifyConclusion.trim()) { ElMessage.warning('请填写退回原因'); return }; detail.saving = true; try { await verifyWorkbenchBug(detail.bug.id, { result: detail.verifyResult, verify_conclusion: detail.verifyConclusion.trim() || null }); await afterAction() } finally { detail.saving = false } }

loadItems()
watch(() => props.refreshKey, loadItems)
watch(assetListRefreshKey, loadItems)
</script>

<style scoped>
.pending-list { display: flex; flex: 1; flex-direction: column; min-height: 0; }
.pending-toolbar { flex-shrink: 0; }.pending-toolbar :deep(.el-form-item) { margin-bottom: 12px; }
.table-wrap { position: relative; flex: 1; min-height: 0; overflow: hidden; }
.pending-table :deep(.el-table__header .cell), .pending-table :deep(.el-table__body .cell) { white-space: nowrap; }
.pending-table :deep(.el-table__body .cell) { overflow: hidden; text-overflow: ellipsis; }
.pending-actions, .pending-dialog-actions { display: flex; align-items: center; gap: 10px; white-space: nowrap; }.pending-pagination { display: flex; justify-content: flex-end; padding-top: 14px; flex-shrink: 0; }.pending-empty { padding: 0; }
.pending-detail-tabs :deep(.el-tabs__header) { margin-bottom: 16px; }.bug-summary { margin-bottom: 14px; }.bug-content-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }.bug-content-grid section { min-height: 106px; padding: 12px 14px; border: 1px solid #ebeef5; border-radius: 6px; background: #fafcff; }.bug-content-grid h4 { margin: 0 0 8px; font-size: 14px; }.bug-content-grid p { margin: 0; line-height: 1.65; white-space: pre-wrap; color: #606266; }.action-form { margin-top: 16px; padding: 14px 16px 0; background: #f5f9ff; border: 1px solid #d9ecff; border-radius: 6px; }.transition-timeline { padding: 10px 8px; }.transition-timeline p { margin: 6px 0 0; color: #606266; white-space: pre-wrap; }.transition-operator { margin-left: 10px; color: #909399; }
</style>
