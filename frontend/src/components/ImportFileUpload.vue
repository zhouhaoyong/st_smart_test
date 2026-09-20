<template>
  <div class="import-file-upload">
    <el-upload
      :auto-upload="false"
      :show-file-list="false"
      :limit="1"
      :disabled="!!selectedFile"
      accept=".json,.yaml,.yml,.xlsx"
      :on-change="handleFileChange"
      :on-exceed="handleExceed"
      :file-list="fileList"
      class="upload-drag"
      :class="{ 'is-locked': !!selectedFile }"
      drag
    >
      <el-icon class="upload-icon"><UploadFilled /></el-icon>
      <div class="el-upload__text">将文件拖到此处，或<em>点击选择</em></div>
      <template #tip>
        <div class="upload-tip">
          支持 OpenAPI 3.0 / Swagger 2.0 / Postman v2.1（.json / .yaml / .yml，≤10MB）与 Excel 接口清单（.xlsx，≤20MB）；Excel 支持多个工作表，工作表名称将作为下级目录。
          <el-button link type="primary" :loading="downloadingTemplate" class="template-download-button" @click="$emit('download-template')">下载 Excel 模板</el-button>
        </div>
      </template>
    </el-upload>

    <div v-if="selectedFile" class="selected-file" :class="{ over: overSize }">
      <el-icon><Document /></el-icon>
      <span class="sf-name">{{ selectedFile.name }}</span>
      <span class="sf-size">{{ formatSize(selectedFile.size) }} / {{ limitLabel }}</span>
      <span v-if="overSize" class="sf-over">超出上限，请更换文件</span>
      <el-button link type="danger" size="small" class="sf-remove" @click="$emit('remove')">移除</el-button>
    </div>
  </div>
</template>

<script setup>
import { Document, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

defineProps({
  selectedFile: { type: Object, default: null },
  fileList: { type: Array, default: () => [] },
  overSize: Boolean,
  limitLabel: { type: String, default: '' },
  downloadingTemplate: Boolean,
})

const emit = defineEmits(['file-change', 'remove', 'download-template'])

function handleFileChange(file) {
  emit('file-change', file)
}

function handleExceed() {
  ElMessage.warning('仅支持上传一个文件')
}

function formatSize(bytes) {
  if (bytes == null) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<style scoped>
.import-file-upload {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  gap: 14px;
}
.upload-drag { align-self: center; width: 100%; }
.upload-drag :deep(.el-upload),
.upload-drag :deep(.el-upload-dragger) { width: 100%; }
.upload-icon { font-size: 48px; color: var(--el-color-primary); }
.upload-tip { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.6; }
.upload-tip .template-download-button { margin-left: 4px; font-size: 12px; vertical-align: baseline; }
.upload-drag.is-locked { opacity: .6; cursor: not-allowed; }
.selected-file {
  display: flex; align-items: center; gap: 8px;
  align-self: center; max-width: 100%;
  padding: 6px 12px; font-size: 13px;
  border: 1px solid var(--el-border-color-light); border-radius: 6px;
  background: var(--el-fill-color-lighter);
}
.selected-file.over { border-color: var(--el-color-danger); color: var(--el-color-danger); }
.selected-file .sf-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.selected-file .sf-size { color: var(--el-text-color-secondary); flex-shrink: 0; }
.selected-file.over .sf-size { color: var(--el-color-danger); }
.selected-file .sf-over { color: var(--el-color-danger); font-size: 12px; flex-shrink: 0; }
.selected-file .sf-remove { flex-shrink: 0; }
@media (max-width: 720px) {
  .selected-file { width: 100%; box-sizing: border-box; }
}
</style>
