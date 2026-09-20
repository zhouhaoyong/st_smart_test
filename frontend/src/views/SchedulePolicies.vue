<template>
  <div class="page-wrap">
    <div class="admin-page-title"><h2>执行策略管理</h2></div>
    <div class="list-toolbar-frame">
      <div class="list-toolbar">
        <el-input v-model="filters.creator" placeholder="创建人" clearable style="width:180px" @keyup.enter="handleSearch" />
        <el-select v-model="filters.is_enabled" placeholder="状态" clearable style="width:140px">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
        <el-button @click="handleSearch">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
        <div class="toolbar-actions">
          <el-button @click="showStatusHelp">状态说明</el-button>
          <el-button type="primary" @click="handleCreate">新增策略</el-button>
        </div>
      </div>
    </div>

    <div class="scroll-area" v-loading="loading">
      <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" class="load-error">
        <el-button link type="danger" @click="loadPolicies">重试</el-button>
      </el-alert>
      <el-table :data="policies" stripe class="policy-table" header-cell-class-name="no-wrap-header">
        <el-table-column prop="name" label="策略名称" min-width="100" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click="handleEdit(row)">{{ row.name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="schedule_text" label="执行规则" min-width="100" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click="handleEdit(row)">{{ row.schedule_text }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="引用数量" align="center">
          <template #default="{ row }">
            <el-link type="primary" @click="openReferences(row)">{{ row.reference_count }} / {{ row.effective_max_references }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="创建人" show-overflow-tooltip>
          <template #default="{ row }">{{ row.creator_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">{{ row.is_enabled ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="下次触发" width="190">
          <template #default="{ row }">{{ formatDate(row.next_trigger_at) }}</template>
        </el-table-column>
        <el-table-column label="最近调度" width="190" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ formatDate(row.last_triggered_at) }}</span>
            <el-tag v-if="row.last_status && row.last_status !== 'disabled'" :type="getPolicyLastStatusType(row.last_status)" size="small" style="margin-left:8px">
              {{ getPolicyLastStatusText(row.last_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近结果" width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.last_summary?.total !== undefined">
              触发 {{ row.last_summary.triggered || 0 }}，跳过 {{ row.last_summary.skipped || 0 }}，失败 {{ row.last_summary.failed || 0 }}
            </span>
            <span v-else class="muted">暂无</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="info" @click="openLogs(row)">日志</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <el-pagination
      v-if="total > 0"
      v-model:current-page="page"
      :page-size="pageSize"
      :total="total"
      :page-sizes="[10, 50, 100]"
      layout="total, sizes, prev, pager, next"
      @current-change="loadPolicies"
      @size-change="handlePageSizeChange"
      class="pagination-area"
    />

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑执行策略' : '新增执行策略'" width="680px" :close-on-click-modal="false">
      <el-form :model="form" ref="formRef" label-width="120px" :rules="rules">
        <el-form-item label="策略名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="策略类型">
          <el-radio-group v-model="form.schedule_type" @change="resetScheduleConfig">
            <el-radio value="daily_times">每天多次</el-radio>
            <el-radio value="weekly_times">每周定时</el-radio>
            <el-radio value="interval">间隔执行</el-radio>
            <el-radio value="cron">高级 Cron</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.schedule_type === 'daily_times'" label="执行时间" prop="times">
          <el-time-picker v-model="form.times" format="HH:mm" value-format="HH:mm" placeholder="选择时间" style="width:180px" @change="addTime" />
          <div class="time-tags">
            <el-tag v-for="time in form.schedule_config.times" :key="time" closable @close="removeTime(time)">{{ time }}</el-tag>
          </div>
        </el-form-item>
        <template v-if="form.schedule_type === 'weekly_times'">
          <el-form-item label="星期">
            <el-checkbox-group v-model="form.schedule_config.weekdays">
              <el-checkbox :value="1">周一</el-checkbox>
              <el-checkbox :value="2">周二</el-checkbox>
              <el-checkbox :value="3">周三</el-checkbox>
              <el-checkbox :value="4">周四</el-checkbox>
              <el-checkbox :value="5">周五</el-checkbox>
              <el-checkbox :value="6">周六</el-checkbox>
              <el-checkbox :value="7">周日</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          <el-form-item label="执行时间">
            <el-time-picker v-model="form.times" format="HH:mm" value-format="HH:mm" placeholder="选择时间" style="width:180px" @change="addTime" />
            <div class="time-tags">
              <el-tag v-for="time in form.schedule_config.times" :key="time" closable @close="removeTime(time)">{{ time }}</el-tag>
            </div>
          </el-form-item>
        </template>
        <el-form-item v-if="form.schedule_type === 'interval'" label="执行间隔">
          <div style="display:flex;gap:10px">
            <el-input-number v-model="form.schedule_config.every" :min="5" :max="1440" />
            <el-select v-model="form.schedule_config.unit" style="width:120px">
              <el-option label="分钟" value="minutes" />
              <el-option label="小时" value="hours" />
            </el-select>
          </div>
        </el-form-item>
        <el-form-item v-if="form.schedule_type === 'cron'" label="Cron 表达式">
          <el-input v-model="form.cron_expression" placeholder="例如：0 * * * *" />
        </el-form-item>
        <el-form-item label="最大引用数">
          <el-input-number v-model="form.max_references" :min="1" :max="20" />
          <span class="muted" style="margin-left:10px">为空时使用系统默认 {{ defaultMaxReferences }}</span>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_enabled" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" maxlength="50" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="refsVisible" title="引用执行集" width="820px">
      <el-table :data="references" stripe class="policy-reference-table" header-cell-class-name="no-wrap-header">
        <el-table-column prop="project_name" label="所属项目" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.project_name || `项目ID ${row.project_id}` }}</template>
        </el-table-column>
        <el-table-column prop="name" label="执行集" min-width="160" show-overflow-tooltip />
        <el-table-column label="调度状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getSchedulerStatusType(row.scheduler_status)" size="small">
              {{ getSchedulerStatusText(row.scheduler_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近定时触发" width="170">
          <template #default="{ row }">{{ formatDate(row.last_scheduled_run_at) }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="logsVisible" title="调度日志" width="92vw" top="5vh">
      <el-form :model="logSearch" inline class="log-search">
        <el-form-item label="执行集">
          <el-input v-model="logSearch.execution_set_name" clearable placeholder="执行集名称" style="width:180px" @keyup.enter="handleLogSearch" />
        </el-form-item>
        <el-form-item label="项目">
          <el-input v-model="logSearch.project_name" clearable placeholder="项目名称" style="width:180px" @keyup.enter="handleLogSearch" />
        </el-form-item>
        <el-form-item label="触发时间">
          <el-date-picker
            v-model="logSearch.dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width:360px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleLogSearch">搜索</el-button>
          <el-button @click="handleLogReset">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="logs" v-loading="logsLoading" stripe max-height="620" class="policy-log-table" header-cell-class-name="no-wrap-header">
        <el-table-column prop="project_name" label="项目" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.project_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="execution_set_name" label="执行集" min-width="170" show-overflow-tooltip>
          <template #default="{ row }">{{ row.execution_set_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="执行状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getRunStatusType(row.status)" size="small">{{ getRunStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message_status" label="消息状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getMessageStatusType(row.message_status)" size="small">{{ getMessageStatusText(row.message_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message_detail" label="消息结果" min-width="180" show-overflow-tooltip />
        <el-table-column label="触发时间" width="170">
          <template #default="{ row }">{{ formatDate(row.triggered_at) }}</template>
        </el-table-column>
        <el-table-column label="完成时间" width="170">
          <template #default="{ row }">{{ formatDate(row.finished_at) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="logTotal > 0"
        v-model:current-page="logPage"
        :page-size="logPageSize"
        :total="logTotal"
        layout="total, sizes, prev, pager, next"
        :page-sizes="[10, 50, 100]"
        @current-change="loadLogs"
        @size-change="handleLogSizeChange"
        class="pagination-area"
      />
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatBeijingMinute } from '@/utils/beijingTime'
import {
  createSchedulePolicy,
  deleteSchedulePolicy,
  getSchedulePolicies,
  getSchedulePolicyLogs,
  getSchedulePolicyReferences,
  updateSchedulePolicy,
} from '@/api/schedulePolicies'

const loading = ref(false)
const saving = ref(false)
const policies = ref([])
const errorMessage = ref('')
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const filters = reactive({ creator: '', is_enabled: '' })
const defaultMaxReferences = ref(3)
const dialogVisible = ref(false)
const refsVisible = ref(false)
const logsVisible = ref(false)
const logsLoading = ref(false)
const references = ref([])
const logs = ref([])
const logTotal = ref(0)
const logPage = ref(1)
const logPageSize = ref(10)
const currentLogPolicyId = ref(null)
const formRef = ref(null)
const editingPolicyReferenceCount = ref(0)


const form = reactive({
  id: null,
  name: '',
  description: '',
  schedule_type: 'daily_times',
  schedule_config: { times: [] },
  cron_expression: '',
  max_references: null,
  is_enabled: true,
  times: null,
})

const rules = {
  name: [{ required: true, message: '请输入策略名称', trigger: 'blur' }],
}

const logSearch = reactive({
  execution_set_name: '',
  project_name: '',
  dateRange: null,
})

const formatDate = (value) => value ? formatBeijingMinute(value) : '-'

const getPolicyLastStatusText = (status) => ({
  triggered: '调度中',
  success: '成功',
  failed: '失败',
  disabled: '停用',
}[status] || status || '-')

const getPolicyLastStatusType = (status) => ({
  triggered: 'warning',
  success: 'success',
  failed: 'danger',
  disabled: 'info',
}[status] || 'info')

const getSchedulerStatusText = (status) => ({
  idle: '待调度',
  running: '执行中',
  disabled: '停用',
  error: '异常',
}[status] || status || '-')

const getSchedulerStatusType = (status) => ({
  idle: 'info',
  running: 'warning',
  disabled: 'info',
  error: 'danger',
}[status] || 'info')

const getRunStatusText = (status) => ({
  running: '执行中',
  success: '成功',
  failed: '失败',
  skipped: '跳过',
  pending: '待执行',
}[status] || status || '-')

const getRunStatusType = (status) => ({
  running: 'warning',
  success: 'success',
  failed: 'danger',
  skipped: 'info',
  pending: 'info',
}[status] || 'info')

const getMessageStatusText = (status) => ({
  success: '成功',
  failed: '失败',
  skipped: '跳过',
}[status] || status || '-')

const getMessageStatusType = (status) => ({
  success: 'success',
  failed: 'danger',
  skipped: 'info',
}[status] || 'info')

const loadPolicies = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filters.creator) params.creator = filters.creator
    if (typeof filters.is_enabled === 'boolean') params.is_enabled = filters.is_enabled
    const res = await getSchedulePolicies(params)
    policies.value = res.items || []
    total.value = Number(res.total || policies.value.length || 0)
    defaultMaxReferences.value = res.default_max_references || 3
  } catch (error) {
    errorMessage.value = error?.message || '执行策略加载失败，请重试'
  } finally {
    loading.value = false
  }
}

const handlePageSizeChange = (size) => { pageSize.value = size; page.value = 1; loadPolicies() }
const handleSearch = () => { page.value = 1; loadPolicies() }
const resetFilters = () => { Object.assign(filters, { creator: '', is_enabled: '' }); page.value = 1; loadPolicies() }

const resetForm = () => {
  Object.assign(form, {
    id: null,
    name: '',
    description: '',
    schedule_type: 'daily_times',
    schedule_config: { times: [] },
    cron_expression: '',
    max_references: null,
    is_enabled: true,
    times: null,
  })
}

const resetScheduleConfig = () => {
  if (form.schedule_type === 'interval') form.schedule_config = { every: 30, unit: 'minutes' }
  else if (form.schedule_type === 'weekly_times') form.schedule_config = { weekdays: [1, 2, 3, 4, 5], times: [] }
  else form.schedule_config = { times: [] }
  form.cron_expression = ''
}

const addTime = (time) => {
  if (!time) return
  const times = new Set(form.schedule_config.times || [])
  times.add(time)
  form.schedule_config.times = [...times].sort()
  form.times = null
}

const removeTime = (time) => {
  form.schedule_config.times = (form.schedule_config.times || []).filter(item => item !== time)
}

const handleCreate = () => {
  resetForm()
  editingPolicyReferenceCount.value = 0
  dialogVisible.value = true
}

const handleEdit = (row) => {
  editingPolicyReferenceCount.value = row.reference_count || 0
  Object.assign(form, {
    id: row.id,
    name: row.name,
    description: row.description || '',
    schedule_type: row.schedule_type,
    schedule_config: JSON.parse(JSON.stringify(row.schedule_config || {})),
    cron_expression: row.cron_expression || '',
    max_references: row.max_references,
    is_enabled: row.is_enabled,
    times: null,
  })
  dialogVisible.value = true
}

const buildPayload = () => ({
  name: form.name,
  description: form.description || null,
  schedule_type: form.schedule_type,
  schedule_config: form.schedule_config || {},
  cron_expression: form.schedule_type === 'cron' ? form.cron_expression : null,
  max_references: form.max_references || null,
  is_enabled: form.is_enabled,
})

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate()
  if ((form.schedule_type === 'daily_times' || form.schedule_type === 'weekly_times') && !(form.schedule_config.times || []).length) {
    ElMessage.warning('请至少添加一个执行时间')
    return
  }
  if (form.id && !form.is_enabled && editingPolicyReferenceCount.value > 0) {
    let disableMessage = `当前策略已被 ${editingPolicyReferenceCount.value} 个执行集引用，停用后这些执行集将不再自动执行。确认停用？`
    try {
      const refs = await getSchedulePolicyReferences(form.id)
      const projectCount = new Set((refs || []).map(item => item.project_id)).size
      disableMessage = `当前策略已被 ${projectCount} 个项目的 ${editingPolicyReferenceCount.value} 个执行集引用，停用后这些执行集将不再自动执行。确认停用？`
    } catch {
      // 使用列表中的引用数兜底
    }
    await ElMessageBox.confirm(
      disableMessage,
      '确认停用',
      {
        confirmButtonText: '确认停用',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  }
  saving.value = true
  try {
    if (form.id) await updateSchedulePolicy(form.id, buildPayload())
    else await createSchedulePolicy(buildPayload())
    dialogVisible.value = false
    await loadPolicies()
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row) => {
  let message = `确认删除执行策略「${row.name}」？`
  if ((row.reference_count || 0) > 0) {
    try {
      const refs = await getSchedulePolicyReferences(row.id)
      const projectCount = new Set((refs || []).map(item => item.project_id)).size
      message = `当前策略已被 ${projectCount} 个项目的 ${row.reference_count} 个执行集引用，删除后，这些执行任务将不再自动执行，确认删除？`
    } catch {
      message = `当前策略已被 ${row.reference_count} 个执行集引用，删除后，这些执行任务将不再自动执行，确认删除？`
    }
  }
  await ElMessageBox.confirm(message, '确认删除', {
    confirmButtonText: '确认删除',
    cancelButtonText: '取消',
    type: 'warning',
    confirmButtonClass: 'el-button--danger',
  })
  await deleteSchedulePolicy(row.id)
  await loadPolicies()
}

const showStatusHelp = () => {
  ElMessageBox.alert(
    [
      '执行状态：每个执行集定时触发后写入一条日志。执行完成且执行引擎未抛出异常时为成功；执行过程异常时为失败；上一次定时任务仍在运行时，本次会跳过。',
      '消息状态：执行成功生成报告后发送通知。所有配置渠道发送成功为成功；任一渠道发送失败为失败；未配置通知渠道或执行被跳过时为跳过。',
      '最近调度：策略本次触发的所有执行集任务汇总。调度中表示本次触发正在处理；有失败任务显示失败；没有失败显示成功；策略停用后不再展示最近调度状态。',
    ].join('\n\n'),
    '状态说明',
    { confirmButtonText: '知道了' }
  )
}

const openReferences = async (row) => {
  references.value = await getSchedulePolicyReferences(row.id)
  refsVisible.value = true
}

const buildLogParams = () => {
  const params = {
    skip: (logPage.value - 1) * logPageSize.value,
    limit: logPageSize.value,
  }
  if (logSearch.execution_set_name) params.execution_set_name = logSearch.execution_set_name
  if (logSearch.project_name) params.project_name = logSearch.project_name
  if (logSearch.dateRange?.length === 2) {
    params.start_time = logSearch.dateRange[0]
    params.end_time = logSearch.dateRange[1]
  }
  return params
}

const loadLogs = async () => {
  if (!currentLogPolicyId.value) return
  logsLoading.value = true
  try {
    const res = await getSchedulePolicyLogs(currentLogPolicyId.value, buildLogParams())
    logs.value = res.items || []
    logTotal.value = res.total || 0
  } finally {
    logsLoading.value = false
  }
}

const openLogs = async (row) => {
  currentLogPolicyId.value = row.id
  Object.assign(logSearch, { execution_set_name: '', project_name: '', dateRange: null })
  logPage.value = 1
  logPageSize.value = 10
  logs.value = []
  logTotal.value = 0
  logsVisible.value = true
  await loadLogs()
}

const handleLogSearch = () => {
  logPage.value = 1
  loadLogs()
}

const handleLogReset = () => {
  Object.assign(logSearch, { execution_set_name: '', project_name: '', dateRange: null })
  logPage.value = 1
  loadLogs()
}

const handleLogSizeChange = (size) => {
  logPageSize.value = size
  logPage.value = 1
  loadLogs()
}

onMounted(loadPolicies)
</script>

<style scoped>
.page-wrap { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.list-toolbar { flex-shrink: 0; display: flex; flex-wrap: wrap; gap: 10px 12px; align-items: center; margin-bottom: 16px; }
.toolbar-actions { margin-left: auto; display: flex; gap: 10px; }
.scroll-area { flex: 1; overflow-y: auto; min-height: 0; }
.load-error { margin-bottom: 10px; }
.pagination-area { flex-shrink: 0; display: flex; justify-content: flex-end; padding: 12px 0 0; }
.time-tags { display: inline-flex; gap: 8px; margin-left: 12px; flex-wrap: wrap; vertical-align: middle; }
.muted { color: #909399; font-size: 13px; }
.log-search { margin-bottom: 12px; }
.log-search :deep(.el-form-item) { margin-bottom: 12px; }
.pagination-area { flex-shrink: 0; display: flex; justify-content: flex-end; padding: 12px 0 0; }
:deep(.no-wrap-header .cell) { white-space: nowrap; }
.policy-table :deep(.el-table__cell .cell),
.policy-reference-table :deep(.el-table__cell .cell),
.policy-log-table :deep(.el-table__cell .cell) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.policy-table :deep(.el-table__cell:last-child .cell) { overflow: visible; }
</style>
