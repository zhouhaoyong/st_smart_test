<template>
  <div class="page-wrap">
    <div class="page-header">
      <div class="page-title">
        <h2>通知配置</h2>
        <span class="page-desc">配置钉钉机器人通知，执行集运行完成后自动推送测试报告</span>
      </div>
      <el-button type="primary" :icon="Plus" @click="handleCreate">添加渠道</el-button>
    </div>

    <div class="scroll-area" v-loading="loading">
      <el-table :data="configList" stripe>
        <el-table-column prop="id" label="ID" width="70" class-name="id-cell" />
        <el-table-column prop="channel" label="通知渠道" width="100">
          <template #default="{ row }">
            <el-tag type="primary" size="small">{{ row.channel }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="group_name" label="发送群" width="140" show-overflow-tooltip />
        <el-table-column prop="url" label="Webhook" min-width="280" show-overflow-tooltip />
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="150">
          <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="success" size="small" @click="handleTest(row)" :loading="testLoadingId === row.id">测试</el-button>
            <el-button link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="580px" destroy-on-close>
      <el-form :model="form" ref="formRef" label-width="90px">
        <el-form-item label="通知渠道" required>
          <el-select v-model="form.channel" placeholder="选择渠道" style="width:100%" size="large" :disabled="!!form.id">
            <el-option label="钉钉" value="钉钉" />
          </el-select>
        </el-form-item>
        <el-form-item label="Webhook" required>
          <el-input v-model="form.url" placeholder="https://oapi.dingtalk.com/robot/send?access_token=xxx" size="large" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="发送群">
          <el-input v-model="form.group_name" placeholder="例如：测试团队群" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="秘钥">
          <el-input v-model="form.secret" type="password" placeholder="可选，钉钉机器人安全设置中的加签密钥" show-password />
        </el-form-item>
        <el-form-item label="消息模板">
          <div style="margin-bottom:6px">
            <el-button size="small" @click="applyPresetTemplate">使用预设模板</el-button>
          </div>
          <el-input v-model="form.template" type="textarea" :rows="8" placeholder="留空使用默认模板" class="code-input" />
          <div class="form-tip">
            可用变量：{project_name}、{env_name}、{report_name}、{report_url}、{status}、{total_cases}、{passed_cases}、{failed_cases}、{failed_cases_styled}、{pass_rate}、{pass_rate_styled}、{duration}、{timestamp}
          </div>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" size="large" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="success" @click="handleTestInDialog" :loading="testLoading">测试发送</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { confirmDelete } from '@/utils/confirmDelete'
import { formatBeijingMinute } from '@/utils/beijingTime'
import {
  getNotificationConfigs, getNotificationConfig, createNotificationConfig,
  updateNotificationConfig, deleteNotificationConfig, testNotification, testNotificationWithData,
} from '@/api/notifications'

const loading = ref(false)
const configList = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('')
const formRef = ref(null)
const submitLoading = ref(false)
const testLoadingId = ref(null)
const testLoading = ref(false)

const form = reactive({ id: null, channel: '钉钉', url: '', secret: '', group_name: '', template: '', is_active: true })

const formatDate = (d) => d ? formatBeijingMinute(d) || '-' : '-'

const presetTemplate = `# 🚀 API 自动化测试报告

---

### 📋 基础信息

- **📂 项目名称**：\`{project_name}\`
- **🌍 运行环境**：\`{env_name}\`
- **📝 报告名称**：\`{report_name}\`
- **⏱️ 执行耗时**：\`{duration}\`s

> **📅 执行时间**：\`{timestamp}\`

---

### 📊 测试结果概览

| 统计指标 | 结果数据 |
| :--- | :--- |
| **📌 总用例数** | **{total_cases}** |
| **✅ 通过数量** | **{passed_cases}** |
| **❌ 失败数量** | {failed_cases_styled} |
| **📈 通过率** | {pass_rate_styled} |

---

### 💡 详细说明

- **最终状态**：\`{status}\`
- **备注**：请检查失败用例的具体日志以定位问题。

> 🔗 [点击查看详情]({report_url})`

const applyPresetTemplate = () => {
  form.template = presetTemplate
  ElMessage.success('已应用预设消息模板')
}

const loadConfigs = async () => {
  loading.value = true
  try { configList.value = await getNotificationConfigs() || [] }
  catch { configList.value = [] }
  finally { loading.value = false }
}

const handleCreate = () => {
  Object.assign(form, { id: null, channel: '钉钉', url: '', secret: '', group_name: '', template: presetTemplate, is_active: true })
  dialogTitle.value = '添加通知渠道'
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  try {
    const detail = await getNotificationConfig(row.id)
    Object.assign(form, {
      id: detail.id,
      channel: detail.channel,
      url: detail.url,
      secret: detail.secret || '',
      group_name: detail.group_name || '',
      template: detail.template || '',
      is_active: detail.is_active,
    })
    dialogTitle.value = '编辑通知配置'
    dialogVisible.value = true
  } catch {
    /* handled by interceptor */
  }
}

const handleDelete = async (row) => {
  const ok = await confirmDelete(row.group_name || row.channel, '通知配置')
  if (!ok) return
  await deleteNotificationConfig(row.id)
  // Toast由后端返回的message自动显示
  loadConfigs()
}

const handleTest = async (row) => {
  testLoadingId.value = row.id
  try { await testNotification(row.id) }
  catch { /* handled by interceptor */ }
  finally { testLoadingId.value = null }
}

const handleTestInDialog = async () => {
  if (!form.channel || !form.url) { ElMessage.warning('请先填写渠道和Webhook地址'); return }
  testLoading.value = true
  try {
    if (form.id) {
      await testNotification(form.id)
    } else {
      await testNotificationWithData({
        channel: form.channel,
        url: form.url,
        secret: form.secret || null,
        template: form.template || null,
      })
    }
  }
  catch { /* handled by interceptor */ }
  finally { testLoading.value = false }
}

const handleSubmit = async () => {
  if (!form.channel || !form.url) { ElMessage.warning('请填写渠道和Webhook地址'); return }
  if (!form.group_name) { ElMessage.warning('请填写发送群名称'); return }
  if (!form.template) { ElMessage.warning('请填写消息模板'); return }
  submitLoading.value = true
  try {
    const data = { channel: form.channel, url: form.url, secret: form.secret || null, group_name: form.group_name || null, template: form.template || null, is_active: form.is_active }
    if (form.id) { await updateNotificationConfig(form.id, data) }
    else { await createNotificationConfig(data) }
    dialogVisible.value = false
    loadConfigs()
  } finally { submitLoading.value = false }
}

onMounted(() => { loadConfigs() })
</script>

<style scoped>
.page-wrap { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.page-header { flex-shrink: 0; display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.page-title h2 { margin: 0 0 6px; font-size: 20px; font-weight: 600; color: #1a1a1a; }

/* 统一操作列背景色 */
:deep(.el-table__fixed-right) {
  box-shadow: none !important;
}
:deep(.el-table__fixed-right-patch) {
  background: transparent !important;
}
:deep(.el-table__fixed-right .el-table__row) {
  background: inherit !important;
}
:deep(.el-table__fixed-right .el-table__row:hover) {
  background: inherit !important;
}
.page-desc { font-size: 15px; color: #8c8c8c; }
.scroll-area { flex: 1; overflow-y: auto; min-height: 0; }
.code-input :deep(textarea) { font-family: SFMono-Regular, Consolas, monospace; font-size: 15px; }
.form-tip { font-size: 14px; color: #8c8c8c; margin-top: 6px; line-height: 1.6; }

/* 弹窗：自适应屏幕高度 */
:deep(.el-dialog) { display: flex; flex-direction: column; max-height: min(90vh, 750px); }
:deep(.el-dialog__body) { flex: 1; overflow-y: auto; padding: 20px 28px; }

/* 移动端适配 */
@media (max-width: 768px) {
  .el-row { flex-direction: column !important; }
  .el-row .el-col { max-width: 100% !important; flex: 0 0 100% !important; margin-bottom: 12px; }
  .el-dialog { width: 95vw !important; max-width: 95vw !important; }
  .el-table { font-size: 13px; overflow-x: auto; display: block; }
  .el-pagination { justify-content: center !important; }
  .card-header, .list-header, .tree-header { flex-direction: column; align-items: flex-start; gap: 8px; }
  .header-actions, .tree-header-actions { flex-wrap: wrap; }
}
</style>
