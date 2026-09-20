<template>
  <div class="page-wrap">
    <div class="admin-page-title"><h2>消息渠道管理</h2></div>
    <div class="list-toolbar-frame">
      <div class="list-toolbar">
        <el-input v-model="filters.group_name" placeholder="群名称" clearable style="width:200px" @keyup.enter="handleSearch" />
        <el-select v-model="filters.is_active" placeholder="状态" clearable style="width:140px">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
        <el-select v-model="filters.channel_type" placeholder="渠道类型" clearable style="width:160px">
          <el-option label="钉钉" value="dingtalk" />
          <el-option label="飞书" value="feishu" />
          <el-option label="企业微信" value="wecom" />
          <el-option label="Webhook" value="webhook" />
        </el-select>
        <el-button @click="handleSearch">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
        <div class="toolbar-actions">
          <el-button type="primary" @click="handleCreate">添加渠道</el-button>
        </div>
      </div>
    </div>

    <div class="scroll-area" v-loading="loading">
      <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" class="load-error">
        <el-button link type="danger" @click="loadChannels">重试</el-button>
      </el-alert>
      <el-table :data="channels" stripe>
        <template #empty><GlobalEmpty text="暂无数据" /></template>
        <el-table-column prop="group_name" label="群名称" width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click="handleEdit(row)">{{ row.group_name || '-' }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="channel_type" label="渠道类型" width="110">
          <template #default="{ row }"><el-tag size="small">{{ channelLabel(row.channel_type) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="webhook_url" label="Webhook" min-width="360" show-overflow-tooltip />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="success" size="small" @click="handleTest(row)" :loading="testingId === row.id">测试</el-button>
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
        @current-change="loadChannels"
        @size-change="handlePageSizeChange"
        class="pagination-area"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑消息渠道' : '添加消息渠道'" width="580px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="form.id ? editRules : rules" label-width="90px">
        <el-form-item label="群名称" prop="group_name"><el-input v-model="form.group_name" maxlength="100" show-word-limit placeholder="例如：测试团队通知群" /></el-form-item>
        <el-form-item label="渠道类型" prop="channel_type">
          <el-select v-model="form.channel_type" style="width:100%">
            <el-option label="钉钉" value="dingtalk" />
            <el-option label="飞书" value="feishu" />
            <el-option label="企业微信" value="wecom" />
            <el-option label="Webhook" value="webhook" />
          </el-select>
        </el-form-item>
        <el-form-item label="Webhook" prop="webhook_url"><el-input v-model="form.webhook_url" maxlength="500" show-word-limit /></el-form-item>
        <el-form-item label="钉钉关键词">
          <el-input v-model="form.keyword" maxlength="100" show-word-limit placeholder="对应钉钉安全设置中的自定义关键词" />
          <div class="form-tip">钉钉开启“自定义关键词”时，发送内容必须包含这里填写的关键词。</div>
        </el-form-item>
        <el-form-item label="加签密钥">
          <el-input v-model="form.secret" type="password" show-password placeholder="对应钉钉安全设置中的加签密钥，可选" />
          <div class="form-tip">只有钉钉机器人开启“加签”时才需要填写；它和自定义关键词不是同一个配置。</div>
        </el-form-item>
        <el-form-item label="状态"><el-switch v-model="form.is_active" size="large" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="success" @click="handleTestInDialog" :loading="testLoading">测试发送</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="referenceDialog.visible" class="channel-reference-dialog" title="删除失败" width="520px" destroy-on-close>
      <div class="reference-error-message" role="alert">
        <div class="reference-error-copy">
          <div>
            该渠道已被<el-link class="reference-project-count" type="primary" @click="referenceDialog.showDetails = !referenceDialog.showDetails">
              {{ referenceDialog.data.project_count }}个项目
            </el-link>的{{ referenceDialog.data.execution_set_count }}个执行集选择；
          </div>
          <div>请先手动在对应的执行集下取消选择后再删除。</div>
        </div>
      </div>
      <div v-if="referenceDialog.showDetails" class="reference-details">
        <div v-for="source in referenceGroups" :key="source.source_type" class="reference-source">
          <div class="reference-source-title">{{ source.source_label }}</div>
          <div v-for="project in source.projects" :key="`${source.source_type}-${project.project_id}`" class="reference-project">
            <div class="reference-project-name">{{ project.project_name }}</div>
            <div class="reference-execution-sets">
              <span v-for="(executionSet, index) in project.execution_sets" :key="executionSet.execution_set_id" class="reference-execution-set">
                {{ executionSet.execution_set_name }}<span v-if="index < project.execution_sets.length - 1" class="reference-separator">、</span>
              </span>
            </div>
          </div>
        </div>
      </div>
      <template #footer><el-button @click="referenceDialog.visible = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import GlobalEmpty from '@/components/GlobalEmpty.vue'
import { confirmDelete } from '@/utils/confirmDelete'
import {
  createMessageChannel, deleteMessageChannel, getMessageChannel, getMessageChannelReferences, getMessageChannels,
  testMessageChannel, testTempMessageChannel, updateMessageChannel,
} from '@/api/messageConfig'

const loading = ref(false)
const channels = ref([])
const errorMessage = ref('')
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const dialogVisible = ref(false)
const submitLoading = ref(false)
const testingId = ref(null)
const testLoading = ref(false)
const formRef = ref(null)
const filters = reactive({ group_name: '', is_active: '', channel_type: '' })
const form = reactive({ id: null, name: '', channel_type: 'dingtalk', webhook_url: '', secret: '', keyword: '', group_name: '', is_active: true })
const referenceDialog = reactive({
  visible: false,
  showDetails: false,
  data: { project_count: 0, execution_set_count: 0, references: [] },
})
const rules = {
  group_name: [{ required: true, message: '请输入群名称', trigger: 'blur' }],
  channel_type: [{ required: true, message: '请选择渠道类型', trigger: 'change' }],
  webhook_url: [{ required: true, message: '请输入 Webhook 地址', trigger: 'blur' }],
}
const editRules = { ...rules, group_name: [] }

const channelLabel = (type) => ({ dingtalk: '钉钉', feishu: '飞书', wecom: '企业微信', webhook: 'Webhook' }[type] || type)

const referenceGroups = computed(() => {
  const sourceMap = new Map()
  for (const item of referenceDialog.data.references || []) {
    let source = sourceMap.get(item.source_type)
    if (!source) {
      source = { source_type: item.source_type, source_label: item.source_label, projects: [] }
      sourceMap.set(item.source_type, source)
    }
    let project = source.projects.find(group => group.project_id === item.project_id)
    if (!project) {
      project = { project_id: item.project_id, project_name: item.project_name, execution_sets: [] }
      source.projects.push(project)
    }
    project.execution_sets.push({
      execution_set_id: item.execution_set_id,
      execution_set_name: item.execution_set_name,
    })
  }
  return Array.from(sourceMap.values())
})

const openReferenceDialog = (data) => {
  Object.assign(referenceDialog, {
    visible: true,
    showDetails: false,
    data: data || { project_count: 0, execution_set_count: 0, references: [] },
  })
}

const resetForm = () => Object.assign(form, { id: null, name: '', channel_type: 'dingtalk', webhook_url: '', secret: '', keyword: '', group_name: '', is_active: true })

const loadChannels = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filters.group_name) params.group_name = filters.group_name
    if (filters.channel_type) params.channel_type = filters.channel_type
    if (typeof filters.is_active === 'boolean') params.is_active = filters.is_active
    const result = await getMessageChannels(params)
    channels.value = result?.items || result || []
    total.value = Number(result?.total || channels.value.length || 0)
  } catch (error) {
    errorMessage.value = error?.message || '消息渠道加载失败，请重试'
  }
  finally { loading.value = false }
}

const handlePageSizeChange = (size) => { pageSize.value = size; page.value = 1; loadChannels() }
const handleSearch = () => { page.value = 1; loadChannels() }
const resetFilters = () => { Object.assign(filters, { group_name: '', is_active: '', channel_type: '' }); page.value = 1; loadChannels() }

const handleCreate = () => { resetForm(); dialogVisible.value = true }

const handleEdit = async (row) => {
  const detail = await getMessageChannel(row.id)
  Object.assign(form, { ...detail, secret: detail.secret === '***' ? '' : (detail.secret || '') })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  let referenceData
  try {
    referenceData = await getMessageChannelReferences(row.id)
  } catch {
    return
  }
  if (referenceData?.execution_set_count > 0) {
    openReferenceDialog(referenceData)
    return
  }
  const ok = await confirmDelete(row.name, '消息渠道')
  if (!ok) return
  try {
    await deleteMessageChannel(row.id, { skipErrorToast: true })
    await loadChannels()
  } catch (error) {
    const referenceErrorData = error?.data?.data
    if (referenceErrorData?.execution_set_count > 0) {
      openReferenceDialog(referenceErrorData)
      return
    }
    ElMessage.error(error?.message || '消息渠道删除失败，请重试')
  }
}

const handleTest = async (row) => {
  testingId.value = row.id
  try { await testMessageChannel(row.id) }
  catch {}
  finally { testingId.value = null }
}

const handleTestInDialog = async () => {
  if (!form.webhook_url) { ElMessage.warning('请先填写 Webhook'); return }
  testLoading.value = true
  try {
    if (form.id) await testMessageChannel(form.id)
    else await testTempMessageChannel(form)
  } catch {}
  finally { testLoading.value = false }
}

const handleSubmit = async () => {
  if (!(await formRef.value?.validate().catch(() => false))) return
  submitLoading.value = true
  try {
    const typeLabel = channelLabel(form.channel_type)
    const data = { ...form, name: typeLabel, secret: form.secret || null, keyword: form.keyword || null, group_name: form.group_name || null }
    if (form.id) await updateMessageChannel(form.id, data)
    else await createMessageChannel(data)
    dialogVisible.value = false
    loadChannels()
  } finally { submitLoading.value = false }
}

onMounted(loadChannels)
</script>

<style scoped>
.page-wrap { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.list-toolbar { flex-shrink: 0; display: flex; flex-wrap: wrap; gap: 10px 12px; align-items: center; margin-bottom: 10px; }
.toolbar-actions { margin-left: auto; display: flex; gap: 10px; }
.scroll-area { flex: 1; overflow-y: auto; min-height: 0; }
.load-error { margin-bottom: 10px; }
.pagination-area { display: flex; justify-content: flex-end; padding: 12px 0 0; }
:deep(.el-dialog) { display: flex; flex-direction: column; max-height: min(90vh, 720px); }
:deep(.el-dialog__body) { flex: 1; overflow-y: auto; padding: 20px 28px; }
:deep(.channel-reference-dialog) { max-height: min(80vh, 640px); }
:deep(.channel-reference-dialog .el-dialog__body) { display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.form-tip { margin-top: 6px; color: #8c8c8c; font-size: 12px; line-height: 1.5; }
.reference-error-message { flex: 0 0 auto; padding: 10px 14px; background: #fff7e6; color: #e6a23c; }
.reference-details { flex: 1 1 auto; min-height: 0; max-height: min(50vh, 420px); margin-top: 14px; overflow-y: auto; padding: 0 4px; }
.reference-error-copy { line-height: 24px; }
.reference-project-count { font-weight: 600; }
.reference-source + .reference-source { margin-top: 14px; }
.reference-source-title { padding-bottom: 6px; border-bottom: 1px solid #ebeef5; color: #303133; font-weight: 600; }
.reference-project { display: flex; flex-wrap: wrap; align-items: baseline; padding: 6px 2px; border-bottom: 1px solid #f2f3f5; line-height: 1.6; }
.reference-project-name { flex: 0 0 auto; margin-right: 4px; color: #303133; font-weight: 500; }
.reference-execution-sets { min-width: 0; color: #606266; font-size: 13px; }
.reference-execution-set { display: inline; }
.reference-separator { color: #c0c4cc; }
</style>
