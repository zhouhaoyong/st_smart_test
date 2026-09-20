<template>
  <RequestConfigTabs
    ref="baseTabsRef"
    v-model:active-tab="tab"
    :model="model"
    :body-rows="bodyRows"
    :script-rows="scriptRows"
    body-placeholder="JSON格式，form-data时文件加@前缀如 @D:/file.xlsx"
    body-empty-text="当前请求不发送请求体"
    query-empty-text="暂无查询参数，请添加后配置"
    path-empty-text="暂无路径参数，请在 URL 中输入 {参数名}，系统将自动识别，或点击“添加参数”"
    headers-empty-text="暂无请求头，请添加后配置"
  >
    <template #body-toolbar-extra>
      <el-upload
        v-if="model.body_type === 'form-data'"
        :auto-upload="false"
        :show-file-list="false"
        :on-change="handleFormDataFileUpload"
        accept="*"
        style="display:inline-block"
      >
        <el-button size="small" :loading="formDataFileUploading" type="warning" plain>
          <el-icon><UploadFilled /></el-icon>上传文件
        </el-button>
      </el-upload>
    </template>
    <template #headers-toolbar>
      <div class="header-mode-bar">
        <el-radio-group v-model="headerEditMode" size="small">
          <el-radio-button value="kv">KV</el-radio-button>
          <el-radio-button value="json">JSON</el-radio-button>
        </el-radio-group>
      </div>
    </template>
    <template #headers-content>
      <ParamEditTable
        v-if="headerEditMode === 'kv'"
        v-model="model.headers"
        title="请求头参数"
        add-label="添加请求头"
        empty-text="暂无请求头，请添加后配置"
      />
      <div v-else class="body-editor">
        <div class="body-toolbar">
          <span class="body-toolbar-title">请求头 JSON</span>
          <el-button-group size="small">
            <el-button @click="formatHeaderJson">格式化</el-button>
            <el-button @click="validateHeaderJson">校验</el-button>
          </el-button-group>
        </div>
        <el-input v-model="headerJsonText" type="textarea" :rows="6" placeholder='{"Content-Type":"application/json"}' class="code-editor" />
      </div>
    </template>
  </RequestConfigTabs>
</template>

<script setup>
/**
 * 接口参数配置：接口管理页与用例管理页的「编辑接口」弹窗共用。
 * 在公共参数配置区之上只增强两件事：form-data 上传文件、请求头在 KV 与 JSON 之间切换；
 * 请求体 JSON 的格式化/校验由公共参数配置区统一提供。
 */
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import RequestConfigTabs from '@/components/RequestConfigTabs.vue'
import ParamEditTable from '@/components/ParamEditTable.vue'
import { uploadTempFile } from '@/api/executor'

const props = defineProps({
  model: { type: Object, required: true },
  activeTab: { type: String, default: 'query' },
  bodyRows: { type: Number, default: 9 },
  scriptRows: { type: Number, default: 6 },
})

const emit = defineEmits(['update:activeTab'])

const tab = computed({
  get: () => props.activeTab,
  set: value => emit('update:activeTab', value),
})

const baseTabsRef = ref(null)
const headerEditMode = ref('kv')
const headerJsonText = ref('{}')
const formDataFileUploading = ref(false)

const formatHeaderJson = () => {
  try { const obj = JSON.parse(headerJsonText.value); headerJsonText.value = JSON.stringify(obj, null, 2) }
  catch (e) { ElMessage.error('JSON格式错误: ' + e.message) }
}
const validateHeaderJson = () => {
  try { JSON.parse(headerJsonText.value); ElMessage.success('JSON格式正确') }
  catch (e) { ElMessage.error('JSON格式错误: ' + e.message) }
}
const handleFormDataFileUpload = async (uploadFile) => {
  if (!uploadFile.raw) return
  formDataFileUploading.value = true
  try {
    // 上传到服务端，拿到临时文件引用
    const result = await uploadTempFile(uploadFile.raw, { skipSuccessToast: true, skipErrorToast: true })
    if (result && result.ref) {
      const fieldName = uploadFile.name.replace(/\.[^.]+$/, '')
      let bodyObj = {}
      try { bodyObj = JSON.parse(props.model.body_content || '{}') } catch {}
      bodyObj[fieldName] = result.ref
      props.model.body_content = JSON.stringify(bodyObj, null, 2)
      ElMessage.success(`文件「${uploadFile.name}」已上传，已添加为 "${fieldName}" 字段`)
    }
  } catch (e) {
    console.error('文件上传失败', e)
    ElMessage.error('文件上传失败: ' + (e.message || '未知错误'))
  } finally {
    formDataFileUploading.value = false
  }
}

watch(headerEditMode, (mode, prevMode) => {
  if (mode === 'json') {
    // KV 转 JSON
    const obj = {}
    ;(props.model.headers || []).forEach(h => { if (h.key) obj[h.key] = h.value })
    headerJsonText.value = JSON.stringify(obj, null, 2)
  } else if (prevMode === 'json') {
    // JSON 转 KV
    try {
      const obj = JSON.parse(headerJsonText.value || '{}')
      props.model.headers = Object.entries(obj).map(([k, v]) => ({ key: k, value: String(v), description: '', type: 'string', type_source: 'manual' }))
    } catch { props.model.headers = [{ key: '', value: '', description: '', type: 'string', type_source: 'manual' }] }
  }
})

/** 弹窗重新打开时把编辑器状态复位 */
const resetEditors = () => {
  headerEditMode.value = 'kv'
  headerJsonText.value = '{}'
  baseTabsRef.value?.resetBodyJsonError?.()
}

/** 保存/调试前把 JSON 模式下的请求头写回表单，格式错误时返回 false */
const syncHeaderJsonMode = () => {
  if (headerEditMode.value !== 'json') return true
  try {
    const obj = JSON.parse(headerJsonText.value || '{}')
    props.model.headers = Object.entries(obj).map(([k, v]) => ({ key: k, value: String(v), description: '', type: 'string', type_source: 'manual' }))
    return true
  } catch {
    ElMessage.error('请求头 JSON 格式错误')
    return false
  }
}

defineExpose({ resetEditors, syncHeaderJsonMode })
</script>

<style scoped>
.code-editor :deep(textarea) {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
}
.header-mode-bar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}
.body-editor {
  border: 1px solid #e8edf3;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}
.body-toolbar {
  min-height: 42px;
  padding: 6px 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  background: #fbfcfe;
  border-bottom: 1px solid #edf1f7;
}
.body-toolbar-title {
  color: #303133;
  font-weight: 600;
  font-size: 13px;
}
.body-editor :deep(.el-textarea__inner) {
  border: 0;
  border-radius: 0;
  box-shadow: none;
  background: #fbfcfe;
}
</style>
