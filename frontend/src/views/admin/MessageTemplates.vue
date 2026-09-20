<template>
  <div class="page-wrap">
    <div class="admin-page-title"><h2>消息模板管理</h2></div>
    <div class="list-toolbar-frame">
      <div class="list-toolbar">
        <el-select v-model="filters.module" placeholder="所属模块" clearable style="width:160px">
          <el-option label="API测试" value="api_test" />
        </el-select>
        <el-select v-model="filters.event_type" placeholder="事件类型" clearable style="width:180px">
          <el-option label="执行报告" value="execution_report" />
        </el-select>
        <el-button @click="handleSearch">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
        <div class="toolbar-actions">
          <el-button type="primary" @click="handleCreate">新建模板</el-button>
        </div>
      </div>
    </div>

    <div class="scroll-area" v-loading="loading">
      <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" class="load-error">
        <el-button link type="danger" @click="loadTemplates">重试</el-button>
      </el-alert>
      <el-table :data="templates" stripe class="template-list-table" header-cell-class-name="no-wrap-header">
        <template #empty><GlobalEmpty text="暂无数据" /></template>
        <el-table-column prop="id" label="ID" width="70" class-name="id-cell" />
        <el-table-column prop="name" label="模板名称" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click="handleEdit(row)">{{ row.name || '-' }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="module" label="所属模块" width="160">
          <template #default="{ row }"><el-tag size="small">{{ moduleLabel(row.module) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="event_type" label="事件类型" width="140">
          <template #default="{ row }">{{ eventLabel(row.event_type) }}</template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="90">
          <template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="total > 0"
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        :page-sizes="[10, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="loadTemplates"
        @size-change="handlePageSizeChange"
        class="pagination-area"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑消息模板' : '新建消息模板'" width="760px" destroy-on-close class="template-dialog">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px" class="template-form">
        <el-form-item label="模板名称" prop="name"><el-input v-model="form.name" maxlength="100" show-word-limit /></el-form-item>
        <el-form-item label="所属模块" prop="module">
          <el-select v-model="form.module" style="width:100%">
            <el-option label="API测试" value="api_test" />
          </el-select>
        </el-form-item>
        <el-form-item label="事件类型" prop="event_type">
          <el-select v-model="form.event_type" style="width:100%">
            <el-option label="执行报告" value="execution_report" />
          </el-select>
        </el-form-item>
        <el-form-item label="变量">
          <div class="variable-box">
            <el-tag
              v-for="item in availableVariables"
              :key="item"
              size="small"
              class="variable-tag"
              @click="insertVariable(item)"
            >
              {{ formatVariable(item) }}
            </el-tag>
            <span v-if="availableVariables.length === 0" class="variable-empty">当前模块暂无预置变量</span>
          </div>
        </el-form-item>
        <el-form-item label="模板内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="8" resize="none" class="code-input" />
        </el-form-item>
        <el-link v-if="form.module" type="primary" underline="never" @click="openDefaultDialog" class="preset-link">
          填充预置模板
        </el-link>
        <el-form-item label="状态"><el-switch v-model="form.is_active" size="large" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="defaultDialogVisible" title="预置模板" width="720px">
      <el-table :data="defaultTemplates" stripe class="preset-table" header-cell-class-name="no-wrap-header">
        <el-table-column prop="name" label="模板名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="module" label="所属模块" width="100">
          <template #default="{ row }">{{ moduleLabel(row.module) }}</template>
        </el-table-column>
        <el-table-column prop="event_type" label="事件类型" width="110">
          <template #default="{ row }">{{ eventLabel(row.event_type) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }"><el-button link type="primary" @click="useDefault(row)">使用</el-button></template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import GlobalEmpty from '@/components/GlobalEmpty.vue'
import { confirmDelete } from '@/utils/confirmDelete'
import {
  createMessageTemplate, deleteMessageTemplate, getDefaultMessageTemplates,
  getMessageTemplate, getMessageTemplates, updateMessageTemplate,
} from '@/api/messageConfig'

const loading = ref(false)
const templates = ref([])
const errorMessage = ref('')
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const defaultTemplates = ref([])
const dialogVisible = ref(false)
const defaultDialogVisible = ref(false)
const submitLoading = ref(false)
const formRef = ref(null)
const filters = reactive({ module: '', event_type: '' })
const form = reactive({ id: null, name: '', module: 'api_test', event_type: 'execution_report', content: '', variables: [], is_default: false, is_active: true })
const rules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  module: [{ required: true, message: '请选择所属模块', trigger: 'change' }],
  event_type: [{ required: true, message: '请选择事件类型', trigger: 'change' }],
  content: [{ required: true, message: '请输入模板内容', trigger: 'blur' }],
}

const moduleLabel = (v) => ({ api_test: 'API测试' }[v] || v)
const eventLabel = (v) => ({ execution_report: '执行报告' }[v] || v)
const formatVariable = (value) => `{${value}}`
const variablePresets = {
  api_test: {
    execution_report: [
      'project_name', 'env_name', 'report_name', 'report_url', 'status', 'status_emoji', 'execution_mode',
      'total_cases', 'passed_cases', 'failed_cases', 'failed_cases_styled', 'pass_rate', 'pass_rate_styled',
      'total_steps', 'passed_steps', 'failed_steps', 'duration', 'timestamp',
    ],
  },
}
const availableVariables = computed(() => {
  const preset = variablePresets[form.module]?.[form.event_type]
  if (preset?.length) return preset
  return form.variables || []
})

const resetForm = () => Object.assign(form, { id: null, name: '', module: 'api_test', event_type: 'execution_report', content: '', variables: [], is_default: false, is_active: true })

const loadTemplates = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filters.module) params.module = filters.module
    if (filters.event_type) params.event_type = filters.event_type
    const result = await getMessageTemplates(params)
    templates.value = result?.items || result || []
    total.value = Number(result?.total || templates.value.length || 0)
  } catch (error) { errorMessage.value = error?.message || '消息模板加载失败，请重试' }
  finally { loading.value = false }
}

const handlePageSizeChange = (size) => { pageSize.value = size; page.value = 1; loadTemplates() }
const handleSearch = () => { page.value = 1; loadTemplates() }

const resetFilters = () => {
  Object.assign(filters, { module: '', event_type: '' })
  page.value = 1
  loadTemplates()
}

const handleCreate = () => { resetForm(); loadDefaults(); dialogVisible.value = true }

const handleEdit = async (row) => {
  const detail = await getMessageTemplate(row.id)
  Object.assign(form, detail)
  loadDefaults()
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  const ok = await confirmDelete(row.name, '消息模板')
  if (!ok) return
  await deleteMessageTemplate(row.id)
  loadTemplates()
}

const handleSubmit = async () => {
  if (!(await formRef.value?.validate().catch(() => false))) return
  submitLoading.value = true
  try {
    const data = { ...form, variables: availableVariables.value }
    if (form.id) await updateMessageTemplate(form.id, data)
    else await createMessageTemplate(data)
    dialogVisible.value = false
    loadTemplates()
  } finally { submitLoading.value = false }
}

const openDefaultDialog = async () => {
  defaultTemplates.value = await getDefaultMessageTemplates() || []
  defaultDialogVisible.value = true
}

const useDefault = (row) => {
  form.content = row.content || ''
  defaultDialogVisible.value = false
  ElMessage.success('已填充预置模板内容')
}

const insertVariable = (variable) => {
  const token = formatVariable(variable)
  form.content = form.content ? `${form.content}${token}` : token
}

const loadDefaults = async () => {
  try { defaultTemplates.value = await getDefaultMessageTemplates() || [] }
  catch { defaultTemplates.value = [] }
}

onMounted(loadTemplates)
</script>

<style scoped>
.page-wrap { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.list-toolbar { flex-shrink: 0; display: flex; flex-wrap: wrap; gap: 10px 12px; align-items: center; margin-bottom: 10px; }
.toolbar-actions { margin-left: auto; display: flex; gap: 10px; }
.scroll-area { flex: 1; overflow-y: auto; min-height: 0; }
.load-error { margin-bottom: 10px; }
.pagination-area { display: flex; justify-content: flex-end; padding: 12px 0 0; }
:deep(.template-dialog.el-dialog) { display: flex; flex-direction: column; max-height: min(86vh, 720px); }
:deep(.template-dialog .el-dialog__header) { padding: 18px 24px 14px; margin-right: 0; border-bottom: 1px solid #eef2f7; }
:deep(.template-dialog .el-dialog__body) { flex: 1; overflow: hidden; padding: 14px 28px 8px; }
:deep(.template-dialog .el-dialog__footer) { padding: 12px 28px 18px; border-top: 1px solid #eef2f7; }
.template-form :deep(.el-form-item) { margin-bottom: 12px; }
.template-form :deep(.el-form-item__label) { font-weight: 600; color: #475569; }
.template-list-table :deep(.el-table__cell .cell),
.preset-table :deep(.el-table__cell .cell) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.template-list-table :deep(.el-table__cell:last-child .cell),
.preset-table :deep(.el-table__cell:last-child .cell) { overflow: visible; }
:deep(.no-wrap-header .cell) { white-space: nowrap; }
.variable-box { width: 100%; min-height: 30px; max-height: 84px; overflow: auto; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; }
.variable-tag { margin: 0 6px 6px 0; cursor: pointer; user-select: none; }
.variable-tag:hover { border-color: #1677ff; color: #1677ff; background: #eff6ff; }
.variable-empty { font-size: 13px; color: #94a3b8; }
.code-input :deep(textarea) {
  height: 210px;
  overflow: auto;
  white-space: pre;
  font-family: SFMono-Regular, Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
}
.preset-link { display: block; margin-bottom: 12px; font-size: 13px; }
</style>
